"""CodeMind Autonomous — architecture anomaly detection and remediation proposals."""
from __future__ import annotations
import uuid
from pathlib import Path

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database
from api.core.graph_health import count_circular_dependencies, sample_cycles_for_display
from api.core.storage import graph_dir

router = APIRouter(prefix="/graphs/{graph_id}/autonomous", tags=["Autonomous"])


class RemediationApproval(BaseModel):
    proposal_id: str
    approved: bool
    notes: str | None = None


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


def _proposals_file(graph_id: str) -> Path:
    return graph_dir(graph_id) / "proposals.json"


def _load_proposals(graph_id: str) -> list[dict]:
    import json
    p = _proposals_file(graph_id)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _save_proposals(graph_id: str, proposals: list[dict]) -> None:
    import json
    _proposals_file(graph_id).write_text(json.dumps(proposals, indent=2))


def _detect_anomalies(G: nx.Graph) -> list[dict]:
    """Detect structural anomalies in the graph that indicate architecture drift."""
    anomalies = []

    # 1. Detect god nodes (high degree relative to average)
    degrees = [G.degree(n) for n in G.nodes()]
    if degrees:
        avg_deg = sum(degrees) / len(degrees)
        for nid, data in G.nodes(data=True):
            d = G.degree(nid)
            if d > avg_deg * 5 and d > 20:
                anomalies.append({
                    "type": "god_node",
                    "severity": "high",
                    "node_id": nid,
                    "node_label": data.get("label", nid),
                    "degree": d,
                    "avg_degree": round(avg_deg, 2),
                    "message": f"Node has {d} connections vs avg {avg_deg:.1f} — likely a god object",
                })

    # 2. Circular dependencies (bounded — safe on large graphs)
    cycle_count, cycles_approx = count_circular_dependencies(G)
    if cycle_count > 0:
        for cycle in sample_cycles_for_display(G, max_samples=10)[0]:
            labels = [G.nodes[n].get("label", n) for n in cycle[:6]]
            suffix = "…" if len(cycle) > 6 else ""
            kind = "Cyclic dependency group" if cycles_approx else "Circular dependency"
            anomalies.append({
                "type": "circular_dependency",
                "severity": "medium",
                "nodes": cycle,
                "length": len(cycle),
                "message": f"{kind} ({len(cycle)} components): {' → '.join(labels)}{suffix}",
            })

    # 3. Detect isolated nodes (dead code / orphaned components)
    isolated = list(nx.isolates(G))
    if isolated:
        anomalies.append({
            "type": "isolated_nodes",
            "severity": "low",
            "count": len(isolated),
            "examples": isolated[:5],
            "message": f"{len(isolated)} isolated nodes detected — potential dead code",
        })

    # 4. Detect fragmented graph (multiple disconnected components)
    if G.is_directed():
        components = list(nx.weakly_connected_components(G))
    else:
        components = list(nx.connected_components(G))
    if len(components) > 3:
        anomalies.append({
            "type": "fragmented_graph",
            "severity": "medium",
            "component_count": len(components),
            "message": f"Graph has {len(components)} disconnected components — subsystem fragmentation",
        })

    # 5. High external coupling communities
    communities = engine.communities_from_graph(G)
    for cid, members in communities.items():
        if len(members) < 3:
            continue
        member_set = set(members)
        external = sum(1 for n in members for nb in G.neighbors(n) if nb not in member_set)
        intra = sum(1 for n in members for nb in G.neighbors(n) if nb in member_set)
        if intra > 0 and external / max(intra, 1) > 3:
            hub = max(members, key=lambda n: G.degree(n), default=members[0])
            anomalies.append({
                "type": "high_coupling",
                "severity": "medium",
                "community_id": cid,
                "hub_label": G.nodes[hub].get("label", hub),
                "external_ratio": round(external / max(intra, 1), 2),
                "message": f"Community {cid} has 3x more external than internal edges — high coupling",
            })

    return anomalies


