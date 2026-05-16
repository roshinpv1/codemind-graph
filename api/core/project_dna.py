"""Code Project DNA — full AI narrative summary (run separately from PKB refresh)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.config import LLM_BACKEND
from api.core import database, engine
from api.core.cross_graph import loadable_graphs
from api.core.pkb_storage import load_pkb, save_pkb
from api.core.product_ontology import enrich_pkb


def _pkb_context_block(pkb: dict[str, Any]) -> str:
    lines: list[str] = []
    m = pkb.get("metrics", {})
    lines.append(
        f"Metrics: {m.get('graphs_ready', 0)} repositories, "
        f"{m.get('total_nodes', 0)} components, {m.get('functional_coverage_pct', 0)}% capabilities tested, "
        f"grade {m.get('coverage_grade', '?')}, health {m.get('health', 'unknown')}, "
        f"{m.get('risk_count', 0)} structural risks, {m.get('subsystem_count', 0)} subsystems."
    )
    repos = pkb.get("repositories", [])
    if repos:
        lines.append(
            "Repositories: "
            + "; ".join(f"{r.get('name')} ({r.get('role_label', r.get('role'))})" for r in repos[:8])
        )
    areas = pkb.get("areas", [])[:8]
    if areas:
        lines.append(
            "Product areas: "
            + "; ".join(
                f"{a.get('name')} ({a.get('component_count', 0)} components)"
                for a in areas
            )
        )
    caps = pkb.get("capabilities_ui", [])
    untested = [c for c in caps if c.get("test_status_key") == "untested"]
    if caps:
        lines.append(
            f"Capabilities: {len(caps)} total, {len(untested)} without test coverage."
        )
    findings = pkb.get("findings", [])[:10]
    if findings:
        lines.append(
            "Top findings: "
            + "; ".join(f"{f.get('title')} ({f.get('severity_label', f.get('severity'))})" for f in findings)
        )
    journeys = pkb.get("journeys", [])[:6]
    if journeys:
        lines.append(
            "User journeys: "
            + "; ".join(f"{j.get('name')} ({j.get('test_status', '?')})" for j in journeys)
        )
    subsystems = pkb.get("subsystems", [])[:6]
    if subsystems:
        lines.append(
            "Technical modules: "
            + "; ".join(f"{s.get('name')} (hub: {s.get('hub_label', '?')})" for s in subsystems)
        )
    return "\n".join(lines)


def get_project_dna(project_id: str) -> dict[str, Any]:
    row = database.get_project(project_id)
    if not row:
        return {"project_id": project_id, "ready": False, "message": "Project not found."}

    pkb = enrich_pkb(load_pkb(project_id))
    if not pkb:
        graphs = database.get_project_graphs(project_id)
        ready = len(loadable_graphs(graphs))
        return {
            "project_id": project_id,
            "project_name": row["name"],
            "ready": False,
            "message": (
                "Refresh project understanding first, then generate Code Project DNA."
                if ready
                else "Index at least one repository, then refresh understanding."
            ),
            "graphs_ready": ready,
        }

    dna = pkb.get("dna", {})
    hs = pkb.get("health_summary", {})
    full = dna.get("full_summary") or ""
    return {
        "project_id": project_id,
        "project_name": row["name"],
        "ready": bool(full.strip()),
        "headline": dna.get("headline"),
        "summary": dna.get("summary"),
        "full_summary": full or None,
        "health_label": hs.get("status_label") or dna.get("health"),
        "health_key": hs.get("status_key") or dna.get("health"),
        "coverage_grade": dna.get("coverage_grade"),
        "generated_at": dna.get("dna_generated_at"),
        "metrics": pkb.get("metrics"),
        "message": None if full.strip() else "Generate Code Project DNA to create the full AI summary.",
    }


def generate_project_dna(
    project_id: str,
    backend: str = LLM_BACKEND,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Produce a long-form AI narrative and store it on the PKB."""
    row = database.get_project(project_id)
    if not row:
        raise ValueError(f"Project {project_id!r} not found")

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    if not loadable:
        raise ValueError("No indexed repositories. Ingest source code before generating DNA.")

    pkb = enrich_pkb(load_pkb(project_id))
    if not pkb:
        raise ValueError(
            "Project understanding not built yet. Run POST /projects/{id}/synthesize first."
        )

    dna = dict(pkb.get("dna", {}))
    metrics = pkb.get("metrics", {})
    context = _pkb_context_block(pkb)

    if not use_llm:
        headline, short = _template_full_dna(row["name"], metrics, pkb)
        full_summary = short
    else:
        prompt = (
            f'You are writing "Code Project DNA" — a complete, plain-language intelligence brief '
            f'for the software project "{row["name"]}".\n\n'
            f"Avoid graph jargon (no nodes, edges, communities, PKB). "
            f"Write for product owners, engineering leads, and new hires.\n\n"
            f"STRUCTURED CONTEXT (from indexed repositories):\n{context}\n\n"
            "Write the following sections with clear headings:\n"
            "## What this system is\n"
            "## How it is organized\n"
            "## Quality and test coverage\n"
            "## Top risks and gaps\n"
            "## Recommended focus (next 30 days)\n\n"
            "Be specific using names from the context. Total length 400-700 words."
        )
        full_summary = engine.llm_ask(prompt, backend=backend, max_tokens=1200)
        headline = _extract_headline(full_summary, row["name"])
        short = _first_paragraph(full_summary)

    now = datetime.now(timezone.utc).isoformat()
    dna.update({
        "headline": headline,
        "summary": short[:500],
        "full_summary": full_summary.strip(),
        "dna_generated_at": now,
        "health": metrics.get("health", dna.get("health", "unknown")),
        "coverage_grade": metrics.get("coverage_grade", dna.get("coverage_grade")),
    })
    pkb["dna"] = dna
    pkb.setdefault("synthesis_notes", []).append(f"Project DNA generated at {now}")
    save_pkb(project_id, pkb)

    return get_project_dna(project_id)


def _extract_headline(text: str, project_name: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and len(line) < 120 and not line.startswith("##"):
            return line
    return f"{project_name} — architecture intelligence summary"


def _first_paragraph(text: str) -> str:
    chunks: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("##"):
            if chunks:
                break
            continue
        if s:
            chunks.append(s)
    return " ".join(chunks)[:500] if chunks else text[:500]


def _template_full_dna(name: str, metrics: dict, pkb: dict) -> tuple[str, str]:
    areas = ", ".join(a.get("name", "") for a in pkb.get("areas", [])[:5]) or "various modules"
    body = (
        f"# {name}\n\n"
        f"## What this system is\n"
        f"{name} is indexed across {metrics.get('graphs_ready', 0)} repositories with "
        f"{metrics.get('total_nodes', 0):,} tracked components.\n\n"
        f"## How it is organized\n"
        f"Major areas include: {areas}.\n\n"
        f"## Quality and test coverage\n"
        f"About {metrics.get('functional_coverage_pct', 0)}% of capabilities show test linkage "
        f"(grade {metrics.get('coverage_grade', '?')}).\n\n"
        f"## Top risks and gaps\n"
        f"{metrics.get('risk_count', 0)} structural findings are recorded. "
        f"{metrics.get('capabilities_uncovered', 0)} capabilities appear untested.\n\n"
        f"## Recommended focus\n"
        f"Run Code Project DNA with LLM enabled for a richer narrative, or refresh understanding after new commits."
    )
    return f"{name} — project intelligence snapshot", body
