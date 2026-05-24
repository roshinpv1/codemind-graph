<<<<<<< Updated upstream
"""Project repository roles — Application (CI slot), Test, CD."""
=======
"""Project repository roles — source (application), test, cd."""
>>>>>>> Stashed changes
from __future__ import annotations

from typing import Any

<<<<<<< Updated upstream
=======
# Legacy DB rows may still store graph_role='ci' — treated as source everywhere.
_ROLE_ALIASES: dict[str, str] = {"ci": "source"}

PROJECT_SLOT_ROLES = ("source", "test", "cd")
ALL_ROLES = PROJECT_SLOT_ROLES
APPLICATION_ROLES = ("source",)

ROLE_LABELS = {
    "source": "Source",
    "test": "Test",
    "cd": "CD",
}

>>>>>>> Stashed changes

def graph_dict(g: Any) -> dict:
    """Normalize sqlite3.Row or dict from database.get_project_graphs."""
    if isinstance(g, dict):
        return g
    return {k: g[k] for k in g.keys()}

<<<<<<< Updated upstream
# Application codebase: CI slot (primary). Legacy `source` still supported.
APPLICATION_ROLES = ("source", "ci")
# Older projects may have ingested app code under `test` before CI = Application.
LEGACY_APPLICATION_ROLES = ("test",)
PROJECT_SLOT_ROLES = ("ci", "test", "cd")
ALL_ROLES = ("source", "test", "ci", "cd")

ROLE_LABELS = {
    "source": "Application",
    "ci": "Application",
    "test": "Test",
    "cd": "CD",
}


def normalize_role(role: str | None) -> str:
    return (role or "ci").lower()
=======

def normalize_role(role: str | None) -> str:
    r = (role or "source").lower()
    return _ROLE_ALIASES.get(r, r)
>>>>>>> Stashed changes


def role_label(role: str | None) -> str:
    return ROLE_LABELS.get(normalize_role(role), role or "?")


<<<<<<< Updated upstream
def is_application_graph(meta: Any) -> bool:
    d = graph_dict(meta)
    r = normalize_role(d.get("graph_role"))
    return r in APPLICATION_ROLES or r in LEGACY_APPLICATION_ROLES


def application_graphs(loadable: list[Any]) -> list[dict]:
    """Graphs used for product map, hubs, and Q&A structure."""
    rows = [graph_dict(g) for g in loadable]
    for preferred in ("ci", "source"):
        apps = [g for g in rows if normalize_role(g.get("graph_role")) == preferred]
        if apps:
            return apps
    # Legacy: app was ingested under test when that slot meant "application"
    legacy = [g for g in rows if normalize_role(g.get("graph_role")) == "test"]
    if legacy and not any(
        normalize_role(g.get("graph_role")) in ("ci", "source") for g in rows
    ):
=======
def normalize_graph_meta(data: dict) -> dict:
    """Coerce graph_role for API responses (ci → source)."""
    out = dict(data)
    out["graph_role"] = normalize_role(out.get("graph_role"))
    return out


def is_application_graph(meta: Any) -> bool:
    return normalize_role(graph_dict(meta).get("graph_role")) == "source"


def application_graphs(loadable: list[Any]) -> list[dict]:
    """Graphs used for product map, hubs, Q&A, and coverage entry points."""
    rows = [graph_dict(g) for g in loadable]
    apps = [g for g in rows if normalize_role(g.get("graph_role")) == "source"]
    if apps:
        return apps
    # Legacy: app was ingested under test when roles were mis-assigned.
    legacy = [g for g in rows if normalize_role(g.get("graph_role")) == "test"]
    if legacy and not apps:
>>>>>>> Stashed changes
        return legacy
    return rows[:1] if rows else []


def coverage_test_graphs(loadable: list[Any]) -> list[dict]:
<<<<<<< Updated upstream
    """Test-suite repos used for cross-repo coverage (not the application graph)."""
=======
    """Test-suite repos for cross-repo coverage (not the application graph)."""
>>>>>>> Stashed changes
    rows = [graph_dict(g) for g in loadable]
    app_ids = {g["id"] for g in application_graphs(rows)}
    return [
        g for g in rows
        if normalize_role(g.get("graph_role")) == "test" and g["id"] not in app_ids
    ]


def has_application_graph(graphs: list[Any]) -> bool:
    ready = [graph_dict(g) for g in graphs if graph_dict(g).get("status") == "ready"]
    return bool(application_graphs(ready))
