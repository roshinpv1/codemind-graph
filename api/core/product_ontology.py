"""User-facing product ontology — maps PKB/graph internals to capabilities, areas, findings."""
from __future__ import annotations

import re
from typing import Any

from api.core.pkb_storage import load_pkb

ROLE_LABELS: dict[str, str] = {
    "source": "Production code",
    "test": "Test suite",
    "ci": "CI pipeline",
    "cd": "Deployment",
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
    return ROLE_LABELS.get((role or "source").lower(), role or "Repository")


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


def _mentions_phrase(text: str, phrase: str) -> bool:
    if len(phrase) < 4:
        return False
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text, re.I))


def compute_retrieval_quality(
    pkb: dict | None,
    evidence: list[dict],
    intent: str,
    has_context: bool,
) -> dict[str, Any]:
    score = 0.0
    if pkb:
        score += 0.35
    if len(evidence) >= 5:
        score += 0.35
    elif len(evidence) >= 2:
        score += 0.2
    if intent in ("blast_radius", "architecture", "risk") and any(
        f.get("category_key") == "hub" for f in (pkb or {}).get("findings", [])
    ):
        score += 0.15
    if not has_context:
        score = 0.1
    confidence = "high" if score >= 0.65 else "medium" if score >= 0.35 else "low"
    best_guesses: list[str] = []
    if confidence == "low" and pkb:
        best_guesses = [f["title"] for f in pkb.get("findings", [])[:3]]
    return {
        "score": round(score, 2),
        "confidence": confidence,
        "evidence_count": len(evidence),
        "pkb_present": bool(pkb),
        "best_guesses": best_guesses,
    }


def build_answer_card(
    answer: str,
    persona: str,
    pkb: dict | None,
    evidence: list[dict],
    *,
    confidence: str = "medium",
    retrieval_quality: dict | None = None,
) -> dict[str, Any]:
    """Structure LLM answer for UI — no graph jargon in primary fields."""
    related: list[dict] = []
    gaps: list[str] = []
    answer_l = answer.lower()
    if pkb:
        for cap in pkb.get("capabilities_ui", [])[:20]:
            name = cap.get("name", "")
            if name and len(name) >= 4 and _mentions_phrase(answer, name):
                related.append({
                    "name": name,
                    "type": "capability",
                    "test_status": cap.get("test_status"),
                })
        for f in pkb.get("findings", [])[:12]:
            if not f.get("title"):
                continue
            if f.get("category_key") == "coverage_gap":
                gaps.append(f["title"])
            elif _mentions_phrase(answer, f["title"][:60]):
                related.append({
                    "name": f["title"],
                    "type": "finding",
                    "severity": f.get("severity_label"),
                })
    for e in evidence[:8]:
        lbl = (e.get("label") or "").strip()
        if not lbl or len(lbl) < 3:
            continue
        if lbl.startswith(".") and lbl.endswith("()"):
            continue
        if any(r["name"] == lbl for r in related):
            continue
        related.append({
            "name": lbl,
            "type": "component",
            "file": e.get("source_file"),
        })

    rq = retrieval_quality or {}
    conf = rq.get("confidence", confidence)
    labels = {
        "high": "High confidence",
        "medium": "Medium confidence",
        "low": "Low confidence — verify in code",
    }

    return {
        "summary": answer,
        "confidence": conf,
        "confidence_label": labels.get(conf, labels["medium"]),
        "related": related[:8],
        "gaps": gaps[:5],
        "best_guesses": rq.get("best_guesses", []),
        "suggested_next_steps": _next_steps(persona, gaps, conf),
    }


def _next_steps(persona: str, gaps: list[str], confidence: str = "medium") -> list[str]:


    steps: list[str] = []
    if confidence == "low":
        steps.append("Treat this answer as directional — open cited files and run targeted tests.")
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
