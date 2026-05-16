"""CodeMind Projects — group multiple graphs (source, test, ci, cd) into a
named project for cross-graph analysis, especially functional coverage.

Workflow
--------
1. POST /projects                         – create project
2. POST /ingest  { project_id, role }     – ingest repos with roles
   OR  POST /projects/{id}/graphs         – assign existing graph to project
3. GET  /projects/{id}/coverage           – functional coverage (entry-point vs test)
4. GET  /projects/{id}/graphs             – list member graphs by role
5. GET  /projects/{id}/summary            – health across all roles
"""
from __future__ import annotations
import re
import uuid
from collections import defaultdict

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.core import database, engine, storage
from api.core.cross_graph import loadable_graphs
from api.core.project_query import list_personas, project_ask, project_search
from api.core.project_synthesis import synthesize_project, compute_delta, maybe_synthesize_project
from api.core.project_dna import generate_project_dna, get_project_dna
from api.core import pkb_storage
from api.core.intent_router import SCENARIO_PACKS
from api.core.project_query import get_briefing, list_scenarios
from api.core.product_ontology import get_product_map, get_findings as get_findings_ontology
from api.config import LLM_BACKEND
from api.models.common import (
    AssignGraphRequest, GraphMeta, GraphRole,
    ProjectCreate, ProjectOut,
)
# Reuse functional entry-point logic from coverage router
from api.routers.coverage import (
    _functional_entry_points,
    _bfs_from,
    _is_test_node,
    _TEST_FILE_PAT,
    _COVERAGE_RELS,
    _get_edge_rel,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_meta(row) -> GraphMeta:
    data = {k: row[k] for k in row.keys()}
    data.setdefault("graph_role", "source")
    data.setdefault("project_id", None)
    return GraphMeta(**data)


def _require_project(project_id: str):
    row = database.get_project(project_id)
    if not row:
        raise HTTPException(404, f"Project {project_id!r} not found")
    return row


def _require_ready_graph(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    if not storage.graph_exists(graph_id):
        raise HTTPException(
            409,
            f"Graph {graph_id!r} has no on-disk data. Re-ingest or run update.",
        )
    return row


def _build_project_out(project_id: str) -> ProjectOut:
    row = _require_project(project_id)
    graphs = [_row_to_meta(g) for g in database.get_project_graphs(project_id)]
    return ProjectOut(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        graphs=graphs,
    )


# ── Cross-graph label matching ────────────────────────────────────────────────

def _cross_graph_match_entry_points(
    G_source: nx.Graph,
    G_test: nx.Graph,
    entry_pts: dict,
) -> set[str]:
    """
    Match entry point labels from G_source against labels referenced in G_test.
    Returns the set of entry point node IDs that are covered by the test graph.
    """
    ep_label_idx: dict[str, str] = {
        ep["label"].strip().lower().rstrip("()"): nid
        for nid, ep in entry_pts.items()
    }

    test_labels: set[str] = set()
    for nid, d in G_test.nodes(data=True):
        lbl = d.get("label", "").strip().lower().rstrip("()")
        if lbl:
            test_labels.add(lbl)
    for u, v, d in G_test.edges(data=True):
        rel = d.get("relation", "") if "relation" in d else ""
        if rel in _COVERAGE_RELS or not rel:
            for node in (u, v):
                lbl = G_test.nodes.get(node, {}).get("label", "").strip().lower().rstrip("()")
                if lbl:
                    test_labels.add(lbl)

    return {ep_label_idx[lbl] for lbl in test_labels if lbl in ep_label_idx}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ProjectOut, status_code=201, summary="Create a project")
def create_project(req: ProjectCreate):
    """
    Create a named project to group graphs by role (source / test / ci / cd).
    Then ingest repos with `project_id` set, or use POST /projects/{id}/graphs.
    """
    pid = str(uuid.uuid4())
    database.insert_project(pid, req.name, req.description)
    return _build_project_out(pid)


@router.get("", response_model=list[ProjectOut], summary="List all projects")
def list_projects():
    rows = database.list_projects()
    return [_build_project_out(r["id"]) for r in rows]


@router.get("/personas", summary="Personas for project AI search")
def get_search_personas():
    """Audience modes for POST/GET /projects/{id}/ask (developer, architect, security, …)."""
    return {"personas": list_personas()}


@router.get("/{project_id}", response_model=ProjectOut, summary="Get project details")
def get_project(project_id: str):
    return _build_project_out(project_id)


@router.delete("/{project_id}", summary="Delete a project and all its graphs")
def delete_project(project_id: str):
    _require_project(project_id)
    graph_ids = database.delete_project_cascade(project_id)
    for gid in graph_ids:
        storage.delete_graph(gid)
    return {
        "ok": True,
        "message": f"Project {project_id} deleted",
        "graphs_deleted": len(graph_ids),
    }


@router.get("/{project_id}/graphs", summary="List graphs in a project")
def list_project_graphs(project_id: str):
    _require_project(project_id)
    graphs = [_row_to_meta(g) for g in database.get_project_graphs(project_id)]
    by_role: dict[str, list] = defaultdict(list)
    for g in graphs:
        by_role[g.graph_role.value].append(g)
    return {
        "project_id": project_id,
        "total": len(graphs),
        "by_role": dict(by_role),
    }


@router.post("/{project_id}/graphs", summary="Assign graph to project (same-project only)")
def assign_graph(project_id: str, req: AssignGraphRequest):
    """
    Re-attach a graph that already belongs to this project (e.g. change role).
    Graphs cannot be moved between projects — ingest a new graph per project instead.
    """
    _require_project(project_id)
    row = _require_ready_graph(req.graph_id)
    current_project = row["project_id"]
    if current_project and current_project != project_id:
        raise HTTPException(
            403,
            f"Graph belongs to another project ({current_project!r}). "
            "Delete and re-ingest under this project instead.",
        )
    if not current_project:
        raise HTTPException(
            400,
            "Orphan graphs cannot be assigned. Use POST /graphs with project_id to ingest.",
        )
    existing = database.get_graph_for_project_role(project_id, req.graph_role.value)
    if existing and existing["id"] != req.graph_id:
        raise HTTPException(
            409,
            f"Role '{req.graph_role.value}' is already filled by '{existing['name']}'.",
        )
    database.assign_graph_to_project(req.graph_id, project_id, req.graph_role.value)
    return {
        "ok": True,
        "graph_id": req.graph_id,
        "project_id": project_id,
        "role": req.graph_role.value,
    }


@router.delete("/{project_id}/graphs/{graph_id}", summary="Delete a graph from this project")
def delete_project_graph(project_id: str, graph_id: str):
    """Delete a graph that belongs to this project (storage + DB)."""
    _require_project(project_id)
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["project_id"] != project_id:
        raise HTTPException(403, "Graph does not belong to this project")
    storage.delete_graph(graph_id)
    database.delete_graph_row(graph_id)
    return {"ok": True, "message": f"Graph {graph_id} deleted from project"}


@router.get("/{project_id}/coverage", response_model=dict, summary="Functional coverage: entry-point vs test suite")
def project_coverage(project_id: str, limit: int = 50):
    """
    Compute **functional coverage** for the project.

    **What it measures:**
    Entry points are API handlers, CLI commands, exported service methods — the
    user-visible *features* of the codebase.  A feature is "covered" when at
    least one test in the test suite exercises it (directly calls or imports it).

    **Gap = entry points not reached by any test** — these are untested features,
    not just untested helper functions.

    **Two strategies, combined:**
    1. **In-graph**: test nodes already inside the source graph reach entry points
       via BFS through calls/imports edges.
    2. **Cross-graph** (when a `role=test` graph exists): label-matching maps test
       graph nodes to source entry-point labels.

    Requires at least one `role=source` graph.  For accurate results also add a
    `role=test` graph via `POST /projects/{id}/graphs`.
    """
    _require_project(project_id)
    graphs = database.get_project_graphs(project_id)
    by_role: dict[str, list] = defaultdict(list)
    for g in graphs:
        by_role[g["graph_role"] or "source"].append(g)

    source_graphs = by_role.get("source", [])
    test_graphs   = by_role.get("test",   [])

    if not source_graphs:
        raise HTTPException(400, "No 'source' graph in project. Ingest production code first.")

    loadable_source = loadable_graphs(source_graphs)
    if not loadable_source:
        summary = ", ".join(f"{g['name']!r} ({g['status']})" for g in source_graphs)
        raise HTTPException(
            409,
            "No loadable source graph — ingestion may have failed or is still running. "
            f"Current source slot(s): {summary}. Re-ingest or update, then retry.",
        )

    # Merge multiple ready source graphs
    G_source = engine.load_graph(loadable_source[0]["id"])
    for sg in loadable_source[1:]:
        G_source = nx.compose(G_source, engine.load_graph(sg["id"]))

    # ── Identify functional entry points ─────────────────────────────────────
    entry_pts = _functional_entry_points(G_source)

    # ── Strategy 1: in-graph test node BFS ───────────────────────────────────
    in_graph_test_ids = {
        nid for nid, d in G_source.nodes(data=True) if _is_test_node(d)
    }
    reachable_in_graph = _bfs_from(G_source, in_graph_test_ids) if in_graph_test_ids else set()
    covered_in_graph   = {nid for nid in entry_pts if nid in reachable_in_graph}

    # ── Strategy 2: cross-graph label matching ────────────────────────────────
    test_info: list[dict] = []
    covered_cross: set[str] = set()
    for tg in loadable_graphs(test_graphs):
        G_test = engine.load_graph(tg["id"])
        test_info.append({
            "graph_id": tg["id"],
            "name": tg["name"],
            "node_count": G_test.number_of_nodes(),
            "edge_count": G_test.number_of_edges(),
        })
        matched = _cross_graph_match_entry_points(G_source, G_test, entry_pts)
        covered_cross.update(matched)

    # Combined actual coverage
    actually_covered = covered_in_graph | covered_cross
    coverage_gap     = set(entry_pts) - actually_covered

    func_pct = round(len(actually_covered) / max(len(entry_pts), 1) * 100, 1)

    def _ep_info(nid: str) -> dict:
        ep = entry_pts[nid]
        return {
            "id": nid,
            "label": ep["label"],
            "source_file": ep["source_file"],
            "entry_type": ep["entry_type"],
            "degree": ep["degree"],
            "risk": "critical" if ep["degree"] > 15 else "high" if ep["degree"] > 6 else "medium",
        }

    gaps_ranked = sorted([_ep_info(n) for n in coverage_gap], key=lambda x: -x["degree"])

    return {
        "project_id": project_id,
        "source_graphs": [sg["id"] for sg in loadable_source],
        "test_graphs": [tg["id"] for tg in test_graphs],
        "source_graphs_pending": [
            sg["id"]
            for sg in source_graphs
            if sg["id"] not in {g["id"] for g in loadable_source}
        ],
        "test_graph_info": test_info,

        # Functional coverage (primary)
        "functional_coverage_pct": func_pct,
        "grade": "A" if func_pct >= 80 else "B" if func_pct >= 60 else "C" if func_pct >= 40 else "D" if func_pct >= 20 else "F",
        "entry_points_total": len(entry_pts),
        "entry_points_covered": len(actually_covered),
        "entry_points_uncovered": len(coverage_gap),

        # Gap detail: each = one untested feature/flow
        "coverage_gap": gaps_ranked[:limit],

        # Coverage source breakdown
        "covered_by_in_graph_tests": len(covered_in_graph),
        "covered_by_cross_graph": len(covered_cross - covered_in_graph),

        "warning": (
            None if test_graphs else
            "No 'test' role graph in project. Ingest your regression test repo with "
            "role='test' for cross-graph functional coverage analysis. "
            "Currently using in-graph test-file detection only."
        ),
        "note": (
            "Functional coverage measures entry points (API handlers, CLI commands, "
            "public service methods) — not individual helper functions. "
            "One covered entry point = one tested user-visible feature flow."
        ),
    }


@router.get("/{project_id}/search", response_model=dict, summary="Search all project graphs (no LLM)")
def project_search_route(
    project_id: str,
    q: str,
    mode: str = "bfs",
    depth: int = 3,
    roles: str | None = None,
    top_n: int = 8,
):
    """
    Natural-language search across every ready graph in the project (source, test, CI, CD).
    Returns ranked nodes with graph role and name — use /ask for an AI-generated answer.
    """
    _require_project(project_id)
    role_list = [r.strip() for r in roles.split(",")] if roles else None
    return project_search(
        project_id, q, mode=mode, depth=min(depth, 6), roles=role_list, top_n=top_n
    )


@router.get("/{project_id}/map", response_model=dict, summary="Product map — areas, capabilities, findings")
def project_map_route(project_id: str):
    _require_project(project_id)
    return get_product_map(project_id)


@router.get("/{project_id}/findings", response_model=dict, summary="Findings register (human-readable)")
def project_findings_route(project_id: str, category: str | None = None, limit: int = 30):
    _require_project(project_id)
    pkb = pkb_storage.load_pkb(project_id)
    if not pkb:
        raise HTTPException(
            409,
            "Refresh project understanding first (POST /projects/{id}/synthesize).",
        )
    return get_findings_ontology(project_id, category=category, limit=limit)


@router.post("/{project_id}/synthesize", response_model=dict, summary="Refresh project understanding")
def project_synthesize_route(
    project_id: str,
    use_llm: bool = True,
    backend: str | None = None,
):
    """Build product map: areas, capabilities, findings, journeys from indexed repositories."""
    _require_project(project_id)
    from api.config import LLM_BACKEND as default_backend
    pkb = synthesize_project(project_id, backend=backend or default_backend, use_llm=use_llm)
    return {"ok": True, "project_id": project_id, "meta": pkb.get("meta"), "metrics": pkb.get("metrics")}


@router.get("/{project_id}/briefing", response_model=dict, summary="Project intelligence briefing")
def project_briefing_route(project_id: str):
    _require_project(project_id)
    return get_briefing(project_id)


@router.get("/{project_id}/dna", response_model=dict, summary="Code Project DNA — full AI summary")
def project_dna_route(project_id: str):
    _require_project(project_id)
    return get_project_dna(project_id)


@router.post("/{project_id}/dna/generate", response_model=dict, summary="Generate Code Project DNA (LLM narrative)")
def project_dna_generate_route(
    project_id: str,
    use_llm: bool = True,
    backend: str | None = None,
):
    """Build the complete AI-written project summary. Requires prior synthesize."""
    _require_project(project_id)
    from api.config import LLM_BACKEND as default_backend
    try:
        return generate_project_dna(
            project_id,
            backend=backend or default_backend,
            use_llm=use_llm,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{project_id}/risks", response_model=dict, summary="Findings (alias)")
def project_risks_route(project_id: str, limit: int = 30):
    _require_project(project_id)
    return get_findings_ontology(project_id, limit=limit)


@router.get("/{project_id}/capabilities", response_model=dict, summary="Capabilities with test status")
def project_capabilities_route(project_id: str, uncovered_only: bool = False, limit: int = 50):
    _require_project(project_id)
    data = get_product_map(project_id)
    if not data.get("ready"):
        raise HTTPException(409, "Refresh project understanding first.")
    caps = data.get("capabilities", [])
    if uncovered_only:
        caps = [c for c in caps if c.get("test_status_key") == "untested"]
    return {
        "project_id": project_id,
        "capabilities": caps[:limit],
        "health": data.get("health"),
    }


@router.get("/{project_id}/scenarios", response_model=dict, summary="Pre-built question packs by persona")
def project_scenarios_route(project_id: str):
    _require_project(project_id)
    return {"project_id": project_id, "scenarios": list_scenarios().get("scenarios", SCENARIO_PACKS)}


@router.post("/{project_id}/visit", response_model=dict, summary="Record project visit for delta briefing")
def project_visit_route(project_id: str):
    _require_project(project_id)
    ts = pkb_storage.record_visit(project_id)
    return {"ok": True, "visited_at": ts}


@router.get("/{project_id}/delta", response_model=dict, summary="Changes since last visit / synthesis")
def project_delta_route(project_id: str):
    _require_project(project_id)
    return compute_delta(project_id)


@router.get("/{project_id}/memory", response_model=dict, summary="Project Q&A memory")
def project_memory_list(project_id: str, limit: int = 20):
    _require_project(project_id)
    return {"project_id": project_id, "items": pkb_storage.list_memory(project_id, limit=limit)}


@router.get("/{project_id}/ask", response_model=dict, summary="AI Q&A across all project graphs")
def project_ask_route(
    project_id: str,
    q: str,
    persona: str = "developer",
    mode: str = "bfs",
    depth: int = 3,
    roles: str | None = None,
    backend: str | None = None,
):
    """
    Ask any question about the project using knowledge from all ingested repositories.

    Personas: developer, architect, security, qa, executive, onboarding.
    Optional roles filter: comma list e.g. roles=source,test
    """
    _require_project(project_id)
    role_list = [r.strip() for r in roles.split(",")] if roles else None
    return project_ask(
        project_id,
        q,
        persona=persona,
        mode=mode,
        depth=min(depth, 6),
        roles=role_list,
        backend=backend or LLM_BACKEND,
    )


@router.get("/{project_id}/summary", response_model=dict, summary="Cross-role project health summary")
def project_summary(project_id: str):
    """
    Aggregate health view across all graphs in the project.
    Shows what roles are present, graph statuses, and quick stats.
    """
    _require_project(project_id)
    graphs = database.get_project_graphs(project_id)
    by_role: dict[str, list] = defaultdict(list)
    for g in graphs:
        role = g["graph_role"] or "source"
        by_role[role].append({
            "id": g["id"],
            "name": g["name"],
            "status": g["status"],
            "node_count": g["node_count"],
            "edge_count": g["edge_count"],
        })

    missing_roles = [r for r in ("source", "test", "ci", "cd") if r not in by_role]
    completeness = round((4 - len(missing_roles)) / 4 * 100)

    return {
        "project_id": project_id,
        "completeness_pct": completeness,
        "present_roles": list(by_role.keys()),
        "missing_roles": missing_roles,
        "graphs_by_role": dict(by_role),
        "total_graphs": len(graphs),
        "recommendations": [
            f"Add a '{role}' graph to enable full {role.upper()} analysis"
            for role in missing_roles
        ],
    }
