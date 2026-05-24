"""Project-level blast radius from pasted file paths (no git integration)."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

import networkx as nx

from api.core import engine, storage
from api.core.cross_graph import loadable_graphs
from api.core.graph_context import hub_seeded_context
from api.core.pkb_storage import load_pkb
from api.core.project_roles import application_graphs, graph_dict
from api.core.product_ontology import enrich_pkb


def _normalize_path(p: str) -> str:
    return str(PurePosixPath(p.replace("\\", "/").strip().lstrip("./")))


def _nodes_for_paths(G: nx.Graph, paths: list[str]) -> list[str]:
    norm_paths = {_normalize_path(p) for p in paths if p.strip()}
    if not norm_paths:
        return []
    hits: list[str] = []
    for nid, data in G.nodes(data=True):
        sf = _normalize_path(data.get("source_file") or "")
        if not sf:
            continue
        for p in norm_paths:
            if sf == p or sf.endswith("/" + p) or p.endswith(sf) or p in sf or sf in p:
                hits.append(nid)
                break
    return hits


def project_blast_radius(
    project_id: str,
    changed_paths: list[str],
    *,
    depth: int = 4,
) -> dict[str, Any]:
    from api.core import database

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    structural = application_graphs(loadable)
    if not structural:
        return {
            "project_id": project_id,
            "changed_paths": changed_paths,
            "impacted": [],
            "hub_findings": [],
            "message": "No ready source graph. Ingest application code first.",
        }

    depth = min(max(depth, 1), 6)
    all_impacted: list[dict[str, Any]] = []
    seeds_matched: list[str] = []

    for gmeta in structural[:3]:
        gid = gmeta["id"]
        if not storage.graph_exists(gid):
            continue
        G = engine.load_graph(gid)
        starts = _nodes_for_paths(G, changed_paths)
        seeds_matched.extend(starts)
        if not starts:
            continue
        fwd_ids, _ = engine.bfs(G, starts, depth)
        rev = G.reverse() if G.is_directed() else G
        dep_ids, _ = engine.bfs(rev, starts, min(depth, 2))
        for nid in fwd_ids:
            if nid not in G:
                continue
            d = G.nodes[nid]
            all_impacted.append({
                "node_id": nid,
                "label": d.get("label", nid),
                "source_file": d.get("source_file", ""),
                "degree": G.degree(nid),
                "direction": "downstream",
                "graph_id": gid,
                "graph_name": gmeta["name"],
            })
        for nid in dep_ids - fwd_ids:
            if nid not in G:
                continue
            d = G.nodes[nid]
            all_impacted.append({
                "node_id": nid,
                "label": d.get("label", nid),
                "source_file": d.get("source_file", ""),
                "degree": G.degree(nid),
                "direction": "upstream",
                "graph_id": gid,
                "graph_name": gmeta["name"],
            })

    # Dedupe by node_id
    by_id: dict[str, dict] = {}
    for item in all_impacted:
        key = f"{item['graph_id']}:{item['node_id']}"
        if key not in by_id or item["degree"] > by_id[key]["degree"]:
            by_id[key] = item
    impacted = sorted(by_id.values(), key=lambda x: -x["degree"])[:80]

    hub_findings: list[dict[str, Any]] = []
    pkb = enrich_pkb(load_pkb(project_id))
    if pkb:
        for f in pkb.get("findings", []):
            if f.get("category_key") == "hub":
                hub_findings.append({
                    "title": f.get("title"),
                    "why_it_matters": f.get("why_it_matters"),
                    "severity": f.get("severity"),
                })
        for item in impacted[:15]:
            if item["degree"] > 20:
                hub_findings.append({
                    "title": f"High connectivity: {item['label']}",
                    "why_it_matters": f"Degree {item['degree']} in blast radius of your change.",
                    "severity": "high",
                })

    return {
        "project_id": project_id,
        "changed_paths": changed_paths,
        "seeds_matched": len(set(seeds_matched)),
        "impacted_count": len(impacted),
        "impacted": impacted,
        "hub_findings": hub_findings[:12],
        "message": None if impacted else "No graph nodes matched those paths. Try full repo-relative paths.",
    }
