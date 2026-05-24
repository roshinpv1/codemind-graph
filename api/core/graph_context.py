"""Hub-seeded graph context for architecture and blast-radius questions."""
from __future__ import annotations

import re
from typing import Any

import networkx as nx

from api.core import engine


def _hub_nodes(G: nx.Graph, *, limit: int = 5) -> list[str]:
    if G.number_of_nodes() == 0:
        return []
    degrees = [(n, G.degree(n)) for n in G.nodes()]
    degrees.sort(key=lambda x: -x[1])
    avg = sum(d for _, d in degrees) / len(degrees) if degrees else 0
    hubs = [n for n, d in degrees if d > max(avg * 3, 15)][:limit]
    if not hubs and degrees:
        hubs = [degrees[0][0]]
    return hubs


def hub_seeded_context(
    G: nx.Graph,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 3,
    char_budget: int = 900,
) -> tuple[str, list[dict], list[str]]:
    """
    Combine term-scored seeds with hub nodes for blast-radius / architecture queries.
    Returns (context_text, evidence, seed_node_ids).
    """
    terms = [t.lower() for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question)]
    scored = engine.score_nodes(G, terms)
    term_seeds = [nid for _, nid in scored[:3]]
    hubs = _hub_nodes(G, limit=3)
    starts = list(dict.fromkeys(term_seeds + hubs))[:6]
    if not starts:
        return "", [], []

    node_ids, edges = (
        engine.dfs(G, starts, depth) if mode == "dfs" else engine.bfs(G, starts, depth)
    )
    body = engine.graph_context_text(
        G, node_ids, edges, token_budget=max(200, char_budget // 3), seeds=starts
    )
    evidence = [
        {
            "node_id": n,
            "label": G.nodes[n].get("label", n),
            "source_file": G.nodes[n].get("source_file", ""),
            "is_hub": n in hubs,
        }
        for n in starts
        if n in G
    ]
    if not body.strip():
        return "", evidence, starts
    return body, evidence, starts
