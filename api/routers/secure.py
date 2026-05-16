"""CodeMind Secure — graph-based security intelligence: vulnerability propagation & attack paths."""
from __future__ import annotations

import networkx as nx
from fastapi import APIRouter, HTTPException

from api.core import engine, database

router = APIRouter(prefix="/graphs/{graph_id}/security", tags=["Secure"])

_AUTH_KEYWORDS = frozenset({"auth", "authenticate", "login", "token", "jwt", "session", "password", "oauth", "permission", "role", "acl", "authorize"})
_SECRET_KEYWORDS = frozenset({"secret", "key", "api_key", "apikey", "credential", "password", "token", "private_key"})
_SENSITIVE_KEYWORDS = frozenset({"pii", "ssn", "credit", "card", "email", "phone", "address", "dob", "user_data", "personal"})


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")


def _label_contains(G, nid: str, keywords: frozenset) -> bool:
    label = (G.nodes[nid].get("label") or "").lower()
    return any(kw in label for kw in keywords)


@router.get("/auth-flows", response_model=list[dict], summary="All authentication/authorization paths")
def auth_flows(graph_id: str):
    """Identify nodes participating in auth/login/token flows."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    auth_nodes = [nid for nid in G.nodes() if _label_contains(G, nid, _AUTH_KEYWORDS)]
    result = []
    for nid in auth_nodes[:50]:
        node_ids, edges = engine.bfs(G, [nid], depth=2)
        result.append({
            "auth_node": nid,
            "auth_label": G.nodes[nid].get("label", nid),
            "source_file": G.nodes[nid].get("source_file", ""),
            "connected_nodes": [
                {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
                for n in node_ids if n != nid
            ][:10],
        })
    return result


@router.get("/trust-boundaries", response_model=list[dict], summary="Privilege boundary crossing edges")
def trust_boundaries(graph_id: str):
    """Edges that cross between auth-sensitive and non-sensitive nodes — potential privilege escalation."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    auth_set = {nid for nid in G.nodes() if _label_contains(G, nid, _AUTH_KEYWORDS)}
    violations = []
    for u, v, data in G.edges(data=True):
        u_is_auth = u in auth_set
        v_is_auth = v in auth_set
        if u_is_auth != v_is_auth:
            violations.append({
                "source": u,
                "source_label": G.nodes[u].get("label", u),
                "source_is_auth": u_is_auth,
                "target": v,
                "target_label": G.nodes[v].get("label", v),
                "target_is_auth": v_is_auth,
                "relation": data.get("relation", ""),
                "risk": "auth → public" if u_is_auth else "public → auth",
            })
    return violations[:100]


