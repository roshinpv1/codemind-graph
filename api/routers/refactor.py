"""CodeMind Refactor — topology-safe refactoring and migration planning."""
from __future__ import annotations
import uuid
from pathlib import Path

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database
from api.core.storage import graph_dir

router = APIRouter(prefix="/graphs/{graph_id}/refactor", tags=["Refactor"])


class RefactorPlanRequest(BaseModel):
    goal: str  # e.g. "migrate Flask to FastAPI", "extract auth module", "eliminate circular deps"
    target_modules: list[str] = []  # optional: scope to specific modules
    strategy: str = "incremental"  # incremental | big_bang


class TransformationStep(BaseModel):
    step: int
    action: str
    target_node: str
    target_label: str
    rationale: str
    risk: str = "low"
    dependencies_first: list[str] = []


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


def _topological_order(G: nx.Graph, nodes: list[str]) -> list[str]:
    """Return nodes in topological order (dependency-safe transformation sequence)."""
    try:
        sub = G.subgraph(nodes)
        if sub.is_directed():
            return [n for n in nx.topological_sort(sub) if n in nodes]
    except nx.NetworkXUnfeasible:
        pass
    return sorted(nodes, key=lambda n: G.in_degree(n) if G.is_directed() else G.degree(n))


@router.post("/plan", response_model=dict, status_code=200, summary="Generate a topology-safe transformation plan")
def create_plan(graph_id: str, req: RefactorPlanRequest):
    """
    Analyze the graph and return an ordered migration plan.
    Steps are ordered by topological dependency so each step is safe to execute.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    goal_lower = req.goal.lower()

    # Identify target nodes based on goal keywords and target_modules
    keywords = [w for w in goal_lower.split() if len(w) > 3]
    scored = engine.score_nodes(G, keywords)
    candidate_ids = [nid for _, nid in scored[:40]]

    # Filter by target_modules if specified
    if req.target_modules:
        candidate_ids = [
            nid for nid in candidate_ids
            if any(m.lower() in (G.nodes[nid].get("source_file") or "").lower() for m in req.target_modules)
        ]

    if not candidate_ids:
        return {"goal": req.goal, "steps": [], "message": "No relevant nodes found for this refactoring goal"}

    # Order by dependency (leaves first for safe transformation)
    ordered = _topological_order(G, candidate_ids)

    steps = []
    for i, nid in enumerate(ordered[:20]):
        data = G.nodes[nid]
        deps = [{"id": nb, "label": G.nodes[nb].get("label", nb)} for nb in G.predecessors(nid)] if G.is_directed() else []
        risk = "high" if G.degree(nid) > 10 else "medium" if G.degree(nid) > 4 else "low"
        steps.append({
            "step": i + 1,
            "node_id": nid,
            "node_label": data.get("label", nid),
            "source_file": data.get("source_file", ""),
            "action": _infer_action(req.goal, data),
            "dependencies_to_update_first": deps[:5],
            "degree": G.degree(nid),
            "risk": risk,
            "rationale": f"Process in dependency order — {len(deps)} upstream dependencies",
        })

    plan_id = str(uuid.uuid4())[:8]
    return {
        "plan_id": plan_id,
        "goal": req.goal,
        "strategy": req.strategy,
        "total_steps": len(steps),
        "steps": steps,
        "summary": {
            "high_risk": sum(1 for s in steps if s["risk"] == "high"),
            "medium_risk": sum(1 for s in steps if s["risk"] == "medium"),
            "low_risk": sum(1 for s in steps if s["risk"] == "low"),
        },
    }


def _infer_action(goal: str, node_data: dict) -> str:
    g = goal.lower()
    label = (node_data.get("label") or "").lower()
    if "migrate" in g or "fastapi" in g or "flask" in g:
        return f"Migrate {label} to new framework"
    if "extract" in g or "module" in g:
        return f"Extract {label} into separate module"
    if "circular" in g or "dep" in g:
        return f"Break circular dependency at {label}"
    if "dead" in g or "unused" in g:
        return f"Remove unused node {label}"
    return f"Refactor {label} per goal"


@router.get("/dead-code", response_model=list[dict], summary="Safe-to-delete nodes with zero dependents")
def dead_code(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    result = []
    for n, data in G.nodes(data=True):
        in_deg = G.in_degree(n) if G.is_directed() else G.degree(n)
        if in_deg == 0 and data.get("file_type") == "code":
            result.append({
                "id": n,
                "label": data.get("label", n),
                "source_file": data.get("source_file", ""),
                "out_degree": G.out_degree(n) if G.is_directed() else 0,
            })
    return result


@router.get("/impact", response_model=dict, summary="Impact analysis for a proposed change")
def change_impact(graph_id: str, node: str, depth: int = 3):
    """What will be affected if we change this node?"""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, node)
    if not matches:
        return {"node": node, "impacted": [], "message": "Node not found"}
    nid = matches[0]
    # Reverse BFS — who depends on this node
    rev = G.reverse() if G.is_directed() else G
    node_ids, _ = engine.bfs(rev, [nid], depth)
    node_ids.discard(nid)
    return {
        "node": nid,
        "node_label": G.nodes[nid].get("label", nid),
        "change_depth": depth,
        "impacted_count": len(node_ids),
        "impacted": [
            {
                "id": n,
                "label": G.nodes[n].get("label", n),
                "source_file": G.nodes[n].get("source_file", ""),
                "degree": G.degree(n),
            }
            for n in sorted(node_ids, key=lambda n: G.degree(n), reverse=True)[:50]
            if n in G
        ],
    }


@router.get("/circular-deps", response_model=list[dict], summary="Circular dependency chains to break")
def circular_deps(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    try:
        cycles = list(nx.simple_cycles(G))
        return [
            {
                "cycle": [{"id": n, "label": G.nodes[n].get("label", n)} for n in c],
                "length": len(c),
                "break_at": min(c, key=lambda n: G.degree(n)),
            }
            for c in sorted(cycles, key=len)[:50]
        ]
    except Exception:
        return []


@router.post("/validate", response_model=dict, summary="Check graph consistency post-transformation")
def validate_graph(graph_id: str):
    """Check for orphaned nodes, dangling edges, and isolated components."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        cycles = []
    isolated = list(nx.isolates(G))
    weakly_connected = list(nx.weakly_connected_components(G)) if G.is_directed() else list(nx.connected_components(G))
    return {
        "is_valid": len(cycles) == 0 and len(isolated) == 0,
        "circular_deps": len(cycles),
        "isolated_nodes": len(isolated),
        "connected_components": len(weakly_connected),
        "largest_component_size": max((len(c) for c in weakly_connected), default=0),
        "issues": [
            *(["Circular dependencies detected"] if cycles else []),
            *(["Isolated nodes present"] if isolated else []),
            *(["Graph is fragmented"] if len(weakly_connected) > 1 else []),
        ],
    }
