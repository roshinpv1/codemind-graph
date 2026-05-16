"""CodeMind Due Diligence — automated technical architecture health scoring for M&A."""
from __future__ import annotations
import math

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database

router = APIRouter(prefix="/graphs/{graph_id}/due-diligence", tags=["Due Diligence"])


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


def _cohesion_score(G: nx.Graph, communities: dict) -> float:
    """Average ratio of intra-community edges to total community edges."""
    if not communities:
        return 0.0
    scores = []
    for members in communities.values():
        if len(members) < 2:
            continue
        member_set = set(members)
        total = sum(1 for n in members for nb in G.neighbors(n))
        intra = sum(1 for n in members for nb in G.neighbors(n) if nb in member_set)
        if total > 0:
            scores.append(intra / total)
    return round(sum(scores) / max(len(scores), 1), 3)


def _health_score(G: nx.Graph, communities: dict, cycles: list, dead_nodes: list) -> dict:
    """Composite 0–100 architecture health score."""
    node_count = G.number_of_nodes()
    if node_count == 0:
        return {"total": 0, "breakdown": {}}

    # 1. Cohesion score (higher = better) — weight 30
    cohesion = _cohesion_score(G, communities)
    cohesion_pts = cohesion * 30

    # 2. Circular dep penalty — weight 25
    cycle_ratio = min(1.0, len(cycles) / max(node_count * 0.1, 1))
    circular_pts = (1 - cycle_ratio) * 25

    # 3. Dead code penalty — weight 20
    dead_ratio = min(1.0, len(dead_nodes) / max(node_count * 0.2, 1))
    dead_pts = (1 - dead_ratio) * 20

    # 4. God-node concentration penalty — weight 15
    degrees = sorted(G.degree(n) for n in G.nodes())
    p95 = degrees[int(len(degrees) * 0.95)] if degrees else 0
    avg = sum(degrees) / max(len(degrees), 1)
    god_concentration = min(1.0, p95 / max(avg * 10, 1))
    god_pts = (1 - god_concentration) * 15

    # 5. Community balance — weight 10
    sizes = [len(m) for m in communities.values()]
    if len(sizes) > 1:
        max_s, min_s = max(sizes), min(sizes)
        balance = min_s / max(max_s, 1)
    else:
        balance = 1.0
    balance_pts = balance * 10

    total = round(cohesion_pts + circular_pts + dead_pts + god_pts + balance_pts)
    return {
        "total": min(100, max(0, total)),
        "breakdown": {
            "cohesion": round(cohesion_pts, 1),
            "circular_dep_penalty": round(circular_pts, 1),
            "dead_code_penalty": round(dead_pts, 1),
            "god_node_penalty": round(god_pts, 1),
            "community_balance": round(balance_pts, 1),
        },
    }


@router.get("/score", response_model=dict, summary="Overall architecture health score (0–100)")
def health_score(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    dead_nodes = [n for n in G.nodes() if G.in_degree(n) == 0 and G.out_degree(n) == 0] if G.is_directed() else []
    try:
        cycles = list(nx.simple_cycles(G))[:200]
    except Exception:
        cycles = []
    score = _health_score(G, communities, cycles, dead_nodes)
    rating = "A" if score["total"] >= 80 else "B" if score["total"] >= 65 else "C" if score["total"] >= 50 else "D"
    return {
        "graph_id": graph_id,
        "score": score["total"],
        "rating": rating,
        "breakdown": score["breakdown"],
        "summary": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "communities": len(communities),
            "circular_deps": len(cycles),
            "dead_nodes": len(dead_nodes),
        },
    }


