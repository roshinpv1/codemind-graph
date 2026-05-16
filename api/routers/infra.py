"""CodeMind Infra — topology intelligence for infrastructure (Kubernetes, Terraform, etc.)."""
from __future__ import annotations
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.core import engine, database, pipeline
from api.config import LLM_BACKEND
from api.models.common import JobAccepted

router = APIRouter(prefix="/infra", tags=["Infra"])

# Infra graphs are stored the same way as code graphs — just ingested from infra paths.


class InfraIngestRequest(BaseModel):
    path: str
    name: str
    infra_type: str = "kubernetes"  # kubernetes | terraform | helm | github_actions
    backend: str = LLM_BACKEND


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Infra graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Infra graph not ready — status: {row['status']}")
    return row


@router.post("/graphs", response_model=JobAccepted, status_code=202, summary="Ingest infrastructure repository")
def create_infra_graph(req: InfraIngestRequest, background_tasks: BackgroundTasks):
    gid = str(uuid.uuid4())
    name = f"infra:{req.infra_type}:{req.name}"
    database.insert_graph(gid, name, req.path, req.backend)
    background_tasks.add_task(pipeline.run_extraction, gid, req.path, req.backend)
    return JobAccepted(graph_id=gid, message=f"Infra extraction started for '{req.name}' ({req.infra_type})")


@router.get("/graphs/{graph_id}/impact", response_model=dict, summary="Change blast-radius analysis")
def change_impact(graph_id: str, change: str, depth: int = 4):
    """
    Given a node label (service, resource, config name), return its blast-radius —
    all services/nodes that would be affected by a change to it.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, change)
    if not matches:
        return {"change": change, "impacted": [], "message": "Node not found in infra graph"}
    start = matches[0]
    # Forward: what does this node affect (consumers)
    fwd_ids, fwd_edges = engine.bfs(G, [start], depth)
    # Reverse: what this node depends on
    rev = G.reverse() if G.is_directed() else G
    rev_ids, _ = engine.bfs(rev, [start], depth=2)
    fwd_ids.discard(start)
    rev_ids.discard(start)
    return {
        "changed_node": {"id": start, "label": G.nodes[start].get("label", start)},
        "downstream_impact": [
            {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
            for n in fwd_ids if n in G
        ],
        "upstream_dependencies": [
            {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
            for n in rev_ids if n in G
        ],
        "total_impacted": len(fwd_ids),
    }


@router.get("/graphs/{graph_id}/dependencies", response_model=dict, summary="Full service dependency chain")
def service_dependencies(graph_id: str, service: str, depth: int = 4):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, service)
    if not matches:
        return {"service": service, "dependencies": [], "dependents": [], "message": "Service not found"}
    nid = matches[0]
    dep_ids, dep_edges = engine.bfs(G, [nid], depth)
    rev = G.reverse() if G.is_directed() else G
    svc_ids, _ = engine.bfs(rev, [nid], depth=2)
    dep_ids.discard(nid)
    svc_ids.discard(nid)
    return {
        "service": {"id": nid, "label": G.nodes[nid].get("label", nid)},
        "depends_on": [{"id": n, "label": G.nodes[n].get("label", n)} for n in dep_ids if n in G],
        "depended_on_by": [{"id": n, "label": G.nodes[n].get("label", n)} for n in svc_ids if n in G],
    }


@router.get("/graphs/{graph_id}/ownership", response_model=list[dict], summary="Which team owns which infra component")
def infra_ownership(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    result = []
    for cid, members in communities.items():
        hub = max(members, key=lambda n: G.degree(n), default=None)
        source_files = list({G.nodes[n].get("source_file", "") for n in members if G.nodes[n].get("source_file")})
        result.append({
            "component_group": cid,
            "representative": hub,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "member_count": len(members),
            "source_files": source_files[:10],
        })
    return sorted(result, key=lambda x: x["member_count"], reverse=True)


@router.get("/graphs/{graph_id}/query", response_model=dict, summary="NL query over infra topology")
def infra_query(graph_id: str, q: str, mode: str = "bfs", depth: int = 3):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.query_graph(G, q, mode=mode, depth=depth)


@router.get("/graphs/{graph_id}/stats", response_model=dict, summary="Infrastructure graph statistics")
def infra_stats(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.get_graph_stats(G)
