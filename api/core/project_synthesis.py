"""Build Project Knowledge Base (PKB) from all ready graphs in a project."""
from __future__ import annotations

import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from api.config import LLM_BACKEND, PKB_VERSION
from api.core import database, engine, storage
from api.core.pkb_storage import load_pkb, save_pkb
from api.core.intent_router import SCENARIO_PACKS
from api.routers.coverage import (
    _functional_entry_points,
    _bfs_from,
    _is_test_node,
)
from api.core.cross_graph import loadable_graphs, cross_graph_match_entry_points
from api.core.project_roles import application_graphs, coverage_test_graphs


def _evidence(
    graph_id: str,
    graph_role: str,
    graph_name: str,
    node_id: str | None = None,
    label: str | None = None,
    source_file: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    e: dict[str, Any] = {
        "graph_id": graph_id,
        "graph_role": graph_role,
        "graph_name": graph_name,
    }
    if node_id:
        e["node_id"] = node_id
    if label:
        e["label"] = label
    if source_file:
        e["source_file"] = source_file
    if detail:
        e["detail"] = detail
    return e


def _template_brief(name: str, members: list[str], G: nx.Graph, hub: str | None) -> str:
    hub_label = G.nodes[hub].get("label", hub) if hub and hub in G else "unknown"
    files = list({G.nodes[n].get("source_file", "") for n in members[:20] if n in G})[:5]
    return (
        f"**{name}** groups {len(members)} components around `{hub_label}`. "
        f"Key files: {', '.join(f for f in files if f) or 'n/a'}."
    )


def synthesize_project(
    project_id: str,
    backend: str = LLM_BACKEND,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Full PKB build. Returns the PKB dict and writes to disk."""
    row = database.get_project(project_id)
    if not row:
        raise ValueError(f"Project {project_id!r} not found")

    graphs = database.get_project_graphs(project_id)
    loadable = loadable_graphs(graphs)
    by_role: dict[str, list] = defaultdict(list)
    for g in loadable:
        by_role[g["graph_role"] or "source"].append(g)

    prev = load_pkb(project_id) or {}
    pkb: dict[str, Any] = {
        "meta": {
            "version": PKB_VERSION,
            "project_id": project_id,
            "project_name": row["name"],
            "synthesized_at": datetime.now(timezone.utc).isoformat(),
            "graph_ids": [g["id"] for g in loadable],
            "roles_present": list(by_role.keys()),
            "status": "ready" if loadable else "empty",
        },
        "dna": {},
        "subsystems": [],
        "capabilities": [],
        "risks": [],
        "flows": [],
        "module_briefs": {},
        "metrics": {},
        "open_questions": [],
        "scenarios": SCENARIO_PACKS,
        "synthesis_notes": [],
    }

    if not loadable:
        pkb["dna"] = {
            "headline": "No indexed repositories yet",
            "summary": "Add your production codebase to build a product map and findings.",
            "health": "unknown",
        }
        from api.core.product_ontology import finalize_ontology
        finalize_ontology(pkb, [])
        save_pkb(project_id, pkb)
        return pkb

    # ── Per-graph analysis ───────────────────────────────────────────────────
    all_gods: list[dict] = []
    all_surprises: list[dict] = []
    subsystems: list[dict] = []
    module_briefs: dict[str, str] = {}
    community_labels: dict[str, dict[int, str]] = {}

    total_nodes = 0
    total_edges = 0

    structural = application_graphs(loadable)
    for gmeta in structural:
        gid = gmeta["id"]
        role = gmeta["graph_role"] or "source"
        G = engine.load_graph(gid)
        total_nodes += G.number_of_nodes()
        total_edges += G.number_of_edges()
        communities = engine.communities_from_graph(G)

        labels: dict[int, str] = {}
        if use_llm and communities:
            try:
                labels = engine.llm_label_communities(G, communities, backend=backend)
            except Exception as exc:
                pkb["synthesis_notes"].append(f"LLM labels skipped for {gmeta['name']}: {exc}")
        for cid in communities:
            if cid not in labels:
                labels[cid] = f"Community {cid}"
        community_labels[gid] = labels

        from graphify.analyze import god_nodes, surprising_connections, suggest_questions

        gods = god_nodes(G)
        for g in gods[:15]:
            nid = g.get("id") or g.get("node")
            if nid and nid in G:
                all_gods.append({
                    "severity": "high" if G.degree(nid) > 20 else "medium",
                    "category": "hub",
                    "title": f"Hub: {G.nodes[nid].get('label', nid)}",
                    "detail": f"Degree {G.degree(nid)} — changes here have wide blast radius.",
                    "evidence": [_evidence(gid, role, gmeta["name"], nid, G.nodes[nid].get("label"), G.nodes[nid].get("source_file"))],
                })

        surprises = surprising_connections(G, communities)
        for s in surprises[:10]:
            all_surprises.append({
                "severity": "medium",
                "category": "coupling",
                "title": f"Cross-module link: {s.get('source_label') or s.get('source')} ↔ {s.get('target_label') or s.get('target')}",
                "detail": s.get("explanation", s.get("relation", "")),
                "evidence": [_evidence(gid, role, gmeta["name"], detail=s.get("relation"))],
            })

        if role == "source" or len(by_role.get("source", [])) == 0:
            questions = suggest_questions(G, communities, labels)
            pkb["open_questions"].extend(questions[:5])

        for cid, members in sorted(communities.items(), key=lambda x: -len(x[1]))[:12]:
            hub = max(members, key=lambda n: G.degree(n), default=None)
            name = labels.get(cid, f"Community {cid}")
            subsystems.append({
                "id": f"{gid}:{cid}",
                "name": name,
                "graph_id": gid,
                "graph_role": role,
                "graph_name": gmeta["name"],
                "member_count": len(members),
                "hub_label": G.nodes[hub].get("label", hub) if hub else None,
                "cohesion": None,
            })
            brief_key = f"{gid}:{cid}"
            if use_llm and hub:
                try:
                    top = sorted(members, key=lambda n: G.degree(n), reverse=True)[:8]
                    member_labels = [G.nodes[n].get("label", n) for n in top]
                    prompt = (
                        f"Write a 2-3 sentence technical brief for software module '{name}'. "
                        f"Members: {', '.join(member_labels)}. Be specific. No markdown headers."
                    )
                    module_briefs[brief_key] = engine.llm_ask(prompt, backend=backend, max_tokens=120)
                except Exception:
                    module_briefs[brief_key] = _template_brief(name, members, G, hub)
            else:
                module_briefs[brief_key] = _template_brief(name, members, G, hub)

    pkb["module_briefs"] = module_briefs
    pkb["subsystems"] = subsystems[:24]

    # ── Capabilities + coverage (application code only) ───────────────────────
    loadable_source = application_graphs(loadable)
    capabilities: list[dict] = []
    func_pct = 0.0
    gaps_count = 0

    if loadable_source:
        G_source = engine.load_graph(loadable_source[0]["id"])
        for sg in loadable_source[1:]:
            G_source = nx.compose(G_source, engine.load_graph(sg["id"]))
        entry_pts = _functional_entry_points(G_source)
        test_ids = {nid for nid, d in G_source.nodes(data=True) if _is_test_node(d)}
        reachable = _bfs_from(G_source, test_ids) if test_ids else set()
        covered = set(entry_pts.keys()) & reachable

        covered_cross: set[str] = set()
        for tg in loadable_graphs(coverage_test_graphs(loadable)):
            G_test = engine.load_graph(tg["id"])
            covered_cross |= cross_graph_match_entry_points(G_source, G_test, entry_pts)

        all_covered = covered | covered_cross
        func_pct = round(len(all_covered) / max(len(entry_pts), 1) * 100, 1)
        gaps_count = len(entry_pts) - len(all_covered)

        for nid, ep in sorted(entry_pts.items(), key=lambda x: -x[1]["degree"])[:40]:
            capabilities.append({
                "id": nid,
                "label": ep["label"],
                "source_file": ep["source_file"],
                "entry_type": ep["entry_type"],
                "covered": nid in all_covered,
                "risk": ep.get("risk", "medium"),
                "degree": ep["degree"],
                "evidence": [_evidence(
                    loadable_source[0]["id"], "source", loadable_source[0]["name"],
                    nid, ep["label"], ep["source_file"],
                )],
            })

        for nid in list(entry_pts.keys()):
            if nid not in all_covered and entry_pts[nid]["degree"] > 5:
                ep = entry_pts[nid]
                pkb["risks"].append({
                    "severity": "high" if ep["degree"] > 15 else "medium",
                    "category": "coverage_gap",
                    "title": f"Untested entry: {ep['label']}",
                    "detail": f"User-visible entry point in {ep['source_file']} has no test reachability.",
                    "evidence": [_evidence(
                        loadable_source[0]["id"], "source", loadable_source[0]["name"],
                        nid, ep["label"], ep["source_file"],
                    )],
                })

    pkb["capabilities"] = capabilities

    # ── Flows (top entry points) ───────────────────────────────────────────
    for cap in capabilities[:8]:
        pkb["flows"].append({
            "name": cap["label"],
            "description": f"Entry point ({cap['entry_type']}) — {'covered' if cap['covered'] else 'uncovered'}",
            "covered": cap["covered"],
            "evidence": cap.get("evidence", []),
        })

    # ── Risk register merge ──────────────────────────────────────────────────
    pkb["risks"].extend(all_gods[:12])
    pkb["risks"].extend(all_surprises[:8])
    pkb["risks"] = _dedupe_risks(pkb["risks"])[:30]

    # ── Metrics ─────────────────────────────────────────────────────────────
    grade = "A" if func_pct >= 80 else "B" if func_pct >= 60 else "C" if func_pct >= 40 else "D" if func_pct >= 20 else "F"
    health = "green" if func_pct >= 70 and len(pkb["risks"]) < 8 else "yellow" if func_pct >= 40 else "red"

    pkb["metrics"] = {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "graphs_ready": len(loadable),
        "functional_coverage_pct": func_pct,
        "coverage_grade": grade,
        "capabilities_total": len(capabilities),
        "capabilities_uncovered": gaps_count,
        "risk_count": len(pkb["risks"]),
        "subsystem_count": len(subsystems),
        "health": health,
    }

    # ── Project DNA (short snapshot — full narrative via POST /projects/{id}/dna/generate) ──
    top_subs = [s["name"] for s in subsystems[:6]]
    headline, summary = _template_dna(row["name"], pkb["metrics"], top_subs)
    prev_dna = prev.get("dna", {})
    pkb["dna"] = {
        "headline": headline,
        "summary": summary,
        "health": health,
        "coverage_grade": grade,
        "full_summary": prev_dna.get("full_summary", ""),
        "dna_generated_at": prev_dna.get("dna_generated_at"),
    }

    # Preserve delta baseline
    if prev.get("meta", {}).get("synthesized_at"):
        pkb["meta"]["previous_synthesis_at"] = prev["meta"]["synthesized_at"]
        pkb["meta"]["previous_metrics"] = prev.get("metrics", {})

    from api.core.product_ontology import finalize_ontology
    repo_meta = [
        {
            "id": g["id"],
            "name": g["name"],
            "graph_role": g["graph_role"] or "source",
            "status": g["status"],
            "node_count": g["node_count"],
        }
        for g in loadable
    ]
    finalize_ontology(pkb, repo_meta)

    save_pkb(project_id, pkb)
    return pkb


def _template_dna(name: str, metrics: dict, subsystems: list[str]) -> tuple[str, str]:
    headline = f"{name} — {metrics.get('graphs_ready', 0)} repos, {metrics.get('subsystem_count', 0)} modules"
    summary = (
        f"The project indexes {metrics.get('total_nodes', 0):,} components across "
        f"{metrics.get('graphs_ready', 0)} repositories. "
        f"Functional test coverage of user-facing entry points is {metrics.get('functional_coverage_pct', 0)}% "
        f"(grade {metrics.get('coverage_grade', '?')}). "
        f"Major areas include: {', '.join(subsystems[:5]) or 'unknown'}."
    )
    return headline, summary


def _dedupe_risks(risks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in risks:
        key = r.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def maybe_synthesize_project(project_id: str | None, backend: str = LLM_BACKEND) -> None:
    """Background hook after graph ingest — refresh PKB when project has ready graphs."""
    if not project_id:
        return
    try:
        synthesize_project(project_id, backend=backend, use_llm=True)
        print(f"[synthesis] PKB updated for project {project_id}", file=sys.stderr)
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[synthesis] project {project_id} failed: {exc}\n{tb}", file=sys.stderr)


def compute_delta(project_id: str) -> dict[str, Any]:
    """Changes since last visit or previous synthesis."""
    visits = __import__("api.core.pkb_storage", fromlist=["load_visits"]).load_visits(project_id)
    pkb = load_pkb(project_id)
    if not pkb:
        return {"has_delta": False, "message": "No intelligence synthesized yet."}

    prev_metrics = pkb.get("meta", {}).get("previous_metrics") or {}
    cur = pkb.get("metrics", {})
    deltas: list[str] = []

    for key, label in [
        ("functional_coverage_pct", "Capabilities tested"),
        ("risk_count", "Open findings"),
        ("capabilities_uncovered", "Untested capabilities"),
    ]:
        old_v = prev_metrics.get(key)
        new_v = cur.get(key)
        if old_v is not None and new_v is not None and old_v != new_v:
            deltas.append(f"{label}: {old_v} → {new_v}")

    new_risks = pkb.get("risks", [])[:3]
    return {
        "has_delta": bool(deltas or new_risks),
        "last_visit": visits.get("last_visit"),
        "synthesized_at": pkb.get("meta", {}).get("synthesized_at"),
        "metric_changes": deltas,
        "top_risks": [{"title": r["title"], "severity": r["severity"]} for r in new_risks],
        "headline": pkb.get("dna", {}).get("headline"),
    }
