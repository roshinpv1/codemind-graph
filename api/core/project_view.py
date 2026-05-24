"""Aggregated 360° project view — single payload for dashboard."""
from __future__ import annotations

from typing import Any

from api.core import database
from api.core.cross_graph import loadable_graphs
from api.core.pkb_storage import load_pkb
from api.core.product_ontology import enrich_pkb, get_briefing_user, get_product_map
from api.core.project_roles import PROJECT_SLOT_ROLES, has_application_graph, normalize_role, role_label
from api.core.cluster_snapshot import load_snapshot


def build_project_view(project_id: str) -> dict[str, Any]:
    row = database.get_project(project_id)
    if not row:
        raise ValueError(f"Project {project_id!r} not found")

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    pkb = enrich_pkb(load_pkb(project_id))
    briefing = get_briefing_user(project_id)
    product_map = get_product_map(project_id)

    slots: dict[str, dict] = {}
    for role in PROJECT_SLOT_ROLES:
        g = next((x for x in graphs if normalize_role(x["graph_role"]) == role), None)
        if role == "source" and not g:
            g = next((x for x in graphs if normalize_role(x["graph_role"]) == "source"), None)
        slots[role] = {
            "role": role,
            "role_label": role_label(role),
            "filled": g is not None,
            "graph_id": g["id"] if g else None,
            "name": g["name"] if g else None,
            "status": g["status"] if g else None,
        }

    snapshot = load_snapshot(project_id)
    delivery = (pkb or {}).get("delivery", {})
    if snapshot:
        delivery = {**delivery, "snapshot": {
            "captured_at": snapshot.get("captured_at"),
            "cluster": snapshot.get("cluster"),
            "resource_count": snapshot.get("resource_count"),
        }}

    return {
        "project_id": project_id,
        "project_name": row["name"],
        "ready": bool(pkb),
        "understanding_updated_at": (pkb or {}).get("meta", {}).get("synthesized_at"),
        "briefing": briefing,
        "product_map": product_map,
        "slots": slots,
        "completeness": {
            "has_source": has_application_graph(graphs),
            "graphs_ready": len(loadable),
            "roles_present": list({normalize_role(g["graph_role"]) for g in loadable}),
        },
        "metrics": (pkb or {}).get("metrics", {}),
        "top_findings": (pkb or {}).get("findings", [])[:8],
        "decisions": (pkb or {}).get("decisions", [])[:15],
        "delivery": delivery,
        "coverage_links_count": len((pkb or {}).get("coverage_links", [])),
    }
