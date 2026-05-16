"""CodeMind Architect — continuous architecture governance via policy rule engine."""
from __future__ import annotations
import re
import uuid
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.core import engine, database
from api.core.graph_health import sample_cycles_for_display, structural_architecture_findings
from api.core.storage import graph_dir
from api.models.common import ViolationOut, OkResponse

router = APIRouter(prefix="/graphs/{graph_id}/architect", tags=["Architect"])


# ── Models ─────────────────────────────────────────────────────────────────────

class PolicyRule(BaseModel):
    name: str
    severity: str = "error"
    description: str = ""
    forbidden_relation: str | None = None
    source_pattern: str | None = None
    target_pattern: str | None = None
    must_not_cross_community: bool = False


class PolicyRequest(BaseModel):
    name: str = Field(..., description="Policy set name, e.g. 'Clean Architecture'")
    rules: list[PolicyRule]


class PolicyOut(BaseModel):
    id: str
    name: str
    rule_count: int


class DriftEntry(BaseModel):
    type: str
    node_id: str | None = None
    node_label: str | None = None
    edge_from: str | None = None
    edge_to: str | None = None
    relation: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


def _policy_file(graph_id: str) -> "Path":
    from pathlib import Path
    return graph_dir(graph_id) / "policies.yaml"


def _load_policies(graph_id: str) -> list[dict]:
    p = _policy_file(graph_id)
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text()) or []


def _save_policies(graph_id: str, policies: list[dict]) -> None:
    _policy_file(graph_id).write_text(yaml.dump(policies, allow_unicode=True))


def _match(pattern: str | None, value: str) -> bool:
    if not pattern:
        return True
    return bool(re.search(pattern, value, re.IGNORECASE))


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/policies", response_model=PolicyOut, status_code=201, summary="Upload an architecture policy set")
def create_policy(graph_id: str, req: PolicyRequest):
    _require_ready(graph_id)
    policies = _load_policies(graph_id)
    pid = str(uuid.uuid4())
    entry = {"id": pid, "name": req.name, "rules": [r.model_dump() for r in req.rules]}
    policies.append(entry)
    _save_policies(graph_id, policies)
    return PolicyOut(id=pid, name=req.name, rule_count=len(req.rules))


@router.get("/policies", response_model=list[PolicyOut], summary="List all architecture policies")
def list_policies(graph_id: str):
    _require_ready(graph_id)
    return [PolicyOut(id=p["id"], name=p["name"], rule_count=len(p.get("rules", [])))
            for p in _load_policies(graph_id)]


@router.delete("/policies/{policy_id}", response_model=OkResponse, summary="Delete a policy set")
def delete_policy(graph_id: str, policy_id: str):
    policies = [p for p in _load_policies(graph_id) if p["id"] != policy_id]
    _save_policies(graph_id, policies)
    return OkResponse(message=f"Policy {policy_id} deleted")


@router.get("/violations", response_model=dict, summary="List current policy violations (add ?narrative=true for LLM remediation guide)")
def get_violations(graph_id: str, narrative: bool = False, backend: str | None = None):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    policies = _load_policies(graph_id)
    communities = engine.communities_from_graph(G)
    node_community = {n: cid for cid, members in communities.items() for n in members}
    violations: list[ViolationOut] = []

    for policy in policies:
        for rule in policy.get("rules", []):
            r = PolicyRule(**rule)
            if r.forbidden_relation:
                for u, v, data in G.edges(data=True):
                    rel = data.get("relation", "")
                    if _match(r.forbidden_relation, rel):
                        src_file = G.nodes[u].get("source_file", "")
                        tgt_file = G.nodes[v].get("source_file", "")
                        if _match(r.source_pattern, src_file) and _match(r.target_pattern, tgt_file):
                            violations.append(ViolationOut(
                                rule=r.name,
                                severity=r.severity,
                                source=u,
                                source_label=G.nodes[u].get("label", u),
                                target=v,
                                target_label=G.nodes[v].get("label", v),
                                relation=rel,
                                message=r.description or f"Forbidden relation '{rel}' violates rule '{r.name}'",
                            ))
            if r.must_not_cross_community:
                for u, v, data in G.edges(data=True):
                    cu, cv = node_community.get(u), node_community.get(v)
                    if cu is not None and cv is not None and cu != cv:
                        src_file = G.nodes[u].get("source_file", "")
                        tgt_file = G.nodes[v].get("source_file", "")
                        if _match(r.source_pattern, src_file) and _match(r.target_pattern, tgt_file):
                            violations.append(ViolationOut(
                                rule=r.name,
                                severity=r.severity,
                                source=u,
                                source_label=G.nodes[u].get("label", u),
                                target=v,
                                target_label=G.nodes[v].get("label", v),
                                relation=data.get("relation", ""),
                                message=r.description or f"Cross-community edge violates bounded-context rule '{r.name}'",
                            ))
    structural = structural_architecture_findings(G)
    result: dict = {
        "violations": [v.model_dump() for v in violations],
        "count": len(violations),
        "structural_findings": structural,
        "structural_count": len(structural),
        "policies_configured": len(policies) > 0,
    }
    if narrative and violations:
        from api.config import LLM_BACKEND
        sample = violations[:10]
        viol_text = "\n".join(
            f"  - [{v.severity}] {v.rule}: {v.source_label} → {v.target_label} ({v.relation}) — {v.message}"
            for v in sample
        )
        prompt = (
            f"You are a software architect reviewing policy violations. "
            f"Write a concise remediation guide.\n\n"
            f"TOTAL VIOLATIONS: {len(violations)}\n"
            f"SAMPLE VIOLATIONS:\n{viol_text}\n\n"
            f"Write 4-6 sentences: summarise the violation patterns, explain the architectural risk, "
            f"and give concrete refactoring steps to fix them."
        )
        result["narrative"] = engine.llm_ask(prompt, backend=backend or LLM_BACKEND, max_tokens=500)
    elif narrative:
        result["narrative"] = "No violations found — architecture is compliant with all policies."
    return result


