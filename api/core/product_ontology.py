"""User-facing product ontology — maps PKB/graph internals to capabilities, areas, findings."""
from __future__ import annotations

from typing import Any

from api.core.pkb_storage import load_pkb
from api.core.project_roles import normalize_role, role_label as _slot_role_label

ROLE_LABELS: dict[str, str] = {
<<<<<<< Updated upstream
    "source": "Application",
    "ci": "Application",
=======
    "source": "Source",
>>>>>>> Stashed changes
    "test": "Test",
    "cd": "CD",
}

FINDING_CATEGORY_LABELS: dict[str, str] = {
    "coverage_gap": "Testing",
    "hub": "Architecture",
    "coupling": "Architecture",
    "security": "Security",
    "operations": "Operations",
}

SEVERITY_LABELS = {"high": "High", "medium": "Medium", "low": "Low", "critical": "Critical"}

HEALTH_LABELS = {"green": "Healthy", "yellow": "Needs attention", "red": "At risk", "unknown": "Unknown"}


def repository_role_label(role: str | None) -> str:
    return ROLE_LABELS.get(normalize_role(role), _slot_role_label(role))


def capability_test_label(covered: bool) -> str:
    return "Tested" if covered else "Not tested"


def _risk_to_finding(r: dict) -> dict[str, Any]:
    cat = r.get("category", "general")
    return {
        "id": r.get("id") or r.get("title", ""),
        "title": r.get("title", "Concern"),
        "why_it_matters": r.get("detail", ""),
        "severity": r.get("severity", "medium"),
        "severity_label": SEVERITY_LABELS.get(r.get("severity", ""), r.get("severity", "")),
        "category": FINDING_CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
        "category_key": cat,
        "suggested_action": _suggested_action(cat, r),
        "evidence": r.get("evidence", []),
    }


def _suggested_action(category: str, finding: dict) -> str:
    if category == "coverage_gap":
        return "Add or extend automated tests for this capability."
    if category == "hub":
        return "Review changes carefully; consider splitting or documenting dependencies."
    if category == "coupling":
        return "Assess whether modules should be decoupled before expanding features."
    return "Review with your team and track in your next sprint."


def _subsystem_to_area(s: dict, briefs: dict) -> dict[str, Any]:
    brief_key = s.get("id") or f"{s.get('graph_id')}:{s.get('name')}"
    summary = briefs.get(brief_key) or briefs.get(s.get("id", ""), "")
    if summary.startswith("**"):
        summary = summary.split("\n", 1)[-1].strip()
    return {
        "id": s.get("id", s.get("name", "")),
        "name": s.get("name", "Area"),
        "component_count": s.get("member_count", 0),
        "centerpiece": s.get("hub_label"),
        "repository": s.get("graph_name"),
        "repository_role": repository_role_label(s.get("graph_role")),
        "summary": summary[:400] if summary else None,
    }


def _capability_ui(c: dict) -> dict[str, Any]:
    covered = bool(c.get("covered"))
    return {
        "id": c.get("id", c.get("label", "")),
        "name": c.get("label", "Capability"),
        "source_file": c.get("source_file"),
        "test_status": capability_test_label(covered),
        "test_status_key": "tested" if covered else "untested",
        "importance": c.get("risk", "medium"),
        "type": c.get("entry_type", "feature"),
        "evidence": c.get("evidence", []),
    }


def _flow_to_journey(f: dict) -> dict[str, Any]:
    covered = f.get("covered", False)
    return {
        "name": f.get("name", "Flow"),
        "summary": (f.get("description") or "").replace("Entry point", "User-facing step"),
        "test_status": capability_test_label(covered),
        "steps": [f.get("name", "Start")],
        "evidence": f.get("evidence", []),
    }


def finalize_ontology(pkb: dict[str, Any], repositories: list[dict] | None = None) -> dict[str, Any]:
    """Add user-facing ontology fields to PKB (in-place + return)."""
    briefs = pkb.get("module_briefs", {})
    subsystems = pkb.get("subsystems", [])

    pkb["areas"] = [_subsystem_to_area(s, briefs) for s in subsystems]
    pkb["findings"] = [_risk_to_finding(r) for r in pkb.get("risks", [])]
    pkb["capabilities_ui"] = [_capability_ui(c) for c in pkb.get("capabilities", [])]
    pkb["journeys"] = [_flow_to_journey(f) for f in pkb.get("flows", [])]

    repos: list[dict] = []
    if repositories:
        for g in repositories:
            repos.append({
                "id": g["id"],
                "name": g["name"],
                "role": g.get("graph_role") or "source",
                "role_label": repository_role_label(g.get("graph_role")),
                "status": g.get("status", "ready"),
                "indexed_components": g.get("node_count", 0),
            })
    pkb["repositories"] = repos

    m = pkb.get("metrics", {})
    pkb["health_summary"] = {
        "status_key": m.get("health", "unknown"),
        "status_label": HEALTH_LABELS.get(str(m.get("health", "unknown")), "Unknown"),
        "capabilities_tested_pct": m.get("functional_coverage_pct", 0),
        "capabilities_total": m.get("capabilities_total", 0),
        "capabilities_untested": m.get("capabilities_uncovered", 0),
        "open_findings": len(pkb["findings"]),
        "product_areas": len(pkb["areas"]),
    }
    return pkb


