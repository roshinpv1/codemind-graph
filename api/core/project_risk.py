"""Project-level PR blast radius and risk surfacing."""
from __future__ import annotations

from typing import Any

from api.core import database
from api.core.cross_graph import loadable_graphs
from api.core.graph_context import project_blast_radius
from api.core.project_roles import application_graphs
from api.core.pkb_storage import load_pkb
from api.core.product_ontology import enrich_pkb


def compute_blast_radius(
    project_id: str,
    changed_paths: list[str],
    *,
    depth: int = 2,
) -> dict[str, Any]:
    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    apps = application_graphs(loadable)
    if not apps:
        return {
            "project_id": project_id,
            "ready": False,
            "message": "No application repository indexed yet.",
            "changed_files": changed_paths,
            "dependents": [],
            "hubs": [],
        }

    result = project_blast_radius(apps, changed_paths, depth=depth)
    pkb = enrich_pkb(load_pkb(project_id))
    hub_findings = []
    if pkb:
        hub_findings = [
            f for f in pkb.get("findings", [])
            if f.get("category_key") == "hub"
        ][:8]

    return {
        "project_id": project_id,
        "ready": True,
        "depth": depth,
        "hub_findings": hub_findings,
        **result,
    }
