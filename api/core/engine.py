"""Graph query engine — wraps graphify's serve.py traversal functions for HTTP use."""
from __future__ import annotations
import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from api.core.storage import graph_json_path
from api.config import LLM_BACKEND


# ── Graph loading ──────────────────────────────────────────────────────────────

def load_graph(graph_id: str) -> nx.Graph:
    path = graph_json_path(graph_id)
    if not path.exists():
        raise FileNotFoundError(f"Graph {graph_id!r} not found. Run extraction first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "links" not in data and "edges" in data:
        data = dict(data, links=data["edges"])
    data = {**data, "directed": True}
    try:
        return json_graph.node_link_graph(data, edges="links")
    except TypeError:
        return json_graph.node_link_graph(data)


# ── Community reconstruction ───────────────────────────────────────────────────

def communities_from_graph(G: nx.Graph) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for nid, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is not None:
            result.setdefault(int(cid), []).append(nid)
    return result


# ── Node scoring / lookup (mirrors serve.py) ──────────────────────────────────

import unicodedata


def _strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def find_nodes(G: nx.Graph, term: str) -> list[str]:
    """Return node IDs matching the term — exact, prefix, substring."""
    t = _strip_diacritics(term).lower()
    exact, prefix, substring = [], [], []
    for nid, data in G.nodes(data=True):
        label = _strip_diacritics(data.get("label") or "").lower().rstrip("()")
        nid_l = nid.lower()
        if t == label or t == nid_l:
            exact.append(nid)
        elif label.startswith(t) or nid_l.startswith(t):
            prefix.append(nid)
        elif t in label:
            substring.append(nid)
    return exact + prefix + substring


def score_nodes(G: nx.Graph, terms: list[str]) -> list[tuple[float, str]]:
    scored = []
    norm_terms = [_strip_diacritics(t).lower() for t in terms]
    for nid, data in G.nodes(data=True):
        label = _strip_diacritics(data.get("label") or "").lower().rstrip("()")
        source = (data.get("source_file") or "").lower()
        score = 0.0
        for t in norm_terms:
            if t == label:
                score += 1000.0
            elif label.startswith(t):
                score += 100.0
            elif t in label:
                score += 1.0
            if t in source:
                score += 0.5
        if score > 0:
            scored.append((score, nid))
    return sorted(scored, reverse=True)


# ── BFS / DFS traversal ────────────────────────────────────────────────────────

def _hub_threshold(G: nx.Graph) -> int:
    degs = sorted(G.degree(n) for n in G.nodes())
    if not degs:
        return 50
    return max(50, degs[int(len(degs) * 0.99)])


def bfs(G: nx.Graph, starts: list[str], depth: int = 3) -> tuple[set[str], list[tuple]]:
    threshold = _hub_threshold(G)
    seed_set = set(starts)
    visited: set[str] = set(starts)
    frontier = set(starts)
    edges: list[tuple] = []
    for _ in range(depth):
        nxt: set[str] = set()
        for n in frontier:
            if n not in seed_set and G.degree(n) >= threshold:
                continue
            for nb in G.neighbors(n):
                if nb not in visited:
                    nxt.add(nb)
                    edges.append((n, nb))
        visited.update(nxt)
        frontier = nxt
    return visited, edges


def dfs(G: nx.Graph, starts: list[str], depth: int = 3) -> tuple[set[str], list[tuple]]:
    threshold = _hub_threshold(G)
    seed_set = set(starts)
    visited: set[str] = set()
    edges: list[tuple] = []
    stack = [(n, 0) for n in reversed(starts)]
    while stack:
        node, d = stack.pop()
        if node in visited or d > depth:
            continue
        visited.add(node)
        if node not in seed_set and G.degree(node) >= threshold:
            continue
        for nb in G.neighbors(node):
            if nb not in visited:
                stack.append((nb, d + 1))
                edges.append((node, nb))
    return visited, edges


# ── Result serialisation ───────────────────────────────────────────────────────

def node_to_dict(G: nx.Graph, nid: str) -> dict:
    data = dict(G.nodes[nid])
    data["id"] = nid
    data["degree"] = G.degree(nid)
    neighbors = []
    for nb in G.neighbors(nid):
        edge = G[nid][nb]
        if isinstance(edge, dict) and "relation" not in edge:
            edge = next(iter(edge.values()), {})
        neighbors.append({
            "id": nb,
            "label": G.nodes[nb].get("label", nb),
            "relation": edge.get("relation", ""),
            "confidence": edge.get("confidence", ""),
        })
    data["neighbors"] = neighbors
    return data


def subgraph_to_nodes(G: nx.Graph, node_ids: set[str], edges: list[tuple]) -> dict:
    nodes = [node_to_dict(G, nid) for nid in node_ids if nid in G]
    edge_list = []
    for u, v in edges:
        if u in G and v in G:
            ed = G[u][v]
            if isinstance(ed, dict) and "relation" not in ed:
                ed = next(iter(ed.values()), {})
            edge_list.append({
                "source": u,
                "source_label": G.nodes[u].get("label", u),
                "target": v,
                "target_label": G.nodes[v].get("label", v),
                "relation": ed.get("relation", ""),
                "confidence": ed.get("confidence", ""),
                "confidence_score": ed.get("confidence_score", 0),
            })
    return {"nodes": nodes, "edges": edge_list}


# ── High-level API functions ───────────────────────────────────────────────────

def query_graph(
    G: nx.Graph,
    question: str,
    mode: str = "bfs",
    depth: int = 3,
) -> dict:
    terms = [t for t in question.lower().split() if len(t) > 2]
    scored = score_nodes(G, terms)
    starts = [nid for _, nid in scored[:5]]
    if not starts:
        return {"nodes": [], "edges": [], "message": "No matching nodes found."}
    node_ids, edges = dfs(G, starts, depth) if mode == "dfs" else bfs(G, starts, depth)
    result = subgraph_to_nodes(G, node_ids, edges)
    result["query"] = question
    result["mode"] = mode
    result["start_nodes"] = [G.nodes[n].get("label", n) for n in starts]
    return result


def get_god_nodes(G: nx.Graph, top_n: int = 20) -> list[dict]:
    from graphify.analyze import god_nodes
    gods = god_nodes(G)
    out = []
    for entry in gods[:top_n]:
        nid = entry.get("id") or entry.get("node") or (entry[0] if isinstance(entry, (list, tuple)) else None)
        if nid and nid in G:
            d = dict(G.nodes[nid])
            d["id"] = nid
            d["degree"] = G.degree(nid)
            out.append(d)
    return out


def get_graph_stats(G: nx.Graph) -> dict:
    communities = communities_from_graph(G)
    degrees = [G.degree(n) for n in G.nodes()]
    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "community_count": len(communities),
        "avg_degree": round(sum(degrees) / max(len(degrees), 1), 2),
        "max_degree": max(degrees, default=0),
        "density": round(nx.density(G), 6),
        "is_connected": nx.is_weakly_connected(G) if G.is_directed() else nx.is_connected(G),
    }