@router.get("/circular-deps", response_model=dict, summary="Detect circular dependency chains")
def circular_deps(graph_id: str, limit: int = 20):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    cycles, approximate = sample_cycles_for_display(G, max_samples=min(limit, 50))
    items = [
        {
            "cycle": [{"id": n, "label": G.nodes[n].get("label", n)} for n in cycle],
            "length": len(cycle),
            "approximate_group": approximate and len(cycle) > 1,
        }
        for cycle in sorted(cycles, key=len, reverse=True)
    ]
    return {
        "graph_id": graph_id,
        "cycles": items,
        "count": len(items),
        "approximate": approximate,
    }


@router.get("/layer-violations", response_model=list[dict], summary="Cross-layer import analysis")
def layer_violations(graph_id: str, layers: str = ""):
    """
    Pass layers as comma-separated path fragments in dependency order.
    E.g. layers=controllers,services,repositories
    Violations = any edge going from a lower layer to a higher one.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    layer_list = [l.strip() for l in layers.split(",") if l.strip()]
    if not layer_list:
        return []
    violations = []
    for u, v, data in G.edges(data=True):
        src = G.nodes[u].get("source_file", "")
        tgt = G.nodes[v].get("source_file", "")
        src_layer = next((i for i, l in enumerate(layer_list) if l in src), None)
        tgt_layer = next((i for i, l in enumerate(layer_list) if l in tgt), None)
        if src_layer is not None and tgt_layer is not None and src_layer > tgt_layer:
            violations.append({
                "source": u, "source_label": G.nodes[u].get("label", u), "source_layer": layer_list[src_layer],
                "target": v, "target_label": G.nodes[v].get("label", v), "target_layer": layer_list[tgt_layer],
                "relation": data.get("relation", ""),
            })
    return violations


@router.get("/drift", response_model=list[dict], summary="Architecture changes since a snapshot")
def drift(graph_id: str, snapshot: str | None = None):
    """
    Compare current graph against a saved snapshot.
    Pass snapshot=<graph_id> to diff against another graph.
    Without a snapshot, returns top surprising cross-community connections as proxies for drift.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    if snapshot:
        row = database.get_graph(snapshot)
        if not row or row["status"] != "ready":
            raise HTTPException(404, "Snapshot graph not found or not ready")
        G2 = engine.load_graph(snapshot)
        new_nodes = set(G.nodes()) - set(G2.nodes())
        removed_nodes = set(G2.nodes()) - set(G.nodes())
        new_edges = set(G.edges()) - set(G2.edges())
        removed_edges = set(G2.edges()) - set(G.edges())
        return [
            *[{"type": "added_node", "id": n, "label": G.nodes[n].get("label", n)} for n in new_nodes],
            *[{"type": "removed_node", "id": n, "label": G2.nodes[n].get("label", n)} for n in removed_nodes],
            *[{"type": "added_edge", "source": u, "target": v} for u, v in new_edges],
            *[{"type": "removed_edge", "source": u, "target": v} for u, v in removed_edges],
        ]
    return engine.get_surprising_connections(G, top_n=20)
