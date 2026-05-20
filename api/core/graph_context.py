"""Graph-derived context for Q&A and risk (hubs, blast radius, dependents)."""
from __future__ import annotations

import re
from typing import Any

import networkx as nx

from api.core import engine

# Skip these labels when matching PR file paths (noise).
_NOISE_LABEL = re.compile(
    r"^(push|pop|slice|call|apply|bind|map|filter|reduce|get|set|has|is|toString|valueOf)$",
    re.I,
)


def hub_nodes(G: nx.Graph, top_n: int = 12) -> list[dict]:
    from graphify.analyze import god_nodes

    return god_nodes(G, top_n=top_n)


def blast_radius_from_seeds(
    G: nx.Graph,
    seed_ids: list[str],
    *,
    depth: int = 2,
    max_nodes: int = 80,
) -> tuple[list[str], list[tuple[str, str]], list[dict]]:
    """
    BFS downstream from seed node ids. Returns (node_ids, edges, evidence dicts).
    """
    valid = [s for s in seed_ids if s in G]
    if not valid:
        return [], [], []

    node_set, edges = engine.bfs(G, valid, min(max(depth, 1), 4))
    node_ids = list(node_set)
    if len(node_ids) > max_nodes:
        node_ids = node_ids[:max_nodes]

    evidence: list[dict] = []
    for nid in node_ids[:40]:
        d = G.nodes[nid]
        evidence.append({
            "node_id": nid,
            "label": d.get("label", nid),
            "source_file": d.get("source_file", ""),
            "degree": G.degree(nid),
        })
    return node_ids, edges, evidence


def blast_radius_for_question(
    G: nx.Graph,
    question: str,
    *,
    depth: int = 2,
) -> tuple[str, list[dict]]:
    """Hub-seeded blast context when question mentions hubs / blast radius / impact."""
    hubs = hub_nodes(G, top_n=8)
    if not hubs:
        return "", []

    q = question.lower()
    use_all_hubs = any(
        t in q for t in ("blast", "hub", "impact", "radius", "hotspot", "depend")
    )
    if use_all_hubs:
        seeds = [h["id"] for h in hubs[:5]]
    else:
        seeds = [h["id"] for h in hubs[:3]]

    _, _, evidence = blast_radius_from_seeds(G, seeds, depth=depth)
    lines = ["## Structural impact (from highly connected components)"]
    for h in hubs[:8]:
        lines.append(
            f"- Hub: {h.get('label')} (degree {h.get('degree')})"
        )
    for e in evidence[:20]:
        sf = e.get("source_file") or ""
        if sf:
            lines.append(f"  - dependent: {e.get('label')} in {sf}")
    return "\n".join(lines), evidence


def match_nodes_for_paths(G: nx.Graph, paths: list[str]) -> list[str]:
    """Map file paths or labels to graph node ids."""
    if not paths:
        return []
    normed = [p.strip().replace("\\", "/") for p in paths if p.strip()]
    hits: list[str] = []
    for nid, data in G.nodes(data=True):
        label = (data.get("label") or "").strip()
        sf = (data.get("source_file") or "").replace("\\", "/")
        if not label and not sf:
            continue
        if label and _NOISE_LABEL.match(label.rstrip("()")):
            continue
        for p in normed:
            pl = p.lower()
            if sf and (sf.endswith(pl) or pl in sf or sf.endswith(pl.split("/")[-1])):
                hits.append(nid)
                break
            if label and (label.lower() in pl or pl.endswith(label.lower())):
                hits.append(nid)
                break
    return list(dict.fromkeys(hits))[:30]


def project_blast_radius(
    loadable_apps: list[dict],
    changed_paths: list[str],
    *,
    depth: int = 2,
) -> dict[str, Any]:
    """PR-style blast radius across application repository graphs."""
    all_dependents: list[dict] = []
    hubs: list[dict] = []
    matched: list[dict] = []

    for gmeta in loadable_apps[:2]:
        G = engine.load_graph(gmeta["id"])
        for h in hub_nodes(G, top_n=6):
            h = dict(h)
            h["repository"] = gmeta["name"]
            hubs.append(h)

        seed_ids = match_nodes_for_paths(G, changed_paths)
        for p in changed_paths[:20]:
            matched.append({"path": p, "repository": gmeta["name"], "matched": bool(seed_ids)})

        if not seed_ids and hubs:
            seed_ids = [h["id"] for h in hubs[:2]]

        _, _, ev = blast_radius_from_seeds(G, seed_ids, depth=depth)
        for e in ev:
            e = dict(e)
            e["repository"] = gmeta["name"]
            all_dependents.append(e)

    return {
        "changed_files": changed_paths,
        "matched_seeds": len([m for m in matched if m.get("matched")]),
        "hubs": hubs[:12],
        "dependents": all_dependents[:60],
        "depth": depth,
    }
