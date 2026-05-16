"""User-facing documentation views — translate graphify wiki/report into plain language."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx

from api.core import database, engine
from api.core.storage import graph_dir, report_path, wiki_path


def _strip_md_bullet(line: str) -> str:
    text = line.lstrip("- ").strip()
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\s*\(\d+\s+connections?\)", "", text)
    text = re.sub(r"\s*—\s*`[^`]+`$", "", text)
    return text.strip()


def _section_lines(content: str, heading: str) -> list[str]:
    """Lines under ## heading until next ##."""
    lines = content.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            if line[3:].strip().lower() == heading.lower():
                in_section = True
            continue
        if in_section and line.strip():
            out.append(line)
    return out


def wiki_page_to_guide(content: str, page_name: str) -> dict[str, Any]:
    """Turn one wiki article into a scannable guide block (no graph jargon)."""
    title = page_name.replace("_", " ")
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    key_items: list[str] = []
    for line in _section_lines(content, "Key Concepts"):
        if line.startswith("- "):
            item = _strip_md_bullet(line)
            if item and not item.startswith("... and "):
                key_items.append(item)

    related: list[str] = []
    for line in _section_lines(content, "Relationships"):
        if line.startswith("- "):
            m = re.match(r"-\s*\[\[([^\]]+)\]\]", line)
            if m:
                related.append(m.group(1))

    source_files: list[str] = []
    for line in _section_lines(content, "Source Files"):
        if line.startswith("- `"):
            source_files.append(line.strip("`- "))

    meta = ""
    for line in content.splitlines():
        if line.startswith("> "):
            meta = line[2:].replace("nodes", "components").replace("cohesion", "relatedness")
            break

    summary_parts = []
    if meta:
        summary_parts.append(meta)
    if related:
        summary_parts.append(f"Connects to: {', '.join(related[:4])}")

    return {
        "id": page_name,
        "title": title,
        "summary": ". ".join(summary_parts) if summary_parts else None,
        "key_items": key_items[:12],
        "source_files": source_files[:8],
    }


def extract_report_highlights(md: str) -> dict[str, Any]:
    """Pull readable slices from GRAPH_REPORT.md; hide audit-oriented sections."""
    highlights: dict[str, Any] = {
        "stats_line": None,
        "key_components": [],
        "notable_connections": [],
        "suggested_questions": [],
    }

    for line in md.splitlines():
        if line.startswith("- ") and "nodes" in line and "edges" in line:
            highlights["stats_line"] = (
                line.lstrip("- ")
                .replace("nodes", "components")
                .replace("edges", "relationships")
                .replace("communities", "product areas")
            )
            break

    in_gods = False
    for line in md.splitlines():
        if line.startswith("## God Nodes"):
            in_gods = True
            continue
        if in_gods and line.startswith("## "):
            break
        if in_gods and re.match(r"^\d+\.\s+`", line):
            m = re.match(r"^\d+\.\s+`([^`]+)`\s*-\s*(\d+)\s+edges?", line)
            if m:
                highlights["key_components"].append({
                    "name": m.group(1),
                    "connection_count": int(m.group(2)),
                })

    in_surprises = False
    for line in md.splitlines():
        if "Surprising Connections" in line:
            in_surprises = True
            continue
        if in_surprises and line.startswith("## "):
            break
        if in_surprises and line.startswith("- `"):
            highlights["notable_connections"].append(
                line.lstrip("- ")
                .replace("INFERRED", "inferred")
                .replace("EXTRACTED", "from code")
                .replace("AMBIGUOUS", "uncertain")
            )

    in_questions = False
    for line in md.splitlines():
        if line.startswith("## Suggested Questions"):
            in_questions = True
            continue
        if in_questions and line.startswith("## "):
            break
        if in_questions and line.startswith("- **"):
            m = re.match(r"- \*\*([^*]+)\*\*", line)
            if m:
                highlights["suggested_questions"].append(m.group(1).strip())

    return highlights


