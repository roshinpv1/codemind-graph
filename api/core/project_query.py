"""Cross-graph project Q&A — PKB-first retrieval with structured persona responses."""
from __future__ import annotations

import json
from typing import Any

import networkx as nx

from api.config import LLM_BACKEND
from api.core import database, engine, storage
from api.core.cross_graph import loadable_graphs
from api.core.intent_router import classify_intent, SCENARIO_PACKS
from api.core.pkb_storage import load_pkb, append_memory
from api.core.graph_context import blast_radius_for_question
from api.core.product_ontology import (
    enrich_pkb,
    get_briefing_user,
    build_answer_card,
    compute_retrieval_quality,
    technical_proof,
    repository_role_label,
)

PERSONAS: dict[str, dict[str, str]] = {
    "developer": {
        "label": "Developer",
        "instruction": (
            "Focus on implementation: APIs, handlers, call chains, dependencies. "
            "Include where_to_look with files and symbols from evidence."
        ),
    },
    "architect": {
        "label": "Architect",
        "instruction": "Focus on structure, coupling, hubs, and cross-module risks.",
    },
    "security": {
        "label": "Security",
        "instruction": "Focus on trust boundaries, auth, exposure, and untested sensitive paths.",
    },
    "qa": {
        "label": "QA / Test",
        "instruction": "Focus on entry points, coverage gaps, and test prioritization.",
    },
    "executive": {
        "label": "Executive",
        "instruction": "Concise non-jargon summary with headline, health, top risks only.",
    },
    "onboarding": {
        "label": "Onboarding",
        "instruction": "Orient a new hire: start_here paths, key modules, learning order.",
    },
}

DEFAULT_PERSONA = "developer"


def list_personas() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in PERSONAS.items()]


def _pkb_context_sections(pkb: dict[str, Any], sections: list[str], char_budget: int = 4000) -> str:
    pkb = enrich_pkb(pkb) or pkb
    parts: list[str] = []
    if "dna" in sections and pkb.get("dna"):
        d = pkb["dna"]
        parts.append(f"## Product overview\n{d.get('headline', '')}\n{d.get('summary', '')}")
    if "metrics" in sections and pkb.get("health_summary"):
        hs = pkb["health_summary"]
        parts.append(
            "## Health\n"
            f"- Status: {hs.get('status_label')}\n"
            f"- Capabilities tested: {hs.get('capabilities_tested_pct')}%\n"
            f"- Untested capabilities: {hs.get('capabilities_untested')}\n"
            f"- Open findings: {hs.get('open_findings')}"
        )
    if "risks" in sections and pkb.get("findings"):
        lines = [
            f"- [{f.get('severity_label', f.get('severity'))}] {f['title']}: {f.get('why_it_matters', '')}"
            for f in pkb["findings"][:12]
        ]
        parts.append("## Findings\n" + "\n".join(lines))
    if "capabilities" in sections:
        caps = pkb.get("capabilities_ui") or []
        lines = [
            f"- {c['name']} — {c.get('test_status', '')} ({c.get('source_file', '')})"
            for c in caps[:15]
        ]
        parts.append("## Capabilities\n" + "\n".join(lines))
    if "subsystems" in sections and pkb.get("areas"):
        lines = [
            f"- {a['name']} ({a.get('component_count', 0)} components, centerpiece: {a.get('centerpiece', '')})"
            for a in pkb["areas"][:10]
        ]
        parts.append("## Product areas\n" + "\n".join(lines))
    if "flows" in sections and pkb.get("journeys"):
        lines = [f"- {j['name']}: {j.get('summary', '')} [{j.get('test_status', '')}]" for j in pkb["journeys"][:8]]
        parts.append("## User journeys\n" + "\n".join(lines))
    if "module_briefs" in sections and pkb.get("module_briefs"):
        brief_lines: list[str] = []
        for key, text_b in list(pkb["module_briefs"].items())[:10]:
            area = key.split(":")[-1] if ":" in key else key
            brief_lines.append(f"- **{area}**: {(text_b or '')[:300]}")
        if brief_lines:
            parts.append("## Module briefs\n" + "\n".join(brief_lines))
    if "hubs" in sections:
        hub_findings = [
            f for f in pkb.get("findings", [])
            if f.get("category_key") == "hub"
        ][:10]
        if hub_findings:
            lines = [
                f"- {f['title']}: {f.get('why_it_matters', '')}"
                for f in hub_findings
            ]
            parts.append("## Architectural hubs (findings)\n" + "\n".join(lines))
    if "decisions" in sections and pkb.get("decisions"):
        lines = [
            f"- [{d.get('kind', 'DECISION')}] {d.get('title', '')} ({d.get('source_file', '')})"
            for d in pkb["decisions"][:12]
        ]
        parts.append("## Documented decisions\n" + "\n".join(lines))
    text = "\n\n".join(parts)
    if len(text) > char_budget:
        return text[:char_budget] + "\n...(truncated)"
    return text