@router.get("/anomalies", response_model=list[dict], summary="Detected architecture anomalies")
def detect_anomalies(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return _detect_anomalies(G)


@router.post("/heal", response_model=dict, summary="Generate remediation proposals for detected anomalies")
def generate_proposals(graph_id: str):
    """Analyze anomalies and generate actionable fix proposals."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    anomalies = _detect_anomalies(G)
    proposals = []
    for anomaly in anomalies:
        pid = str(uuid.uuid4())[:8]
        atype = anomaly["type"]
        if atype == "god_node":
            proposals.append({
                "id": pid,
                "status": "pending",
                "anomaly_type": atype,
                "severity": anomaly["severity"],
                "target_node": anomaly.get("node_id"),
                "target_label": anomaly.get("node_label"),
                "proposed_action": "Extract responsibilities into smaller, focused modules",
                "steps": [
                    f"Identify distinct responsibilities in {anomaly.get('node_label', '')}",
                    "Group related methods/functions into cohesive sub-modules",
                    "Introduce facade or coordinator pattern to preserve API surface",
                    "Update all {anomaly.get('degree', 0)} dependents incrementally",
                ],
                "risk": "high",
            })
        elif atype == "circular_dependency":
            cycle = anomaly.get("nodes", [])
            proposals.append({
                "id": pid,
                "status": "pending",
                "anomaly_type": atype,
                "severity": anomaly["severity"],
                "cycle": cycle,
                "proposed_action": "Break cycle by introducing an interface or event",
                "steps": [
                    f"Identify the weakest link in the cycle (lowest degree node)",
                    "Extract shared dependency into a common module",
                    "Invert dependency using interface or callback",
                    "Verify with /refactor/validate after change",
                ],
                "risk": "medium",
                "break_at": min(cycle, key=lambda n: G.degree(n)) if cycle else None,
            })
        elif atype == "isolated_nodes":
            proposals.append({
                "id": pid,
                "status": "pending",
                "anomaly_type": atype,
                "severity": anomaly["severity"],
                "count": anomaly["count"],
                "proposed_action": "Review and remove dead code nodes",
                "steps": [
                    f"Review {anomaly['count']} isolated nodes via /refactor/dead-code",
                    "Confirm each is safe to remove (no runtime dynamic imports)",
                    "Delete or mark as deprecated",
                ],
                "risk": "low",
            })
        elif atype == "high_coupling":
            proposals.append({
                "id": pid,
                "status": "pending",
                "anomaly_type": atype,
                "severity": anomaly["severity"],
                "community_id": anomaly.get("community_id"),
                "proposed_action": "Reduce external coupling by introducing anti-corruption layer",
                "steps": [
                    f"Map all external dependencies of community {anomaly.get('community_id')}",
                    "Group external calls by domain and introduce adapters",
                    "Replace direct references with adapter interfaces",
                ],
                "risk": "medium",
            })

    existing = _load_proposals(graph_id)
    existing.extend(proposals)
    _save_proposals(graph_id, existing)
    return {
        "anomalies_found": len(anomalies),
        "proposals_generated": len(proposals),
        "proposals": proposals,
    }


@router.get("/proposals", response_model=list[dict], summary="Pending remediation proposals")
def list_proposals(graph_id: str):
    _require_ready(graph_id)
    return _load_proposals(graph_id)


@router.post("/proposals/approve", response_model=dict, summary="Approve or reject a remediation proposal")
def approve_proposal(graph_id: str, req: RemediationApproval):
    _require_ready(graph_id)
    proposals = _load_proposals(graph_id)
    updated = False
    for p in proposals:
        if p["id"] == req.proposal_id:
            p["status"] = "approved" if req.approved else "rejected"
            if req.notes:
                p["notes"] = req.notes
            updated = True
            break
    if not updated:
        raise HTTPException(404, f"Proposal {req.proposal_id!r} not found")
    _save_proposals(graph_id, proposals)
    return {"ok": True, "proposal_id": req.proposal_id, "status": "approved" if req.approved else "rejected"}


@router.get("/health-trend", response_model=dict, summary="Architecture health metrics")
def health_trend(graph_id: str):
    """Current health snapshot — wire with external time-series DB for trend tracking."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    stats = engine.get_graph_stats(G)
    anomalies = _detect_anomalies(G)
    high = sum(1 for a in anomalies if a.get("severity") == "high")
    medium = sum(1 for a in anomalies if a.get("severity") == "medium")
    low = sum(1 for a in anomalies if a.get("severity") == "low")
    health = max(0, 100 - high * 20 - medium * 8 - low * 2)
    return {
        "graph_id": graph_id,
        "health_score": health,
        "health_level": "healthy" if health >= 80 else "degraded" if health >= 50 else "critical",
        "anomaly_summary": {"high": high, "medium": medium, "low": low, "total": len(anomalies)},
        "graph_stats": stats,
    }
