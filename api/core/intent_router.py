"""Classify user questions to retrieve the right PKB slices and graph context."""
from __future__ import annotations

import re
from typing import Any

INTENTS = (
    "coverage",
    "security",
    "architecture",
    "blast_radius",
    "why",
    "how_it_works",
    "where_is",
    "onboarding",
    "risk",
    "general",
)

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("coverage", re.compile(
        r"\b(test|coverage|uncovered|untested|qa|regression|spec)\b", re.I
    )),
    ("security", re.compile(
        r"\b(security|auth|secret|pii|gdpr|vulnerab|attack|trust|encrypt)\b", re.I
    )),
    ("blast_radius", re.compile(
        r"\b(blast\s*radius|hotspot|impact\s+of|if\s+i\s+change|affect\s+many|high.degree)\b", re.I
    )),
    ("why", re.compile(
        r"\b(why\s+(did|do|was|is)|rationale|reason\s+for|tradeoff|trade.off|decision)\b", re.I
    )),
    ("architecture", re.compile(
        r"\b(architect|module|coupling|layer|circular|depend|god\s*node|community|hub)\b", re.I
    )),
    ("onboarding", re.compile(
        r"\b(onboard|new\s+(dev|engineer|hire)|start\s+here|learn|beginner|intro)\b", re.I
    )),
    ("risk", re.compile(
        r"\b(risk|danger|concern|debt|health|issue|problem|fragile)\b", re.I
    )),
    ("how_it_works", re.compile(
        r"\b(how\s+does|how\s+do|explain|flow|work|process|end\s*to\s*end)\b", re.I
    )),
    ("where_is", re.compile(
        r"\b(where\s+is|find|locate|which\s+file|which\s+module)\b", re.I
    )),
]


def classify_intent(question: str) -> dict[str, Any]:
    scores: dict[str, int] = {i: 0 for i in INTENTS}
    for intent, pat in _PATTERNS:
        if pat.search(question):
            scores[intent] += 2
    # Prefer specific intents when multiple patterns match equally.
    priority = (
        "blast_radius",
        "why",
        "coverage",
        "security",
        "risk",
        "architecture",
        "how_it_works",
        "where_is",
        "onboarding",
        "general",
    )
    top = max(scores.values())
    if top == 0:
        best = "general"
    else:
        best = next(i for i in priority if scores.get(i) == top)
    return {
        "intent": best,
        "scores": scores,
        "pkb_sections": _sections_for_intent(best),
    }


def _sections_for_intent(intent: str) -> list[str]:
    mapping = {
        "coverage": ["capabilities", "metrics", "risks"],
        "security": ["risks", "subsystems", "dna"],
        "architecture": ["subsystems", "risks", "module_briefs", "hubs"],
        "blast_radius": ["hubs", "risks", "module_briefs", "metrics"],
        "why": ["decisions", "module_briefs", "risks"],
        "how_it_works": ["flows", "module_briefs", "capabilities"],
        "where_is": ["capabilities", "subsystems"],
        "onboarding": ["dna", "flows", "subsystems"],
        "risk": ["risks", "metrics", "dna", "hubs"],
        "general": ["dna", "risks", "capabilities", "subsystems"],
    }
    return mapping.get(intent, mapping["general"])


SCENARIO_PACKS: dict[str, dict[str, Any]] = {
    "ship_safely": {
        "title": "Release checklist",
        "persona": "developer",
        "questions": [
            "What are the blast-radius hotspots if I change a high-degree hub?",
            "Which entry points lack test coverage and are highest risk?",
            "What cross-module coupling should I review before merging?",
        ],
    },
    "due_diligence": {
        "title": "Executive snapshot (10 min)",
        "persona": "executive",
        "questions": [
            "What is this system and what are its major subsystems?",
            "What are the top 5 structural risks?",
            "How healthy is test coverage for user-visible features?",
        ],
    },
    "onboard_dev": {
        "title": "New teammate orientation",
        "persona": "onboarding",
        "questions": [
            "Where should a new developer start reading the codebase?",
            "What are the critical user-facing flows?",
            "Which modules are the architectural centers of gravity?",
        ],
    },
    "security_review": {
        "title": "Trust & exposure review",
        "persona": "security",
        "questions": [
            "What authentication and trust-boundary patterns exist?",
            "Which components have the highest connectivity and why does that matter?",
            "What capabilities are untested and security-sensitive?",
        ],
    },
    "qa_gaps": {
        "title": "Test gap sprint planning",
        "persona": "qa",
        "questions": [
            "Which user-visible entry points are not covered by tests?",
            "How do test-repo labels map to production entry points?",
            "What should we prioritize in the next regression sprint?",
        ],
    },
}
