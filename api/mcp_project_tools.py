"""MCP-style project tools for agents — HTTP-backed helpers."""
from __future__ import annotations

from typing import Any

from api.core.project_view import build_project_view
from api.core.project_query import project_ask
from api.core.project_risk import project_blast_radius
from api.core.product_ontology import get_product_map
from api.core.pkb_storage import load_pkb
from api.core.product_ontology import enrich_pkb


def mcp_project_map(project_id: str) -> dict[str, Any]:
    return get_product_map(project_id)


def mcp_project_ask(project_id: str, question: str, persona: str = "developer") -> dict[str, Any]:
    return project_ask(project_id, question, persona=persona)


def mcp_blast_radius(project_id: str, paths: list[str]) -> dict[str, Any]:
    return project_blast_radius(project_id, paths)


def mcp_coverage_gaps(project_id: str, limit: int = 20) -> dict[str, Any]:
    pkb = enrich_pkb(load_pkb(project_id))
    if not pkb:
        return {"gaps": [], "message": "PKB not ready"}
    gaps = [
        c for c in pkb.get("capabilities_ui", [])
        if c.get("test_status_key") == "untested"
    ][:limit]
    return {
        "project_id": project_id,
        "gaps": gaps,
        "coverage_pct": pkb.get("metrics", {}).get("functional_coverage_pct"),
        "confidence": "high" if pkb else "low",
        "evidence": [g.get("evidence", []) for g in gaps],
    }


def mcp_project_view(project_id: str) -> dict[str, Any]:
    return build_project_view(project_id)


TOOLS = {
    "project_map": mcp_project_map,
    "project_ask": mcp_project_ask,
    "blast_radius": mcp_blast_radius,
    "coverage_gaps": mcp_coverage_gaps,
    "project_view": mcp_project_view,
}