def get_shortest_path(G: nx.Graph, node_a: str, node_b: str) -> dict:
    starts_a = find_nodes(G, node_a)
    starts_b = find_nodes(G, node_b)
    if not starts_a:
        return {"error": f"Node not found: {node_a}"}
    if not starts_b:
        return {"error": f"Node not found: {node_b}"}
    try:
        ug = G.to_undirected() if G.is_directed() else G
        path = nx.shortest_path(ug, starts_a[0], starts_b[0])
        return {
            "path": [{"id": n, "label": G.nodes[n].get("label", n)} for n in path],
            "length": len(path) - 1,
        }
    except nx.NetworkXNoPath:
        return {"error": f"No path between {node_a!r} and {node_b!r}"}
    except nx.NodeNotFound as exc:
        return {"error": str(exc)}


def get_surprising_connections(G: nx.Graph, top_n: int = 10) -> list[dict]:
    from graphify.analyze import surprising_connections
    communities = communities_from_graph(G)
    surprises = surprising_connections(G, communities)
    out = []
    for s in surprises[:top_n]:
        out.append({
            "source": s.get("source") or s.get("node_a", ""),
            "target": s.get("target") or s.get("node_b", ""),
            "source_label": s.get("source_label", ""),
            "target_label": s.get("target_label", ""),
            "relation": s.get("relation", ""),
            "confidence_score": s.get("confidence_score", 0),
            "explanation": s.get("explanation", ""),
        })
    return out


# ── LLM integration helpers ────────────────────────────────────────────────────