def _graph_context_block(
    G: nx.Graph,
    question: str,
    *,
    mode: str,
    depth: int,
    header: str,
    char_budget: int = 800,
) -> tuple[str, list[dict]]:
    terms = [t.lower() for t in question.split() if len(t) > 2]
    scored = engine.score_nodes(G, terms)
    starts = [nid for _, nid in scored[:3]]
    if not starts:
        return "", []
    node_ids, edges = (
        engine.dfs(G, starts, depth) if mode == "dfs" else engine.bfs(G, starts, depth)
    )
    body = engine.graph_context_text(
        G, node_ids, edges, token_budget=max(200, char_budget // 3), seeds=starts
    )
    evidence = [
        {"node_id": n, "label": G.nodes[n].get("label", n), "source_file": G.nodes[n].get("source_file", "")}
        for n in starts if n in G
    ]
    if not body.strip():
        return "", evidence
    return f"### Graph slice: {header}\n{body}", evidence


def project_search(
    project_id: str,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 3,
    roles: list[str] | None = None,
    top_n: int = 8,
) -> dict[str, Any]:
    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    if roles:
        role_set = {r.lower() for r in roles}
        loadable = [g for g in loadable if (g["graph_role"] or "source").lower() in role_set]
    if not loadable:
        return {
            "project_id": project_id,
            "query": question,
            "nodes": [],
            "message": "No ready graphs in this project.",
        }
    terms = [t.lower() for t in question.split() if len(t) > 2]
    hits: list[dict[str, Any]] = []
    for gmeta in loadable:
        G = engine.load_graph(gmeta["id"])
        for score, nid in engine.score_nodes(G, terms)[:top_n]:
            if score <= 0:
                continue
            d = G.nodes[nid]
            hits.append({
                "id": nid,
                "label": d.get("label", nid),
                "source_file": d.get("source_file", ""),
                "degree": G.degree(nid),
                "score": round(score, 2),
                "graph_id": gmeta["id"],
                "graph_name": gmeta["name"],
                "graph_role": gmeta["graph_role"] or "source",
            })
    hits.sort(key=lambda x: -x["score"])
    return {
        "project_id": project_id,
        "query": question,
        "graphs_searched": len(loadable),
        "nodes": hits[: top_n * 2],
        "message": None if hits else "No matching nodes found.",
    }


def _structure_for_persona(persona: str, answer: str, pkb: dict, evidence: list) -> dict[str, Any]:
    """Wrap LLM answer in persona-shaped structured fields."""
    base = {
        "answer": answer,
        "evidence": evidence[:15],
    }
    if persona == "executive":
        dna = pkb.get("dna", {})
        metrics = pkb.get("metrics", {})
        return {
            **base,
            "headline": dna.get("headline", answer.split(".")[0][:120]),
            "health": metrics.get("health", "unknown"),
            "top_risks": [r["title"] for r in pkb.get("risks", [])[:3]],
        }
    if persona == "onboarding":
        flows = pkb.get("flows", [])[:5]
        return {
            **base,
            "start_here": [f["name"] for f in flows] or [s["name"] for s in pkb.get("subsystems", [])[:5]],
            "key_modules": [s["name"] for s in pkb.get("subsystems", [])[:6]],
        }
    if persona == "qa":
        gaps = [c for c in pkb.get("capabilities", []) if not c.get("covered")][:8]
        return {
            **base,
            "untested_capabilities": [
                {"label": c["label"], "source_file": c.get("source_file"), "risk": c.get("risk")}
                for c in gaps
            ],
            "coverage_pct": pkb.get("metrics", {}).get("functional_coverage_pct"),
        }
    if persona == "developer":
        return {
            **base,
            "where_to_look": [
                {"file": e.get("source_file"), "label": e.get("label"), "node_id": e.get("node_id")}
                for e in evidence[:8]
                if e.get("source_file") or e.get("label")
            ],
        }
    if persona == "architect":
        return {
            **base,
            "structural_concerns": [
                {"title": r["title"], "severity": r["severity"], "category": r.get("category")}
                for r in pkb.get("risks", [])[:6]
            ],
        }
    return base


def project_ask(
    project_id: str,
    question: str,
    *,
    persona: str = DEFAULT_PERSONA,
    mode: str = "bfs",
    depth: int = 3,
    roles: list[str] | None = None,
    backend: str = LLM_BACKEND,
    save_memory: bool = True,
) -> dict[str, Any]:
    row = database.get_project(project_id)
    if not row:
        raise ValueError(f"Project {project_id!r} not found")

    persona = persona.lower() if persona else DEFAULT_PERSONA
    if persona not in PERSONAS:
        persona = DEFAULT_PERSONA

    routing = classify_intent(question)
    pkb = enrich_pkb(load_pkb(project_id))

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    if roles:
        role_set = {r.lower() for r in roles}
        loadable = [g for g in loadable if (g["graph_role"] or "source").lower() in role_set]

    if not loadable and not pkb:
        return {
            "project_id": project_id,
            "question": question,
            "persona": persona,
            "intent": routing["intent"],
            "answer": "No repositories are ready yet. Add your production codebase and refresh project understanding.",
            "answer_card": {"summary": "No repositories are ready yet.", "confidence": "low"},
            "structured": {"answer": "No data yet."},
            "context_nodes": 0,
            "sources": [],
            "backend": backend,
            "pkb_available": False,
        }

    context_parts: list[str] = []
    all_evidence: list[dict] = []
    sources: list[dict] = []

    if pkb:
        sections = routing["pkb_sections"]
        pkb_text = _pkb_context_sections(pkb, sections)
        if pkb_text:
            context_parts.append(pkb_text)

    depth = min(max(depth, 1), 6)
<<<<<<< Updated upstream
    per_graph = max(400, 1200 // max(len(loadable), 1))
    for gmeta in loadable[:4]:
=======
    per_graph = max(400, 1200 // max(len(structural), 1))
    use_hub_blast = routing["intent"] in ("blast_radius", "architecture", "risk")
    for gmeta in structural[:4]:
>>>>>>> Stashed changes
        G = engine.load_graph(gmeta["id"])
        role = gmeta["graph_role"] or "source"
        if use_hub_blast:
            hub_block, hub_ev = blast_radius_for_question(G, question, depth=depth)
            if hub_block:
                context_parts.append(
                    f"### {gmeta['name']} — {repository_role_label(role)}\n{hub_block}"
                )
                for e in hub_ev:
                    e = dict(e)
                    e["graph_id"] = gmeta["id"]
                    e["graph_name"] = gmeta["name"]
                    e["graph_role"] = role
                    all_evidence.append(e)
        block, ev = _graph_context_block(
            G, question, mode=mode, depth=depth,
            header=f"{gmeta['name']} — {repository_role_label(role)}",
            char_budget=per_graph,
        )
        if block:
            context_parts.append(block)
            for e in ev:
                e["graph_id"] = gmeta["id"]
                e["graph_name"] = gmeta["name"]
                e["graph_role"] = role
            all_evidence.extend(ev)
            sources.append({
                "graph_id": gmeta["id"],
                "graph_name": gmeta["name"],
                "graph_role": role,
                "context_nodes": len(ev),
            })

    if not context_parts:
        return {
            "project_id": project_id,
            "question": question,
            "persona": persona,
            "intent": routing["intent"],
            "answer": "No relevant context found. Try rephrasing or run POST /projects/{id}/synthesize.",
            "structured": {"answer": "No context."},
            "context_nodes": 0,
            "sources": [],
            "backend": backend,
            "pkb_available": bool(pkb),
        }

    persona_info = PERSONAS[persona]
    context = "\n\n".join(context_parts)
    prompt = (
        f'Project: "{row["name"]}"\n'
        f"Persona: {persona_info['label']}\n"
        f"{persona_info['instruction']}\n"
        f"Intent detected: {routing['intent']}\n\n"
        "Use ONLY the product intelligence below. "
        "Speak in terms of capabilities, product areas, findings, and user journeys — "
        "never say graph, node, community, entry point, PKB, or BFS. "
        "If the context does not support a specific call chain or file list, say what is unknown "
        "rather than inventing paths.\n\n"
        f"QUESTION: {question}\n\n"
        f"CONTEXT:\n{context}\n\n"
        "ANSWER:"
    )
    answer = engine.llm_ask(prompt, backend=backend, max_tokens=1000)
    retrieval = compute_retrieval_quality(
        pkb, all_evidence, routing["intent"], bool(context_parts)
    )
    confidence = retrieval["confidence"]
    answer_card = build_answer_card(
        answer, persona, pkb, all_evidence,
        confidence=confidence,
        retrieval_quality=retrieval,
    )
    structured = _structure_for_persona(persona, answer, pkb or {}, all_evidence)
    proof = technical_proof(all_evidence, sources)

    if save_memory and answer and not answer.startswith("[LLM error"):
        append_memory(project_id, question, answer, persona=persona, evidence=all_evidence[:10])

    return {
        "project_id": project_id,
        "project_name": row["name"],
        "question": question,
        "persona": persona,
        "persona_label": persona_info["label"],
        "lens": persona_info["label"],
        "intent": routing["intent"],
        "answer": answer,
        "answer_card": answer_card,
        "retrieval_quality": retrieval,
        "technical_proof": proof,
        "structured": structured,
        "understanding_ready": bool(pkb),
        "context_nodes": len(all_evidence),
        "sources": sources,
        "backend": backend,
        "mode": mode,
        "depth": depth,
        "pkb_available": bool(pkb),
    }


def get_briefing(project_id: str) -> dict[str, Any]:
    return get_briefing_user(project_id)


def list_scenarios() -> dict[str, Any]:
    return {"scenarios": SCENARIO_PACKS}
