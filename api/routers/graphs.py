"""CodeMind Context API — core graph ingestion, versioned storage, and traversal."""
from __future__ import annotations
import threading
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from api.core import database, storage, engine, pipeline
from api.config import LLM_BACKEND
from api.models.common import (
    GraphMeta, GraphStatus, IngestRequest, JobAccepted,
    NodeOut, QueryResult, PathResult, StatsResult, OkResponse,
)

router = APIRouter(prefix="/graphs", tags=["Context API"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_graph(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    return row


def _require_ready(graph_id: str):
    row = _require_graph(graph_id)
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


def _row_to_meta(row) -> GraphMeta:
    keys = row.keys()
    data = {k: row[k] for k in keys}
    data.setdefault("graph_role", "source")
    data.setdefault("project_id", None)
    return GraphMeta(**data)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[GraphMeta], summary="List graphs (optionally filter by project)")
def list_graphs(project_id: str | None = None):
    return [_row_to_meta(r) for r in database.list_graphs(project_id=project_id)]


@router.post("", response_model=JobAccepted, status_code=202, summary="Ingest a repository")
def create_graph(req: IngestRequest, background_tasks: BackgroundTasks):
    if not database.get_project(req.project_id):
        raise HTTPException(404, f"Project {req.project_id!r} not found")
    existing = database.get_graph_for_project_role(req.project_id, req.graph_role.value)
    if existing:
        raise HTTPException(
            409,
            f"Project already has a '{req.graph_role.value}' graph ({existing['name']}). "
            "Delete it before ingesting a replacement.",
        )
    gid = str(uuid.uuid4())
    backend = req.backend or LLM_BACKEND
    database.insert_graph(
        gid, req.name, req.path, backend,
        graph_role=req.graph_role.value,
        project_id=req.project_id,
    )
    background_tasks.add_task(
        pipeline.run_extraction,
        gid,
        req.path,
        backend,
        req.dedup_llm,
        req.use_semantic,
    )
    return JobAccepted(
        graph_id=gid,
        message=f"Extraction started for '{req.name}' (role={req.graph_role.value})",
    )


@router.get("/{graph_id}", response_model=GraphMeta, summary="Get graph metadata")
def get_graph(graph_id: str):
    return _row_to_meta(_require_graph(graph_id))


@router.delete("/{graph_id}", response_model=OkResponse, summary="Delete a graph")
def delete_graph(graph_id: str, project_id: str | None = None):
    row = _require_graph(graph_id)
    if project_id and row["project_id"] != project_id:
        raise HTTPException(
            403,
            f"Graph {graph_id!r} does not belong to project {project_id!r}",
        )
    storage.delete_graph(graph_id)
    database.delete_graph_row(graph_id)
    return OkResponse(message=f"Graph {graph_id} deleted")


@router.post("/{graph_id}/update", response_model=JobAccepted, status_code=202, summary="Re-index a graph")
def update_graph(graph_id: str, background_tasks: BackgroundTasks):
    row = _require_graph(graph_id)
    background_tasks.add_task(pipeline.run_extraction, graph_id, row["source_path"], row["backend"] or LLM_BACKEND)
    return JobAccepted(graph_id=graph_id, message="Re-extraction started")


@router.get("/{graph_id}/stats", response_model=StatsResult, summary="Graph statistics")
def graph_stats(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.get_graph_stats(G)


@router.get("/{graph_id}/query", response_model=dict, summary="Semantic BFS/DFS query (add ?llm=true for natural-language answer)")
def query(
    graph_id: str,
    q: str,
    mode: str = "bfs",
    depth: int = 3,
    llm: bool = False,
    backend: str | None = None,
):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    if llm:
        return engine.llm_query_answer(
            G, q, mode=mode, depth=min(depth, 6),
            backend=backend or LLM_BACKEND,
        )
    result = engine.query_graph(G, q, mode=mode, depth=min(depth, 6))
    return result if isinstance(result, dict) else result.model_dump()


@router.get("/{graph_id}/nodes/{node_id}", response_model=dict, summary="Get a single node with neighbors")
def get_node(graph_id: str, node_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    if node_id not in G:
        # try fuzzy
        matches = engine.find_nodes(G, node_id)
        if not matches:
            raise HTTPException(404, f"Node {node_id!r} not found")
        node_id = matches[0]
    return engine.node_to_dict(G, node_id)


@router.get("/{graph_id}/gods", response_model=list[dict], summary="High-centrality god nodes")
def god_nodes(graph_id: str, top_n: int = 20):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.get_god_nodes(G, top_n)


@router.get("/{graph_id}/path", response_model=PathResult, summary="Shortest path between two concepts")
def shortest_path(graph_id: str, from_: str, to: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    result = engine.get_shortest_path(G, from_, to)
    if "error" in result:
        return PathResult(error=result["error"])
    return PathResult(**result)


@router.get("/{graph_id}/communities", response_model=list[dict], summary="List communities / subsystems")
def get_communities(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    out = []
    for cid, members in communities.items():
        hub = max(members, key=lambda n: G.degree(n), default=None)
        out.append({
            "community_id": cid,
            "size": len(members),
            "hub_node": hub,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "members": members[:20],
        })
    return sorted(out, key=lambda x: x["size"], reverse=True)


@router.get("/{graph_id}/report", summary="Full GRAPH_REPORT.md as text")
def get_report(graph_id: str):
    _require_ready(graph_id)
    p = storage.report_path(graph_id)
    if not p.exists():
        raise HTTPException(404, "Report not generated yet")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@router.get("/{graph_id}/surprising", response_model=list[dict], summary="Surprising cross-community connections")
def surprising_connections(graph_id: str, top_n: int = 10):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.get_surprising_connections(G, top_n)


@router.get("/{graph_id}/summarize", response_model=dict, summary="LLM-generated executive architecture summary")
def summarize(graph_id: str, backend: str | None = None):
    """Call the LLM to produce an executive-level summary of the codebase architecture."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.llm_architecture_summary(G, backend=backend or LLM_BACKEND)


@router.get("/{graph_id}/explain/{node_id:path}", response_model=dict, summary="LLM plain-language node explanation")
def explain_node(graph_id: str, node_id: str, backend: str | None = None):
    """Get an LLM-generated plain-language explanation of a node and its role."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    # Support fuzzy lookup by label
    if node_id not in G:
        matches = engine.find_nodes(G, node_id)
        if not matches:
            raise HTTPException(404, f"Node {node_id!r} not found")
        node_id = matches[0]
    return engine.llm_explain_node(G, node_id, backend=backend or LLM_BACKEND)


@router.post("/{graph_id}/communities/label", response_model=dict, summary="LLM-generated community labels")
def label_communities(graph_id: str, backend: str | None = None):
    """Use the LLM to assign human-readable names to every community in the graph."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    labels = engine.llm_label_communities(G, communities, backend=backend or LLM_BACKEND)
    # Persist labels for use in docs/wiki generation
    from api.core.storage import graph_dir
    import json as _json
    labels_path = graph_dir(graph_id) / ".graphify_labels.json"
    labels_path.write_text(_json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")
    return {"labels": labels, "count": len(labels), "persisted": True}
