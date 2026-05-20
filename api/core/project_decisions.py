"""Project-level architecture decisions from inline code markers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx

from api.core import engine
from api.core.project_roles import application_graphs
from api.core.cross_graph import loadable_graphs

_MARKER = re.compile(
    r"^\s*#\s*(WHY|DECISION|TRADEOFF)\s*:?\s*(.*)$",
    re.I | re.MULTILINE,
)


def _scan_file(path: Path, *, repo: str, graph_id: str) -> list[dict[str, Any]]:
    if not path.is_file() or path.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt"):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if len(text) > 200_000:
        text = text[:200_000]
    out: list[dict[str, Any]] = []
    for m in _MARKER.finditer(text):
        kind = m.group(1).upper()
        body = (m.group(2) or "").strip()
        line_no = text[: m.start()].count("\n") + 1
        title = body[:120] if body else f"{kind} in {path.name}"
        out.append({
            "id": f"{graph_id}:{path}:{line_no}",
            "kind": kind,
            "title": title,
            "detail": body[:800] if body else None,
            "source_file": str(path),
            "line": line_no,
            "repository": repo,
            "graph_id": graph_id,
        })
    return out


def extract_decisions_from_graph(
    G: nx.Graph,
    graph_meta: dict[str, Any],
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    root = Path(graph_meta.get("source_path") or "")
    if not root.is_dir():
        return []

    seen_files: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for _, data in G.nodes(data=True):
        sf = (data.get("source_file") or "").strip()
        if not sf or sf in seen_files:
            continue
        seen_files.add(sf)
        full = root / sf if not Path(sf).is_absolute() else Path(sf)
        for d in _scan_file(full, repo=graph_meta["name"], graph_id=graph_meta["id"]):
            decisions.append(d)
            if len(decisions) >= limit:
                return decisions
    return decisions


def extract_decisions_for_loadable(
    loadable: list[dict[str, Any]],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    apps = application_graphs(loadable)
    all_dec: list[dict[str, Any]] = []
    for gmeta in apps[:3]:
        G = engine.load_graph(gmeta["id"])
        all_dec.extend(extract_decisions_from_graph(G, gmeta, limit=limit))
        if len(all_dec) >= limit:
            break
    return all_dec[:limit]


def get_project_decisions(project_id: str, *, limit: int = 40) -> dict[str, Any]:
    from api.core import database
    from api.core.pkb_storage import load_pkb

    pkb = load_pkb(project_id)
    if pkb and pkb.get("decisions"):
        return {
            "project_id": project_id,
            "decisions": pkb["decisions"][:limit],
            "count": len(pkb["decisions"]),
            "source": "pkb",
        }

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    decisions = extract_decisions_for_loadable(loadable, limit=limit)
    return {
        "project_id": project_id,
        "decisions": decisions,
        "count": len(decisions),
        "source": "scan",
    }
