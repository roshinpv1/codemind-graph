"""Project repository roles — application vs supporting repos."""
from __future__ import annotations

# Primary application graph: prefer legacy `source`, else `test` (current UI slot).
APPLICATION_ROLES = ("source", "test")
# Supporting repos only — used for coverage, pipelines, deploy context (not product map).
SUPPORTING_ROLES = ("test", "ci", "cd")
# UI / completeness expects these three slots (test holds app code when `source` slot removed).
PROJECT_SLOT_ROLES = ("test", "ci", "cd")
ALL_ROLES = ("source", "test", "ci", "cd")


def normalize_role(role: str | None) -> str:
    return (role or "test").lower()


def is_application_graph(meta: dict) -> bool:
    return normalize_role(meta.get("graph_role")) in APPLICATION_ROLES


def application_graphs(loadable: list[dict]) -> list[dict]:
    """Graphs used for product map, hubs, and Q&A structure."""
    apps = [g for g in loadable if is_application_graph(g)]
    if apps:
        # Prefer explicit source repo over test when both exist
        sources = [g for g in apps if normalize_role(g.get("graph_role")) == "source"]
        if sources:
            return sources
        return apps
    return loadable[:1] if loadable else []


def coverage_test_graphs(loadable: list[dict]) -> list[dict]:
    """Separate test-suite repos (not the primary application graph)."""
    app_ids = {g["id"] for g in application_graphs(loadable)}
    return [
        g for g in loadable
        if normalize_role(g.get("graph_role")) == "test" and g["id"] not in app_ids
    ]


def pipeline_graphs(loadable: list[dict]) -> list[dict]:
    return [g for g in loadable if normalize_role(g.get("graph_role")) in ("ci", "cd")]