@router.get("/debt", response_model=list[dict], summary="Technical debt heatmap by community")
def tech_debt(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    result = []
    for cid, members in communities.items():
        member_set = set(members)
        intra = sum(1 for n in members for nb in G.neighbors(n) if nb in member_set)
        external = sum(1 for n in members for nb in G.neighbors(n) if nb not in member_set)
        avg_degree = sum(G.degree(n) for n in members) / max(len(members), 1)
        # Debt proxy: high external coupling + high avg degree = more coupling debt
        debt_score = min(100, int((external / max(intra + external, 1)) * 60 + min(avg_degree, 20) * 2))
        hub = max(members, key=lambda n: G.degree(n), default=None)
        result.append({
            "community_id": cid,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "member_count": len(members),
            "intra_edges": intra,
            "external_edges": external,
            "avg_degree": round(avg_degree, 2),
            "debt_score": debt_score,
            "debt_level": "high" if debt_score >= 60 else "medium" if debt_score >= 30 else "low",
        })
    return sorted(result, key=lambda x: x["debt_score"], reverse=True)


@router.get("/dead-code", response_model=list[dict], summary="Unreachable / dead code nodes")
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
                "out_degree": G.out_degree(n) if G.is_directed() else G.degree(n),
            })
    return sorted(result, key=lambda x: x["source_file"])


@router.get("/complexity", response_model=list[dict], summary="Per-community complexity metrics")
def complexity(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    result = []
    for cid, members in communities.items():
        member_set = set(members)
        sub = G.subgraph(members)
        try:
            density = nx.density(sub)
        except Exception:
            density = 0.0
        hub = max(members, key=lambda n: G.degree(n), default=None)
        result.append({
            "community_id": cid,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "size": len(members),
            "internal_edges": sub.number_of_edges(),
            "external_edges": sum(1 for n in members for nb in G.neighbors(n) if nb not in member_set),
            "density": round(density, 4),
            "max_degree_in_community": max((G.degree(n) for n in members), default=0),
        })
    return sorted(result, key=lambda x: x["size"], reverse=True)


@router.get("/report", response_model=dict, summary="Full due-diligence narrative report (add ?narrative=true for LLM summary)")
def full_report(graph_id: str, narrative: bool = False, backend: str | None = None):
    """Aggregates all signals into a single due-diligence report JSON."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    dead = [n for n in G.nodes() if (G.in_degree(n) if G.is_directed() else G.degree(n)) == 0]
    try:
        cycles = list(nx.simple_cycles(G))[:200]
    except Exception:
        cycles = []
    score = _health_score(G, communities, cycles, dead)
    gods = engine.get_god_nodes(G, top_n=10)
    rating = "A" if score["total"] >= 80 else "B" if score["total"] >= 65 else "C" if score["total"] >= 50 else "D"
    risks = [
        *(["High circular dependency count indicates tight coupling"] if len(cycles) > 10 else []),
        *(["Significant dead code detected"] if len(dead) > G.number_of_nodes() * 0.1 else []),
        *(["Very high-degree god nodes — single points of failure"] if gods and gods[0].get("degree", 0) > 50 else []),
    ]
    result = {
        "graph_id": graph_id,
        "health_score": score["total"],
        "rating": rating,
        "score_breakdown": score["breakdown"],
        "summary": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "communities": len(communities),
            "circular_deps": len(cycles),
            "dead_nodes": len(dead),
        },
        "god_nodes": gods[:10],
        "top_circular_deps": [{"cycle": c, "length": len(c)} for c in cycles[:5]],
        "risks": risks,
    }
    if narrative:
        from api.config import LLM_BACKEND
        god_labels = [g.get("label", g.get("id", "?")) for g in gods[:5]]
        prompt = (
            f"You are a technical due-diligence analyst. Write an investment-grade technical health assessment.\n\n"
            f"HEALTH SCORE: {score['total']}/100 (Grade {rating})\n"
            f"BREAKDOWN: cohesion={score['breakdown']['cohesion']}, "
            f"circular_deps_penalty={score['breakdown']['circular_dep_penalty']}, "
            f"dead_code_penalty={score['breakdown']['dead_code_penalty']}\n"
            f"GRAPH: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} modules\n"
            f"CIRCULAR DEPS: {len(cycles)}\n"
            f"DEAD CODE: {len(dead)} nodes ({round(len(dead)/max(G.number_of_nodes(),1)*100)}%)\n"
            f"GOD NODES: {', '.join(god_labels)}\n"
            f"RISKS: {'; '.join(risks) or 'None identified'}\n\n"
            f"Write a 4-6 sentence technical health narrative covering: overall quality, key risks, "
            f"maintainability, and acquirer/investor recommendations."
        )
        result["narrative"] = engine.llm_ask(prompt, backend=backend or LLM_BACKEND, max_tokens=500)
    return result
