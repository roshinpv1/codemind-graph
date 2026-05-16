"""CodeMind Search — semantic graph-aware engineering discovery."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.core import engine, database

router = APIRouter(prefix="/graphs/{graph_id}/search", tags=["Search"])


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


@router.get("", response_model=dict, summary="Semantic BFS/DFS graph search")
def search(
    graph_id: str,
    q: str,
    mode: str = "bfs",
    depth: int = 3,
    top_n: int = 5,
):
    """
    Natural language query → graph traversal → ranked results.
    mode: 'bfs' (broad context) or 'dfs' (trace a specific path).
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    terms = [t for t in q.lower().split() if len(t) > 2]
    scored = engine.score_nodes(G, terms)
    starts = [nid for _, nid in scored[:top_n]]
    if not starts:
        return {"query": q, "nodes": [], "edges": [], "message": "No matching nodes found."}
    node_ids, edges = engine.dfs(G, starts, depth) if mode == "dfs" else engine.bfs(G, starts, depth)
    result = engine.subgraph_to_nodes(G, node_ids, edges)
    result["query"] = q
    result["mode"] = mode
    result["start_nodes"] = [{"id": n, "label": G.nodes[n].get("label", n), "score": s} for s, n in scored[:top_n]]
    return result


@router.get("/owners", response_model=list[dict], summary="Who owns the code related to a query")
def search_owners(graph_id: str, q: str):
    """
    Returns source files (and community/subsystem) matching a query — as a proxy for ownership.
    Wire with git blame / CODEOWNERS externally for team attribution.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    terms = [t for t in q.lower().split() if len(t) > 2]
    scored = engine.score_nodes(G, terms)
    communities = engine.communities_from_graph(G)
    node_community = {n: cid for cid, members in communities.items() for n in members}
    seen_files: set[str] = set()
    result = []
    for _, nid in scored[:30]:
        data = G.nodes[nid]
        src = data.get("source_file", "")
        if src and src not in seen_files:
            seen_files.add(src)
            cid = node_community.get(nid)
            result.append({
                "source_file": src,
                "representative_node": nid,
                "label": data.get("label", nid),
                "community_id": cid,
            })
    return result


@router.get("/path", response_model=dict, summary="Shortest path between two concepts")
def search_path(graph_id: str, from_: str, to: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.get_shortest_path(G, from_, to)


@router.get("/dependents", response_model=dict, summary="What depends on a given node")
def search_dependents(graph_id: str, node: str, depth: int = 2):
    """Return all nodes that (transitively) depend on the queried node."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, node)
    if not matches:
        return {"node": node, "dependents": [], "message": "Node not found"}
    nid = matches[0]
    rev = G.reverse() if G.is_directed() else G
    node_ids, edges = engine.bfs(rev, [nid], depth)
    node_ids.discard(nid)
    dependents = [
        {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
        for n in node_ids if n in G
    ]
    return {
        "node": nid,
        "node_label": G.nodes[nid].get("label", nid),
        "depth": depth,
        "dependents": dependents,
    }


@router.get("/dependencies", response_model=dict, summary="What a given node depends on")
def search_dependencies(graph_id: str, node: str, depth: int = 2):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, node)
    if not matches:
        return {"node": node, "dependencies": [], "message": "Node not found"}
    nid = matches[0]
    node_ids, edges = engine.bfs(G, [nid], depth)
    node_ids.discard(nid)
    deps = [
        {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
        for n in node_ids if n in G
    ]
    return {
        "node": nid,
        "node_label": G.nodes[nid].get("label", nid),
        "depth": depth,
        "dependencies": deps,
    }