def graph_context_text(
    G: nx.Graph,
    node_ids: set[str],
    edges: list[tuple],
    token_budget: int = 2000,
    seeds: list[str] | None = None,
) -> str:
    """Render a subgraph as plain text for LLM context (mirrors serve._subgraph_to_text)."""
    from graphify.security import sanitize_label
    from graphify.build import edge_data as _edge_data

    char_budget = token_budget * 3
    lines: list[str] = []
    seed_set = set(seeds or [])
    ordered = [n for n in (seeds or []) if n in node_ids] + \
              sorted(node_ids - seed_set, key=lambda n: G.degree(n), reverse=True)

    for nid in ordered:
        d = G.nodes[nid]
        lines.append(
            f"NODE {sanitize_label(d.get('label', nid))} "
            f"[src={sanitize_label(str(d.get('source_file', '')))} "
            f"community={sanitize_label(str(d.get('community', '')))}]"
        )
    for u, v in edges:
        if u in node_ids and v in node_ids:
            raw = G[u][v]
            d = next(iter(raw.values()), {}) if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)) else raw
            lines.append(
                f"EDGE {sanitize_label(G.nodes[u].get('label', u))} "
                f"--{sanitize_label(str(d.get('relation', '')))}-> "
                f"{sanitize_label(G.nodes[v].get('label', v))} "
                f"[{sanitize_label(str(d.get('confidence', '')))}]"
            )

    output = "\n".join(lines)
    if len(output) > char_budget:
        output = output[:char_budget] + f"\n... (truncated)"
    return output


def llm_ask(prompt: str, backend: str = LLM_BACKEND, max_tokens: int = 1024) -> str:
    """Call the configured LLM backend with a plain-text prompt and return the reply."""
    try:
        from graphify.llm import _call_llm
        return _call_llm(prompt, backend=backend, max_tokens=max_tokens)
    except Exception as exc:
        return f"[LLM error: {exc}]"


def llm_query_answer(
    G: nx.Graph,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 3,
    backend: str = LLM_BACKEND,
) -> dict:
    """BFS/DFS to find relevant subgraph, then call LLM to answer the question."""
    terms = [t.lower() for t in question.split() if len(t) > 2]
    scored = score_nodes(G, terms)
    start_nodes = [nid for _, nid in scored[:3]]
    if not start_nodes:
        return {"answer": "No relevant nodes found in the graph.", "context_nodes": 0, "backend": backend}

    node_ids, edges = dfs(G, start_nodes, depth) if mode == "dfs" else bfs(G, start_nodes, depth)
    context = graph_context_text(G, node_ids, edges, token_budget=2000, seeds=start_nodes)

    prompt = (
        f"You are a code architecture expert. Using the knowledge graph context below, "
        f"answer the question concisely and precisely.\n\n"
        f"QUESTION: {question}\n\n"
        f"GRAPH CONTEXT:\n{context}\n\n"
        f"ANSWER:"
    )
    answer = llm_ask(prompt, backend=backend, max_tokens=800)
    return {
        "question": question,
        "answer": answer,
        "context_nodes": len(node_ids),
        "context_edges": len(edges),
        "backend": backend,
        "mode": mode,
        "depth": depth,
    }


def llm_explain_node(G: nx.Graph, node_id: str, backend: str = LLM_BACKEND) -> dict:
    """Explain a node and its neighborhood in plain language using the LLM."""
    if node_id not in G:
        return {"error": f"Node {node_id!r} not found"}

    d = G.nodes[node_id]
    label = d.get("label", node_id)
    source_file = d.get("source_file", "")
    community = d.get("community", "")

    # Collect immediate neighbors
    neighbors_out = [(nb, G[node_id][nb] if not isinstance(G, (nx.MultiGraph, nx.MultiDiGraph))
                      else next(iter(G[node_id][nb].values()), {}))
                     for nb in G.successors(node_id)]
    neighbors_in = [(nb, G[nb][node_id] if not isinstance(G, (nx.MultiGraph, nx.MultiDiGraph))
                     else next(iter(G[nb][node_id].values()), {}))
                    for nb in G.predecessors(node_id)]

    conn_lines = []
    for nb, edata in (neighbors_out + neighbors_in)[:30]:
        nb_label = G.nodes[nb].get("label", nb)
        rel = edata.get("relation", "relates_to")
        direction = "calls/uses" if nb in G.successors(node_id) else "used_by"
        conn_lines.append(f"  - {direction} {nb_label!r} via {rel} ({edata.get('confidence', '')})")

    conn_text = "\n".join(conn_lines) if conn_lines else "  (no connections)"

    prompt = (
        f"You are a senior engineer reviewing a codebase knowledge graph. "
        f"Explain what the following node does, its role in the system, and why it matters.\n\n"
        f"NODE: {label}\n"
        f"FILE: {source_file}\n"
        f"COMMUNITY (module cluster): {community}\n"
        f"DEGREE: {G.degree(node_id)} connections\n\n"
        f"CONNECTIONS:\n{conn_text}\n\n"
        f"Write a concise paragraph (3-5 sentences) explaining this component's purpose, "
        f"what it depends on, and what depends on it."
    )
    explanation = llm_ask(prompt, backend=backend, max_tokens=400)
    return {
        "node_id": node_id,
        "label": label,
        "source_file": source_file,
        "community": community,
        "degree": G.degree(node_id),
        "explanation": explanation,
        "backend": backend,
    }


