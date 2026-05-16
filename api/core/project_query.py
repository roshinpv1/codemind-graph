"""Cross-graph project Q&A — search and LLM answers across all ready project graphs."""
from __future__ import annotations

from typing import Any

import networkx as nx

from api.config import LLM_BACKEND
from api.core import database, engine, storage

PERSONAS: dict[str, dict[str, str]] = {
    "developer": {
        "label": "Developer",
        "instruction": (
            "Focus on implementation: APIs, handlers, call chains, dependencies, and "
            "where to change code. Be concrete with file and symbol names from the context."
        ),
    },
    "architect": {
        "label": "Architect",
        "instruction": (
            "Focus on structure: modules, communities, coupling, hub components, and "
            "cross-cutting concerns. Highlight risks from high-degree nodes and surprising edges."
        ),
    },
    "security": {
        "label": "Security",
        "instruction": (
            "Focus on trust boundaries, authentication flows, sensitive data paths, secrets, "
            "and external exposure. Flag risky patterns even if the question is general."
        ),
    },
    "qa": {
        "label": "QA / Test",
        "instruction": (
            "Focus on testability: entry points, coverage gaps, test-to-feature mapping, and "
            "what is or is not exercised. Relate test-repo context to production source when both exist."
        ),
    },
    "executive": {
        "label": "Executive",
        "instruction": (
            "Give a concise, non-jargon summary suitable for leadership: scope, major subsystems, "
            "risks, and delivery implications. Avoid deep implementation detail unless asked."
        ),
    },
    "onboarding": {
        "label": "Onboarding",
        "instruction": (
            "Help a new team member: orient them to main areas, critical flows, and where to "
            "start reading code. Suggest a learning path using components named in the context."
        ),
    },
}

DEFAULT_PERSONA = "developer"


def list_personas() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in PERSONAS.items()]


def _load_project_graphs(
    project_id: str,
    roles: list[str] | None = None,
) -> list[dict[str, Any]]:
    graphs = database.get_project_graphs(project_id)
    loadable = [
        g for g in graphs
        if g["status"] == "ready" and storage.graph_exists(g["id"])
    ]
    if roles:
        role_set = {r.lower() for r in roles}
        loadable = [g for g in loadable if (g["graph_role"] or "source").lower() in role_set]
    return loadable