@router.get("/attack-paths", response_model=dict, summary="BFS attack paths from entry to sensitive target")
def attack_paths(graph_id: str, target: str, max_depth: int = 4):
    """
    Find paths from any public-facing node to a sensitive target.
    target: node label or ID to find attack paths toward.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    target_nodes = engine.find_nodes(G, target)
    if not target_nodes:
        return {"target": target, "paths": [], "message": "Target node not found"}

    # Entry points: nodes with no inbound edges (public API surface)
    if G.is_directed():
        entry_nodes = [n for n in G.nodes() if G.in_degree(n) == 0][:20]
    else:
        entry_nodes = []

    paths = []
    for entry in entry_nodes[:5]:
        for tgt in target_nodes[:3]:
            try:
                ug = G.to_undirected() if G.is_directed() else G
                path = nx.shortest_path(ug, entry, tgt)
                if len(path) <= max_depth + 1:
                    paths.append({
                        "entry": entry,
                        "entry_label": G.nodes[entry].get("label", entry),
                        "target": tgt,
                        "target_label": G.nodes[tgt].get("label", tgt),
                        "path": [{"id": n, "label": G.nodes[n].get("label", n)} for n in path],
                        "hops": len(path) - 1,
                    })
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

    return {
        "target": target,
        "target_nodes_found": [{"id": n, "label": G.nodes[n].get("label", n)} for n in target_nodes[:5]],
        "paths": sorted(paths, key=lambda x: x["hops"])[:20],
    }


@router.get("/secret-exposure", response_model=list[dict], summary="Where secrets/credentials flow in the graph")
def secret_exposure(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    secret_nodes = [nid for nid in G.nodes() if _label_contains(G, nid, _SECRET_KEYWORDS)]
    result = []
    for nid in secret_nodes[:30]:
        node_ids, edges = engine.bfs(G, [nid], depth=3)
        node_ids.discard(nid)
        result.append({
            "secret_node": nid,
            "secret_label": G.nodes[nid].get("label", nid),
            "source_file": G.nodes[nid].get("source_file", ""),
            "propagates_to": [
                {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
                for n in list(node_ids)[:10]
            ],
            "exposure_count": len(node_ids),
        })
    return sorted(result, key=lambda x: x["exposure_count"], reverse=True)


@router.get("/cve-impact", response_model=dict, summary="Trace CVE impact through dependency graph")
def cve_impact(graph_id: str, package: str, depth: int = 4):
    """
    Given a vulnerable package name, find all nodes that (transitively) depend on it.
    This is a graph-propagation proxy for CVE impact analysis.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, package)
    if not matches:
        return {"package": package, "impacted_nodes": [], "message": "Package not found in graph"}
    pkg_node = matches[0]
    rev = G.reverse() if G.is_directed() else G
    node_ids, edges = engine.bfs(rev, [pkg_node], depth)
    node_ids.discard(pkg_node)
    impacted = [
        {"id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
        for n in node_ids if n in G
    ]
    return {
        "package": package,
        "package_node": {"id": pkg_node, "label": G.nodes[pkg_node].get("label", pkg_node)},
        "impacted_node_count": len(impacted),
        "depth_searched": depth,
        "impacted_nodes": impacted[:100],
    }


@router.get("/report", response_model=dict, summary="Full security analysis report (add ?narrative=true for LLM risk narrative)")
def security_report(graph_id: str, narrative: bool = False, backend: str | None = None):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    auth_count = sum(1 for n in G.nodes() if _label_contains(G, n, _AUTH_KEYWORDS))
    secret_count = sum(1 for n in G.nodes() if _label_contains(G, n, _SECRET_KEYWORDS))
    auth_set = {n for n in G.nodes() if _label_contains(G, n, _AUTH_KEYWORDS)}
    boundary_crossings = sum(1 for u, v in G.edges() if (u in auth_set) != (v in auth_set))
    risk_level = "high" if boundary_crossings > 10 else "medium" if boundary_crossings > 3 else "low"
    recommendations = [
        *(["Review trust boundary crossings — auth ↔ public edges detected"] if boundary_crossings > 0 else []),
        *(["High number of secret-related nodes — verify credential handling"] if secret_count > 5 else []),
    ]
    result = {
        "graph_id": graph_id,
        "summary": {
            "total_nodes": G.number_of_nodes(),
            "auth_related_nodes": auth_count,
            "secret_related_nodes": secret_count,
            "trust_boundary_crossings": boundary_crossings,
        },
        "risk_level": risk_level,
        "recommendations": recommendations,
    }
    if narrative:
        from api.config import LLM_BACKEND
        prompt = (
            f"You are a security architect. Write a concise security risk narrative for this codebase.\n\n"
            f"METRICS:\n"
            f"  - Total nodes: {G.number_of_nodes()}\n"
            f"  - Auth-related nodes: {auth_count}\n"
            f"  - Secret-related nodes: {secret_count}\n"
            f"  - Trust boundary crossings: {boundary_crossings}\n"
            f"  - Overall risk level: {risk_level}\n\n"
            f"RECOMMENDATIONS: {'; '.join(recommendations) or 'None'}\n\n"
            f"Write 3-5 sentences summarising security posture, key risks, and immediate remediation priorities."
        )
        result["narrative"] = engine.llm_ask(prompt, backend=backend or LLM_BACKEND, max_tokens=400)
    return result
