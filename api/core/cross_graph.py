"""Shared helpers for multi-graph project analysis."""
from __future__ import annotations

import networkx as nx

from api.core import storage
from api.routers.coverage import _COVERAGE_RELS, _get_edge_rel


def loadable_graphs(graphs: list) -> list:
    return [
        g for g in graphs
        if g["status"] == "ready" and storage.graph_exists(g["id"])
    ]


def cross_graph_match_entry_points(
    G_source: nx.Graph,
    G_test: nx.Graph,
    entry_pts: dict,
) -> set[str]:
    ep_label_idx: dict[str, str] = {
        ep["label"].strip().lower().rstrip("()"): nid
        for nid, ep in entry_pts.items()
    }
    test_labels: set[str] = set()
    for _, d in G_test.nodes(data=True):
        lbl = d.get("label", "").strip().lower().rstrip("()")
        if lbl:
            test_labels.add(lbl)
    for u, v in G_test.edges():
        ed = G_test[u][v]
        if isinstance(ed, dict) and "relation" not in ed:
            ed = next(iter(ed.values()), {})
        rel = ed.get("relation", "") if isinstance(ed, dict) else ""
        if rel in _COVERAGE_RELS or not rel:
            for node in (u, v):
                lbl = G_test.nodes.get(node, {}).get("label", "").strip().lower().rstrip("()")
                if lbl:
                    test_labels.add(lbl)
    return {ep_label_idx[lbl] for lbl in test_labels if lbl in ep_label_idx}
