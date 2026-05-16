"""Generate wiki, callflow, and tree artifacts for a graph."""
from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

from api.core.storage import graph_dir, graph_json_path, wiki_path


def generate_docs_artifacts(
    graph_id: str,
    G: nx.Graph,
    communities: dict[int, list[str]],
    cohesion: dict[int, float],
    labels: dict[int, str],
) -> dict:
    """
    Write wiki/*.md, callflow.html, and tree.html under data/graphs/{graph_id}/.
    Safe to call after graph.json exists. Logs and continues on partial failure.
    """
    out: dict = {"graph_id": graph_id}
    gpath = graph_json_path(graph_id)
    gdir = graph_dir(graph_id)

    try:
        from graphify.wiki import to_wiki

        wiki_dir = wiki_path(graph_id)
        wiki_dir.mkdir(parents=True, exist_ok=True)
        n = to_wiki(G, communities, wiki_dir, community_labels=labels, cohesion=cohesion)
        out["wiki_articles"] = n
    except Exception as exc:  # noqa: BLE001
        out["wiki_error"] = str(exc)
        print(f"[docgen] wiki failed for {graph_id}: {exc}", file=sys.stderr)

    if gpath.exists():
        try:
            from graphify.callflow_html import write_callflow_html

            write_callflow_html(
                graph=str(gpath),
                output=str(gdir / "callflow.html"),
            )
            out["callflow"] = True
        except Exception as exc:  # noqa: BLE001
            out["callflow_error"] = str(exc)
            print(f"[docgen] callflow failed for {graph_id}: {exc}", file=sys.stderr)

        try:
            from graphify.tree_html import write_tree_html

            write_tree_html(graph_path=gpath, output_path=gdir / "tree.html")
            out["tree"] = True
        except Exception as exc:  # noqa: BLE001
            out["tree_error"] = str(exc)
            print(f"[docgen] tree failed for {graph_id}: {exc}", file=sys.stderr)
    else:
        out["callflow_error"] = "graph.json missing"
        out["tree_error"] = "graph.json missing"

    return out