def llm_label_communities(
    G: nx.Graph,
    communities: dict[int, list[str]],
    backend: str = LLM_BACKEND,
) -> dict[int, str]:
    """Use LLM to generate human-readable names for each community."""
    labels: dict[int, str] = {}

    for cid, members in sorted(communities.items(), key=lambda x: -len(x[1])):
        # Pick top members by degree for the prompt
        top = sorted(members, key=lambda n: G.degree(n), reverse=True)[:10]
        member_labels = [G.nodes[n].get("label", n) for n in top]
        files = list({G.nodes[n].get("source_file", "") for n in top if G.nodes[n].get("source_file")})[:5]

        prompt = (
            f"You are naming a software module cluster. Based on its top members, "
            f"suggest a short, precise name (3-5 words max) that describes what this cluster does.\n\n"
            f"TOP MEMBERS: {', '.join(member_labels)}\n"
            f"SOURCE FILES: {', '.join(files)}\n\n"
            f"Respond with ONLY the cluster name, nothing else."
        )
        name = llm_ask(prompt, backend=backend, max_tokens=30).strip().strip('"').strip("'")
        labels[cid] = name or f"Community {cid}"

    return labels


def llm_architecture_summary(G: nx.Graph, backend: str = LLM_BACKEND) -> dict:
    """Generate an executive-level architecture summary using the LLM."""
    stats = get_graph_stats(G)
    gods = get_god_nodes(G, top_n=10)
    surprises = get_surprising_connections(G, top_n=5)
    communities = communities_from_graph(G)

    gods_text = "\n".join(
        f"  - {g.get('label', g.get('id', '?'))} (degree {g.get('degree', 0)}, "
        f"file: {g.get('source_file', '')})"
        for g in gods[:10]
    )
    surprises_text = "\n".join(
        f"  - {s['source_label'] or s['source']} ↔ {s['target_label'] or s['target']} "
        f"({s['relation']}) — {s['explanation']}"
        for s in surprises
    )

    # Sample community sizes
    community_sizes = sorted([(cid, len(m)) for cid, m in communities.items()], key=lambda x: -x[1])[:8]
    comm_text = "\n".join(f"  - Community {cid}: {sz} nodes" for cid, sz in community_sizes)

    prompt = (
        f"You are a principal architect reviewing a codebase knowledge graph. "
        f"Write a concise executive summary of the architecture.\n\n"
        f"GRAPH STATISTICS:\n"
        f"  - {stats['node_count']} nodes, {stats['edge_count']} edges\n"
        f"  - {stats['community_count']} communities (modules)\n"
        f"  - avg degree: {stats['avg_degree']}, max degree: {stats['max_degree']}\n\n"
        f"MOST CRITICAL COMPONENTS (god nodes):\n{gods_text}\n\n"
        f"SURPRISING CROSS-MODULE CONNECTIONS:\n{surprises_text or '  (none)'}\n\n"
        f"LARGEST COMMUNITY CLUSTERS:\n{comm_text}\n\n"
        f"Write 4-6 sentences covering: overall structure, key components, potential risks "
        f"(high-degree hub nodes, cross-community coupling), and notable patterns."
    )

    summary = llm_ask(prompt, backend=backend, max_tokens=600)
    return {
        "summary": summary,
        "stats": stats,
        "god_nodes_count": len(gods),
        "surprising_connections_count": len(surprises),
        "backend": backend,
    }