def enrich_pkb(pkb: dict[str, Any] | None) -> dict[str, Any] | None:
    if not pkb:
        return None
    if pkb.get("areas") and pkb.get("findings"):
        return pkb
    return finalize_ontology(pkb, pkb.get("repositories"))


def get_product_map(project_id: str) -> dict[str, Any]:
    pkb = load_pkb(project_id)
    if not pkb:
        return {
            "project_id": project_id,
            "ready": False,
            "message": "Index your repositories, then refresh project understanding.",
        }
    pkb = enrich_pkb(pkb) or pkb
    dna = pkb.get("dna", {})
    hs = pkb.get("health_summary", {})
    return {
        "project_id": project_id,
        "ready": True,
        "headline": dna.get("headline"),
        "summary": dna.get("summary"),
        "health": hs,
        "areas": pkb.get("areas", [])[:16],
        "capabilities": pkb.get("capabilities_ui", [])[:40],
        "findings": pkb.get("findings", [])[:12],
        "journeys": pkb.get("journeys", [])[:8],
        "repositories": pkb.get("repositories", []),
        "understanding_updated_at": pkb.get("meta", {}).get("synthesized_at"),
    }


def get_findings(
    project_id: str,
    *,
    category: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    pkb = enrich_pkb(load_pkb(project_id))
    if not pkb:
        return {"project_id": project_id, "findings": [], "count": 0}
    findings = pkb.get("findings", [])
    if category:
        cat_lower = category.lower()
        findings = [
            f for f in findings
            if f.get("category_key", "").lower() == cat_lower
            or f.get("category", "").lower() == cat_lower
        ]
    return {
        "project_id": project_id,
        "findings": findings[:limit],
        "count": len(findings),
    }


def get_briefing_user(project_id: str) -> dict[str, Any]:
    pkb = enrich_pkb(load_pkb(project_id))
    if not pkb:
        return {
            "project_id": project_id,
            "ready": False,
            "message": "Refresh project understanding after your repositories finish indexing.",
        }
    hs = pkb.get("health_summary", {})
    dna = pkb.get("dna", {})
    return {
        "project_id": project_id,
        "ready": True,
        "headline": dna.get("headline"),
        "summary": dna.get("summary"),
        "health_label": hs.get("status_label"),
        "health_key": hs.get("status_key"),
        "capabilities_tested_pct": hs.get("capabilities_tested_pct"),
        "capabilities_untested": hs.get("capabilities_untested"),
        "open_findings": hs.get("open_findings"),
        "top_findings": pkb.get("findings", [])[:5],
        "top_areas": pkb.get("areas", [])[:6],
        "understanding_updated_at": pkb.get("meta", {}).get("synthesized_at"),
    }


def build_answer_card(
    answer: str,
    persona: str,
    pkb: dict | None,
    evidence: list[dict],
    *,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Structure LLM answer for UI — no graph jargon in primary fields."""
    related: list[dict] = []
    gaps: list[str] = []
    if pkb:
        for cap in pkb.get("capabilities_ui", [])[:5]:
            if cap["name"].lower() in answer.lower():
                related.append({"name": cap["name"], "type": "capability", "test_status": cap["test_status"]})
        for f in pkb.get("findings", [])[:8]:
            if not f.get("title"):
                continue
            if f.get("category_key") == "coverage_gap":
                gaps.append(f["title"])
    for e in evidence[:6]:
        lbl = e.get("label") or e.get("node_id")
        if lbl and not any(r["name"] == lbl for r in related):
            related.append({
                "name": lbl,
                "type": "component",
                "file": e.get("source_file"),
            })

    return {
        "summary": answer,
        "confidence": confidence,
        "confidence_label": {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"}.get(
            confidence, "Medium confidence"
        ),
        "related": related[:8],
        "gaps": gaps[:5],
        "suggested_next_steps": _next_steps(persona, gaps),
    }


def _next_steps(persona: str, gaps: list[str]) -> list[str]:
    steps: list[str] = []
    if persona == "qa" and gaps:
        steps.append("Prioritize test design for the untested capabilities listed above.")
    elif persona == "executive":
        steps.append("Review top findings with engineering leads before the next release.")
    elif persona == "onboarding":
        steps.append("Open the highlighted product areas and follow one journey end to end.")
    else:
        steps.append("Open related files in your IDE and run the focused test suite.")
    return steps


def technical_proof(evidence: list[dict], sources: list[dict]) -> dict[str, Any]:
    """Collapsed technical detail for 'Show proof' expander."""
    components = [
        {
            "label": e.get("label"),
            "file": e.get("source_file"),
            "repository": e.get("graph_name"),
        }
        for e in evidence[:20]
        if e.get("label") or e.get("source_file")
    ]
    repos = [
        {"name": s.get("graph_name"), "role": repository_role_label(s.get("graph_role"))}
        for s in sources
    ]
    return {"repositories": repos, "components": components}
