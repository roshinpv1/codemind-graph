"""Extract architectural decisions from rationale nodes and comment markers."""
from __future__ import annotations

import re
from typing import Any

import networkx as nx

from api.core import engine, storage
from api.core.cross_graph import loadable_graphs
from api.core.project_roles import application_graphs, graph_dict

_DECISION_MARKERS = re.compile(
    r"#\s*(WHY|DECISION|TRADEOFF|RATIONALE|NOTE|IMPORTANT)\s*:?\s*(.+)",
    re.I,
)


def _decision_from_rationale_node(G: nx.Graph, nid: str, gmeta: dict) -> dict[str, Any] | None:
    data = G.nodes.get(nid, {})
    if data.get("file_type") != "rationale":
        return None
    label = (data.get("label") or "").strip()
    if not label or len(label) < 8:
        return None
    kind = "decision"
    lower = label.lower()
    if "tradeoff" in lower or "trade-off" in lower:
        kind = "tradeoff"
    elif label.startswith("#"):
        m = _DECISION_MARKERS.match(label)
        if m:
            kind = m.group(1).lower()
            label = m.group(2).strip()
    parent = ""
    for u, v, ed in G.edges(data=True):
        rel = ed.get("relation", "") if isinstance(ed, dict) else ""
        if rel == "rationale_for" and (u == nid or v == nid):
            other = v if u == nid else u
            parent = G.nodes.get(other, {}).get("label", other)
            break
    return {
        "title": label[:200],
        "kind": kind,
        "detail": f"Documented near {parent}" if parent else "From source comments",
        "source_file": data.get("source_file", ""),
        "graph_id": gmeta["id"],
        "graph_name": gmeta["name"],
        "node_id": nid,
    }


def scan_graph_decisions(gmeta: dict) -> list[dict[str, Any]]:
    gid = gmeta["id"]
    if not storage.graph_exists(gid):
        return []
    G = engine.load_graph(gid)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for nid, data in G.nodes(data=True):
        if data.get("file_type") == "rationale":
            d = _decision_from_rationale_node(G, nid, gmeta)
            if d and d["title"] not in seen:
                seen.add(d["title"])
                out.append(d)
    return out[:40]


def collect_project_decisions(project_id: str) -> list[dict[str, Any]]:
    from api.core import database

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    structural = application_graphs(loadable)
    cd_graphs = [graph_dict(g) for g in loadable if graph_dict(g).get("graph_role") == "cd"]
    targets = structural + cd_graphs

    all_dec: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gmeta in targets:
        for d in scan_graph_decisions(gmeta):
            key = (d.get("title", ""), d.get("source_file", ""))
            if key in seen:
                continue
            seen.add(key)
            all_dec.append(d)
    return all_dec[:50]
