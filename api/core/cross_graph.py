"""Shared helpers for multi-graph project analysis."""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import networkx as nx

from api.core import storage
from api.routers.coverage import _COVERAGE_RELS, _get_edge_rel


def loadable_graphs(graphs: list) -> list[dict]:
    from api.core.project_roles import graph_dict

    out: list[dict] = []
    for g in graphs:
        d = graph_dict(g)
        if d.get("status") == "ready" and storage.graph_exists(d["id"]):
            out.append(d)
    return out


def _norm_label(lbl: str) -> str:
    return lbl.strip().lower().rstrip("()")


def _test_labels_and_paths(G_test: nx.Graph) -> tuple[set[str], set[str]]:
    labels: set[str] = set()
    paths: set[str] = set()
    for _, d in G_test.nodes(data=True):
        lbl = _norm_label(d.get("label", ""))
        if lbl:
            labels.add(lbl)
        sf = (d.get("source_file") or "").replace("\\", "/").lower()
        if sf:
            paths.add(sf)
            parts = PurePosixPath(sf).parts
            if len(parts) >= 2:
                paths.add("/".join(parts[-2:]))
    for u, v in G_test.edges():
        ed = G_test[u][v]
        if isinstance(ed, dict) and "relation" not in ed:
            ed = next(iter(ed.values()), {})
        rel = ed.get("relation", "") if isinstance(ed, dict) else ""
        if rel in _COVERAGE_RELS or not rel:
            for node in (u, v):
                lbl = _norm_label(G_test.nodes.get(node, {}).get("label", ""))
                if lbl:
                    labels.add(lbl)
    return labels, paths


def _package_tokens_from_graph(G: nx.Graph) -> set[str]:
    """Heuristic package/module tokens from source paths."""
    tokens: set[str] = set()
    for _, d in G.nodes(data=True):
        sf = (d.get("source_file") or "").replace("\\", "/")
        if not sf:
            continue
        parts = PurePosixPath(sf).parts
        for p in parts:
            if p.endswith((".py", ".go", ".ts", ".js", ".java")):
                continue
            if len(p) > 2 and p not in ("src", "lib", "test", "tests", "pkg", "internal"):
                tokens.add(p.lower())
    return tokens


def cross_graph_match_entry_points(
    G_source: nx.Graph,
    G_test: nx.Graph,
    entry_pts: dict,
) -> set[str]:
    """Label-only match (legacy)."""
    ep_label_idx: dict[str, str] = {
        _norm_label(ep["label"]): nid for nid, ep in entry_pts.items()
    }
    test_labels, _ = _test_labels_and_paths(G_test)
    return {ep_label_idx[lbl] for lbl in test_labels if lbl in ep_label_idx}


def build_coverage_links(
    G_source: nx.Graph,
    test_graphs: list[tuple[dict, nx.Graph]],
    entry_pts: dict,
) -> list[dict[str, Any]]:
    """
    Path-aware and label-aware links from test graph nodes to source entry points.
    Returns list of {source_entry_id, test_label, confidence, method}.
    """
    ep_label_idx: dict[str, str] = {
        _norm_label(ep["label"]): nid for nid, ep in entry_pts.items()
    }
    ep_path_idx: dict[str, list[str]] = {}
    for nid, ep in entry_pts.items():
        sf = (ep.get("source_file") or "").replace("\\", "/").lower()
        if sf:
            ep_path_idx.setdefault(sf, []).append(nid)
            base = PurePosixPath(sf).name
            ep_path_idx.setdefault(base, []).append(nid)

    source_pkgs = _package_tokens_from_graph(G_source)
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for gmeta, G_test in test_graphs:
        test_labels, test_paths = _test_labels_and_paths(G_test)
        test_pkgs = _package_tokens_from_graph(G_test)

        for lbl in test_labels:
            if lbl in ep_label_idx:
                key = (ep_label_idx[lbl], lbl)
                if key not in seen:
                    seen.add(key)
                    links.append({
                        "source_entry_id": ep_label_idx[lbl],
                        "source_label": entry_pts[ep_label_idx[lbl]]["label"],
                        "test_graph_id": gmeta["id"],
                        "test_graph_name": gmeta["name"],
                        "test_reference": lbl,
                        "confidence": "high",
                        "method": "label_match",
                    })

        for path in test_paths:
            for ep_path, nids in ep_path_idx.items():
                if ep_path in path or path.endswith(ep_path):
                    for nid in nids:
                        key = (nid, path)
                        if key in seen:
                            continue
                        seen.add(key)
                        links.append({
                            "source_entry_id": nid,
                            "source_label": entry_pts[nid]["label"],
                            "test_graph_id": gmeta["id"],
                            "test_graph_name": gmeta["name"],
                            "test_reference": path,
                            "confidence": "medium",
                            "method": "path_match",
                        })

        shared = source_pkgs & test_pkgs
        if shared and len(shared) >= 1:
            for nid, ep in entry_pts.items():
                sf = (ep.get("source_file") or "").lower()
                if not any(pkg in sf for pkg in shared):
                    continue
                key = (nid, f"pkg:{','.join(sorted(shared)[:3])}")
                if key in seen:
                    continue
                seen.add(key)
                links.append({
                    "source_entry_id": nid,
                    "source_label": ep["label"],
                    "test_graph_id": gmeta["id"],
                    "test_graph_name": gmeta["name"],
                    "test_reference": f"package:{','.join(sorted(shared)[:5])}",
                    "confidence": "low",
                    "method": "package_alignment",
                })

    return links[:200]


def covered_entry_ids_from_links(
    entry_pts: dict,
    links: list[dict[str, Any]],
) -> set[str]:
    high_med = {
        l["source_entry_id"]
        for l in links
        if l.get("confidence") in ("high", "medium", "low")
    }
    return {nid for nid in entry_pts if nid in high_med}
