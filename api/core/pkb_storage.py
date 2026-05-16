"""Project Knowledge Base (PKB) — persisted intelligence per project."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.config import PKB_VERSION, PROJECTS_DIR


def project_dir(project_id: str) -> Path:
    d = PROJECTS_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def intelligence_path(project_id: str) -> Path:
    return project_dir(project_id) / "intelligence.json"


def memory_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def visits_path(project_id: str) -> Path:
    return project_dir(project_id) / "visits.json"


def load_pkb(project_id: str) -> dict[str, Any] | None:
    p = intelligence_path(project_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_pkb(project_id: str, pkb: dict[str, Any]) -> Path:
    pkb.setdefault("meta", {})
    pkb["meta"]["version"] = PKB_VERSION
    pkb["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = intelligence_path(project_id)
    path.write_text(json.dumps(pkb, indent=2), encoding="utf-8")
    return path


def load_visits(project_id: str) -> dict[str, Any]:
    p = visits_path(project_id)
    if not p.exists():
        return {"last_visit": None, "history": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"last_visit": None, "history": []}


def record_visit(project_id: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    data = load_visits(project_id)
    data["last_visit"] = now
    history = data.get("history") or []
    history.append(now)
    data["history"] = history[-50:]
    visits_path(project_id).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return now


def append_memory(
    project_id: str,
    question: str,
    answer: str,
    *,
    persona: str = "developer",
    evidence: list[dict] | None = None,
) -> Path:
    """Persist a Q&A into project memory for future synthesis context."""
    slug = "".join(c if c.isalnum() else "_" for c in question.lower())[:40].strip("_")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = memory_dir(project_id) / f"qa_{ts}_{slug}.json"
    path.write_text(
        json.dumps(
            {
                "question": question,
                "answer": answer,
                "persona": persona,
                "evidence": evidence or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def list_memory(project_id: str, limit: int = 20) -> list[dict[str, Any]]:
    md = memory_dir(project_id)
    items: list[dict[str, Any]] = []
    for p in sorted(md.glob("qa_*.json"), reverse=True)[:limit]:
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items