def build_ownership_areas(G: nx.Graph) -> list[dict[str, Any]]:
    communities = engine.communities_from_graph(G)
    areas: list[dict[str, Any]] = []
    for cid, members in communities.items():
        source_files = list({
            G.nodes[n].get("source_file", "")
            for n in members
            if G.nodes[n].get("source_file")
        })
        hub = max(members, key=lambda n: G.degree(n), default=None)
        if not hub:
            continue
        areas.append({
            "id": str(cid),
            "name": G.nodes[hub].get("label", hub) or f"Area {cid}",
            "centerpiece": G.nodes[hub].get("label", hub),
            "component_count": len(members),
            "source_files": source_files[:6],
        })
    areas.sort(key=lambda a: a["component_count"], reverse=True)
    return areas[:12]


def build_docs_overview(graph_id: str) -> dict[str, Any]:
    row = database.get_graph(graph_id)
    if not row:
        return {"graph_id": graph_id, "ready": False, "message": "Repository not found."}
    row = dict(row)
    if row["status"] != "ready":
        return {
            "graph_id": graph_id,
            "ready": False,
            "message": f"Documentation available after indexing completes (status: {row['status']}).",
        }

    gdir = graph_dir(graph_id)
    artifacts = {
        "report": report_path(graph_id).exists(),
        "wiki": wiki_path(graph_id).exists() and any(wiki_path(graph_id).glob("*.md")),
        "callflow": (gdir / "callflow.html").exists(),
        "tree": (gdir / "tree.html").exists(),
    }

    wiki_guides: list[dict[str, Any]] = []
    wiki_dir = wiki_path(graph_id)
    if wiki_dir.exists():
        for md_file in sorted(wiki_dir.glob("*.md")):
            if md_file.stem == "index":
                continue
            wiki_guides.append(wiki_page_to_guide(md_file.read_text(encoding="utf-8"), md_file.stem))

    report_highlights: dict[str, Any] | None = None
    rp = report_path(graph_id)
    if rp.exists():
        report_highlights = extract_report_highlights(rp.read_text(encoding="utf-8"))

    product_areas: list[dict[str, Any]] = []
    try:
        G = engine.load_graph(graph_id)
        product_areas = build_ownership_areas(G)
    except Exception:
        pass

    overview_cache = gdir / "overview.json"
    plain_summary: str | None = None
    if overview_cache.exists():
        try:
            import json
            plain_summary = json.loads(overview_cache.read_text(encoding="utf-8")).get("plain_summary")
        except Exception:
            plain_summary = None

    return {
        "graph_id": graph_id,
        "repository_name": row.get("name") or graph_id,
        "ready": True,
        "audience_note": (
            "This overview uses everyday product language. "
            "Open Technical reference for the full graph audit (nodes, confidence scores, wikilinks)."
        ),
        "plain_summary": plain_summary,
        "plain_summary_available": plain_summary is not None,
        "product_areas": product_areas,
        "wiki_guides": wiki_guides,
        "report_highlights": report_highlights,
        "artifacts": artifacts,
        "suggested_actions": _suggested_actions(artifacts, wiki_guides, plain_summary),
    }


def _suggested_actions(
    artifacts: dict[str, bool],
    wiki_guides: list[dict],
    plain_summary: str | None,
) -> list[str]:
    actions: list[str] = []
    if not plain_summary:
        actions.append("Generate a plain-language summary (uses your configured LLM).")
    if not artifacts.get("wiki"):
        actions.append("Generate documentation to unlock area guides and flow diagrams.")
    if artifacts.get("callflow"):
        actions.append("Open Call flow to see how user-facing steps connect.")
    if wiki_guides:
        actions.append("Browse area guides below, then ask the project assistant follow-up questions.")
    return actions[:4]


def cache_plain_summary(graph_id: str, summary: str) -> Path:
    import json
    gdir = graph_dir(graph_id)
    gdir.mkdir(parents=True, exist_ok=True)
    path = gdir / "overview.json"
    path.write_text(json.dumps({"plain_summary": summary}, indent=2), encoding="utf-8")
    return path