def _graph_context_block(
    G: nx.Graph,
    question: str,
    *,
    mode: str,
    depth: int,
    top_starts: int,
    char_budget: int,
    header: str,
) -> tuple[str, set[str], list[tuple], list[str]]:
    terms = [t.lower() for t in question.split() if len(t) > 2]
    scored = engine.score_nodes(G, terms)
    starts = [nid for _, nid in scored[:top_starts]]
    if not starts:
        return "", set(), [], []

    node_ids, edges = (
        engine.dfs(G, starts, depth) if mode == "dfs" else engine.bfs(G, starts, depth)
    )
    body = engine.graph_context_text(
        G, node_ids, edges, token_budget=max(200, char_budget // 3), seeds=starts
    )
    if not body.strip():
        return "", node_ids, edges, starts
    return f"### {header}\n{body}", node_ids, edges, starts


def project_search(
    project_id: str,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 3,
    roles: list[str] | None = None,
    top_n: int = 8,
) -> dict[str, Any]:
    """Ranked nodes across all project graphs (no LLM)."""
    graphs = _load_project_graphs(project_id, roles)
    if not graphs:
        return {
            "project_id": project_id,
            "query": question,
            "nodes": [],
            "message": "No ready graphs in this project. Ingest at least one repository first.",
        }

    terms = [t.lower() for t in question.split() if len(t) > 2]
    hits: list[dict[str, Any]] = []

    for gmeta in graphs:
        G = engine.load_graph(gmeta["id"])
        scored = engine.score_nodes(G, terms)
        role = gmeta["graph_role"] or "source"
        for score, nid in scored[:top_n]:
            if score <= 0:
                continue
            data = dict(G.nodes[nid])
            hits.append({
                "id": nid,
                "label": data.get("label", nid),
                "source_file": data.get("source_file", ""),
                "community": data.get("community"),
                "degree": G.degree(nid),
                "score": round(score, 2),
                "graph_id": gmeta["id"],
                "graph_name": gmeta["name"],
                "graph_role": role,
            })

    hits.sort(key=lambda x: -x["score"])
    hits = hits[: top_n * 2]

    return {
        "project_id": project_id,
        "query": question,
        "graphs_searched": len(graphs),
        "nodes": hits,
        "message": None if hits else "No matching nodes found across project graphs.",
    }


def project_ask(
    project_id: str,
    question: str,
    *,
    persona: str = DEFAULT_PERSONA,
    mode: str = "bfs",
    depth: int = 3,
    roles: list[str] | None = None,
    backend: str = LLM_BACKEND,
) -> dict[str, Any]:
    """LLM answer using merged subgraph context from all ready project graphs."""
    row = database.get_project(project_id)
    if not row:
        raise ValueError(f"Project {project_id!r} not found")

    persona = persona.lower() if persona else DEFAULT_PERSONA
    if persona not in PERSONAS:
        persona = DEFAULT_PERSONA

    graphs = _load_project_graphs(project_id, roles)
    if not graphs:
        return {
            "project_id": project_id,
            "question": question,
            "persona": persona,
            "answer": (
                "No indexed repositories are ready in this project yet. "
                "Ingest source (and optionally test/CI/CD) graphs, then try again."
            ),
            "context_nodes": 0,
            "sources": [],
            "backend": backend,
        }

    depth = min(max(depth, 1), 6)
    blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    total_nodes = 0
    per_graph_budget = max(600, 3200 // max(len(graphs), 1))

    for gmeta in graphs:
        G = engine.load_graph(gmeta["id"])
        role = gmeta["graph_role"] or "source"
        header = f"{gmeta['name']} (role={role})"
        block, node_ids, edges, starts = _graph_context_block(
            G,
            question,
            mode=mode,
            depth=depth,
            top_starts=3,
            char_budget=per_graph_budget,
            header=header,
        )
        if block:
            blocks.append(block)
            total_nodes += len(node_ids)
            sources.append({
                "graph_id": gmeta["id"],
                "graph_name": gmeta["name"],
                "graph_role": role,
                "context_nodes": len(node_ids),
                "start_labels": [G.nodes[n].get("label", n) for n in starts[:5]],
            })

    if not blocks:
        return {
            "project_id": project_id,
            "question": question,
            "persona": persona,
            "answer": "No relevant components found in the project knowledge graphs for this question.",
            "context_nodes": 0,
            "sources": [],
            "backend": backend,
        }

    persona_info = PERSONAS[persona]
    context = "\n\n".join(blocks)
    prompt = (
        f'You are answering questions about the software project "{row["name"]}".\n'
        f"Audience persona: {persona_info['label']}.\n"
        f"{persona_info['instruction']}\n\n"
        "Use ONLY the knowledge graph context below (from one or more repositories). "
        "When multiple roles are present (source, test, ci, cd), relate them explicitly. "
        "If the context is insufficient, say what is missing.\n\n"
        f"QUESTION: {question}\n\n"
        f"PROJECT GRAPH CONTEXT:\n{context}\n\n"
        "ANSWER:"
    )
    answer = engine.llm_ask(prompt, backend=backend, max_tokens=1000)

    return {
        "project_id": project_id,
        "project_name": row["name"],
        "question": question,
        "persona": persona,
        "persona_label": persona_info["label"],
        "answer": answer,
        "context_nodes": total_nodes,
        "graphs_used": len(sources),
        "sources": sources,
        "backend": backend,
        "mode": mode,
        "depth": depth,
    }
