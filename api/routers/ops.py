"""CodeMind Ops — incident relationship intelligence and blast-radius analysis."""
from __future__ import annotations

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database

router = APIRouter(prefix="/graphs/{graph_id}/ops", tags=["Ops"])


class IncidentRequest(BaseModel):
    service: str
    alert_type: str = "down"  # down | degraded | slow | error


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


@router.get("/blast-radius", response_model=dict, summary="What fails if this service goes down")
def blast_radius(graph_id: str, service: str, depth: int = 4):
    """
    Compute downstream blast radius: all services/components that depend on `service`
    and would fail or degrade if `service` goes offline.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, service)
    if not matches:
        return {"service": service, "blast_radius": [], "message": "Service not found"}
    nid = matches[0]
    # Who depends on this node (reverse traversal)
    rev = G.reverse() if G.is_directed() else G
    node_ids, edges = engine.bfs(rev, [nid], depth)
    node_ids.discard(nid)
    blast = [
        {
            "id": n,
            "label": G.nodes[n].get("label", n),
            "source_file": G.nodes[n].get("source_file", ""),
            "dependency_depth": _min_hops(edges, nid, n),
        }
        for n in node_ids if n in G
    ]
    return {
        "service": {"id": nid, "label": G.nodes[nid].get("label", nid)},
        "blast_radius_count": len(blast),
        "depth_searched": depth,
        "affected_services": sorted(blast, key=lambda x: x["dependency_depth"]),
    }


def _min_hops(edges: list[tuple], start: str, target: str) -> int:
    """Approximate minimum hops from start to target using edge list."""
    adj: dict[str, set[str]] = {}
    for u, v in edges:
        adj.setdefault(u, set()).add(v)
    visited = {start}
    queue = [(start, 0)]
    while queue:
        node, hops = queue.pop(0)
        if node == target:
            return hops
        for nb in adj.get(node, set()):
            if nb not in visited:
                visited.add(nb)
                queue.append((nb, hops + 1))
    return -1


@router.get("/root-cause", response_model=dict, summary="DFS from alert symptom back to probable root cause")
def root_cause(graph_id: str, symptom: str, depth: int = 4):
    """
    Starting from an alerting node (symptom), trace backwards through dependencies
    to find probable root causes.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, symptom)
    if not matches:
        return {"symptom": symptom, "root_causes": [], "message": "Symptom node not found"}
    nid = matches[0]
    node_ids, edges = engine.dfs(G, [nid], depth)
    # Root causes: nodes with low in-degree (likely originating failures)
    candidates = [
        {
            "id": n,
            "label": G.nodes[n].get("label", n),
            "source_file": G.nodes[n].get("source_file", ""),
            "in_degree": G.in_degree(n) if G.is_directed() else G.degree(n),
            "likelihood": "high" if (G.in_degree(n) if G.is_directed() else G.degree(n)) == 0 else "medium",
        }
        for n in node_ids if n != nid and n in G
    ]
    candidates.sort(key=lambda x: x["in_degree"])
    return {
        "symptom": {"id": nid, "label": G.nodes[nid].get("label", nid)},
        "root_causes": candidates[:10],
    }


@router.post("/incident", response_model=dict, summary="Ingest an incident event and return impact subgraph")
def ingest_incident(graph_id: str, req: IncidentRequest):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, req.service)
    if not matches:
        return {"service": req.service, "impact": [], "message": "Service not found in graph"}
    nid = matches[0]
    rev = G.reverse() if G.is_directed() else G
    # Immediate impact (depth 2 for incident triage speed)
    node_ids, _ = engine.bfs(rev, [nid], depth=2)
    node_ids.discard(nid)
    fwd_ids, _ = engine.bfs(G, [nid], depth=2)
    fwd_ids.discard(nid)
    return {
        "incident": {"service": req.service, "alert_type": req.alert_type},
        "affected_node": {"id": nid, "label": G.nodes[nid].get("label", nid)},
        "immediate_dependents": [
            {"id": n, "label": G.nodes[n].get("label", n)} for n in node_ids if n in G
        ][:20],
        "dependencies_at_risk": [
            {"id": n, "label": G.nodes[n].get("label", n)} for n in fwd_ids if n in G
        ][:10],
        "total_impacted": len(node_ids),
    }


@router.get("/dependencies", response_model=dict, summary="Full runtime dependency chain of a service")
def service_dependencies(graph_id: str, service: str, depth: int = 3):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, service)
    if not matches:
        return {"service": service, "dependencies": [], "message": "Service not found"}
    nid = matches[0]
    dep_ids, _ = engine.bfs(G, [nid], depth)
    dep_ids.discard(nid)
    return {
        "service": {"id": nid, "label": G.nodes[nid].get("label", nid)},
        "dependency_count": len(dep_ids),
        "dependencies": [
            {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
            for n in dep_ids if n in G
        ],
    }


@router.get("/health-summary", response_model=dict, summary="Structural health summary for ops monitoring")
def health_summary(graph_id: str):
    """Returns graph topology metrics useful for ops health monitoring."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    stats = engine.get_graph_stats(G)
    # Single points of failure: nodes whose removal disconnects the graph
    spof_count = 0
    try:
        if not G.is_directed():
            spof_count = len(list(nx.articulation_points(G)))
    except Exception:
        pass
    return {
        **stats,
        "single_points_of_failure": spof_count,
        "risk_level": "high" if spof_count > 5 else "medium" if spof_count > 0 else "low",
    }
