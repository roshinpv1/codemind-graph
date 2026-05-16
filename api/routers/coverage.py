"""CodeMind Coverage — structural test coverage analysis via graph reachability.

Coverage modes
--------------
FUNCTIONAL (default, recommended)
    Analyses *entry points* — nodes that external callers invoke but that
    nothing in production code itself calls.  These are API handlers, CLI
    commands, exported service methods, public module interfaces.  A feature
    is "covered" when at least one test reaches its entry point.  This is
    close to what QA/regression suites exercise: user-visible behaviour, not
    internal plumbing.

UNIT
    Counts every production node individually.  Useful for understanding
    raw reachability but produces noisy scores because private helpers,
    generated code, and glue functions all count equally.

For multi-repo projects (separate source/test repos) use:
    POST /projects              — create project
    POST /projects/{id}/graphs  — assign graph roles
    GET  /projects/{id}/coverage — expected vs actual with cross-graph matching
"""
from __future__ import annotations
import re
from collections import defaultdict
from typing import Literal

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core import engine, database
from api.config import LLM_BACKEND

router = APIRouter(prefix="/graphs/{graph_id}/coverage", tags=["Coverage"])


# ── Shared patterns ───────────────────────────────────────────────────────────

_TEST_FILE_PAT = re.compile(
    r"(^|[\\/])(test_|_test\.|\.test\.|\.spec\.|spec_|tests[\\/]|__tests__[\\/]|"
    r"conftest|fixtures?[\\/]|e2e[\\/]|integration[\\/]test)",
    re.IGNORECASE,
)
_TEST_LABEL_PAT = re.compile(
    r"^(test_|it_|describe_|should_|given_|when_|then_|setup_|teardown_|before_|after_|fixture_)",
    re.IGNORECASE,
)

# File/path patterns that indicate a public-facing module
_ENTRY_FILE_PAT = re.compile(
    r"(routes?|views?|controllers?|handlers?|endpoints?|api|cli|commands?|"
    r"main|__main__|app|server|tasks?|jobs?|workers?)",
    re.IGNORECASE,
)

# Private-symbol prefix (Python / JS convention)
_PRIVATE_PAT = re.compile(r"^_[^_]")

# Edge relations that mean "A uses B"
_COVERAGE_RELS = {"calls", "imports", "imports_from", "uses", "references", "inherits"}

# Pure container node labels (file-level nodes, not callable units)
_CONTAINER_PAT = re.compile(r"\.(py|js|ts|tsx|jsx|rb|java|go|cs|cpp|c|rs|kt|swift)$", re.IGNORECASE)


# ── Node classifiers ──────────────────────────────────────────────────────────

def _is_test_node(data: dict) -> bool:
    src   = data.get("source_file", "")
    label = data.get("label", "")
    return bool(_TEST_FILE_PAT.search(src) or _TEST_LABEL_PAT.match(label))


def _is_prod_node(data: dict) -> bool:
    return (
        not _is_test_node(data)
        and data.get("file_type") in ("code", "document", "concept", None, "")
    )


def _is_container_node(nid: str, data: dict) -> bool:
    """File-level nodes that just own other nodes (no real executable logic)."""
    label = data.get("label", "")
    return bool(_CONTAINER_PAT.search(label))


# ── Functional entry-point detection ─────────────────────────────────────────

def _functional_entry_points(G: nx.Graph) -> dict[str, dict]:
    """
    Return production nodes that are *functional entry points*:
    places where external execution begins (API handlers, CLI commands,
    exported service methods, public module interfaces).

    A node qualifies as a functional entry point if ANY of:
      1. Zero in-degree from *production* code (nothing in prod calls it)
         AND the node has at least one outgoing call (it calls other things)
      2. Lives in a file whose name indicates a public interface
         (routes, api, cli, handlers, main, server, workers …)
      3. Is a public symbol (no leading `_`) in a module that is directly
         imported by other modules (i.e., the module file-node has in-degree > 0)

    Excludes: test nodes, pure file-container nodes, isolated leaf nodes with
    no connections at all.
    """
    # Separate prod node ids from test node ids
    prod_ids: set[str] = {
        nid for nid, d in G.nodes(data=True)
        if _is_prod_node(d) and not _is_container_node(nid, d)
    }
    test_ids: set[str] = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}

    # Build a set of prod-to-prod predecessor counts (ignoring test callers)
    prod_in_degree: dict[str, int] = {nid: 0 for nid in prod_ids}
    for u, v, edata in G.edges(data=True):
        if u in prod_ids and v in prod_ids:
            rel = _get_edge_rel(G, u, v)
            if rel in _COVERAGE_RELS or not rel:
                prod_in_degree[v] = prod_in_degree.get(v, 0) + 1

    entry_points: dict[str, dict] = {}

    for nid in prod_ids:
        d     = G.nodes[nid]
        src   = d.get("source_file", "")
        label = d.get("label", "")
        if not label:
            continue

        out_deg    = G.out_degree(nid) if G.is_directed() else G.degree(nid)
        in_from_prod = prod_in_degree.get(nid, 0)
        total_deg  = G.degree(nid)

        # Rule 1: zero callers from production AND calls into other code
        is_zero_in = in_from_prod == 0 and out_deg >= 1
        # Rule 2: lives in a public-interface file
        is_api_file = bool(_ENTRY_FILE_PAT.search(src))
        # Rule 3: public symbol in an imported module
        is_public = (
            not _PRIVATE_PAT.match(label)
            and total_deg >= 2
            and not _is_container_node(nid, d)
        )

        if is_zero_in or is_api_file or is_public:
            entry_points[nid] = {
                "id": nid,
                "label": label,
                "source_file": src,
                "module": src.split("/")[-1] if src else "",
                "degree": total_deg,
                "out_degree": out_deg,
                "prod_in_degree": in_from_prod,
                "is_api_file": is_api_file,
                "is_zero_in": is_zero_in,
                "is_public": is_public,
                "entry_type": (
                    "api_handler"  if is_api_file else
                    "public_entry" if is_zero_in  else
                    "public_symbol"
                ),
            }

    return entry_points


# ── BFS helpers ───────────────────────────────────────────────────────────────

def _get_edge_rel(G: nx.Graph, u: str, v: str) -> str:
    try:
        raw = G[u][v]
        if isinstance(raw, dict):
            if "relation" in raw:
                return raw["relation"]
            for sub in raw.values():
                if isinstance(sub, dict) and "relation" in sub:
                    return sub["relation"]
    except Exception:
        pass
    return ""


def _bfs_from(G: nx.Graph, starts: set[str]) -> set[str]:
    """BFS outward through coverage-relevant edges."""
    visited = set(starts)
    queue   = list(starts)
    while queue:
        node = queue.pop(0)
        nbrs = list(G.successors(node)) if G.is_directed() else list(G.neighbors(node))
        for nb in nbrs:
            if nb not in visited:
                rel = _get_edge_rel(G, node, nb)
                if rel in _COVERAGE_RELS or not rel:
                    visited.add(nb)
                    queue.append(nb)
    return visited


def _call_chain(G: nx.Graph, start: str, max_depth: int = 4) -> list[str]:
    """BFS call chain labels from an entry point (breadth-first, bounded)."""
    visited: set[str] = {start}
    queue: list[tuple[str, int]] = [(start, 0)]
    chain: list[str] = []
    while queue:
        node, depth = queue.pop(0)
        if depth > max_depth:
            break
        lbl = G.nodes[node].get("label", node)
        if lbl and node != start:
            chain.append(lbl)
        if depth < max_depth:
            for nb in (G.successors(node) if G.is_directed() else G.neighbors(node)):
                if nb not in visited:
                    rel = _get_edge_rel(G, node, nb)
                    if rel in _COVERAGE_RELS or not rel:
                        visited.add(nb)
                        queue.append((nb, depth + 1))
    return chain[:12]


# ── Unit-level coverage helper (kept for /gaps /hotspots /files /unit) ────────

def _compute_unit_coverage(G: nx.Graph) -> dict:
    """BFS from all test nodes → reachable production nodes (unit granularity)."""
    test_nodes: set[str] = set()
    prod_nodes: set[str] = set()

    for nid, data in G.nodes(data=True):
        if _is_test_node(data):
            test_nodes.add(nid)
        elif _is_prod_node(data):
            prod_nodes.add(nid)

    if not test_nodes:
        return {
            "test_nodes": 0, "prod_nodes": len(prod_nodes),
            "covered_nodes": 0, "uncovered_nodes": len(prod_nodes),
            "coverage_pct": 0.0, "covered": [], "uncovered": [],
            "test_files": [],
            "warning": "No test files detected. Expected: test_*, *_test.*, *.spec.*, tests/ directory.",
        }

    covered: set[str] = set()
    visited  = set(test_nodes)
    queue    = list(test_nodes)

    while queue:
        node = queue.pop(0)
        nbrs = list(G.successors(node)) if G.is_directed() else list(G.neighbors(node))
        for nb in nbrs:
            if nb in visited:
                continue
            rel = _get_edge_rel(G, node, nb)
            if rel in _COVERAGE_RELS or not rel:
                visited.add(nb)
                queue.append(nb)
                if nb in prod_nodes:
                    covered.add(nb)

    uncovered = prod_nodes - covered
    pct = round(len(covered) / max(len(prod_nodes), 1) * 100, 1)

    test_files = sorted({G.nodes[n].get("source_file", "") for n in test_nodes if G.nodes[n].get("source_file")})

    def _ns(nid: str) -> dict:
        d = G.nodes[nid]
        return {"id": nid, "label": d.get("label", nid), "source_file": d.get("source_file", ""), "degree": G.degree(nid), "community": d.get("community")}

    return {
        "test_nodes": len(test_nodes), "prod_nodes": len(prod_nodes),
        "covered_nodes": len(covered), "uncovered_nodes": len(uncovered),
        "coverage_pct": pct, "test_files": test_files,
        "covered":   sorted([_ns(n) for n in covered],   key=lambda x: -x["degree"]),
        "uncovered": sorted([_ns(n) for n in uncovered], key=lambda x: -x["degree"]),
    }


# ── Route guards ──────────────────────────────────────────────────────────────

def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=dict, summary="Functional + unit coverage scores")
def coverage_summary(graph_id: str):
    """
    Returns **two** coverage views:

    **Functional coverage** *(primary — what QA/regression tests care about)*
    Measures what fraction of *entry points* are reached by any test.
    Entry points = API handlers, CLI commands, exported service methods,
    public module interfaces.  One covered entry point = one tested *feature flow*.

    **Unit coverage** *(secondary — raw reachability)*
    Counts every production node individually.  Useful for drill-down but
    less meaningful as a headline score since private helpers count equally.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    # ── Functional ───────────────────────────────────────────────────────────
    entry_pts   = _functional_entry_points(G)
    test_ids    = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
    reachable   = _bfs_from(G, test_ids) if test_ids else set()

    func_covered   = {nid for nid in entry_pts if nid in reachable}
    func_uncovered = set(entry_pts) - func_covered
    func_pct       = round(len(func_covered) / max(len(entry_pts), 1) * 100, 1)

    # ── Unit (broad) ─────────────────────────────────────────────────────────
    unit = _compute_unit_coverage(G)

    grade = lambda p: "A" if p >= 80 else "B" if p >= 60 else "C" if p >= 40 else "D" if p >= 20 else "F"

    return {
        "graph_id": graph_id,

        "functional": {
            "coverage_pct": func_pct,
            "grade": grade(func_pct),
            "entry_points_total": len(entry_pts),
            "entry_points_covered": len(func_covered),
            "entry_points_uncovered": len(func_uncovered),
            "description": "Fraction of entry-points (API handlers, CLI commands, public service methods) reached by tests",
        },

        "unit": {
            "coverage_pct": unit["coverage_pct"],
            "grade": grade(unit["coverage_pct"]),
            "prod_nodes_total": unit["prod_nodes"],
            "prod_nodes_covered": unit["covered_nodes"],
            "prod_nodes_uncovered": unit["uncovered_nodes"],
            "description": "Fraction of ALL production nodes reachable from tests (fine-grained, noisier)",
        },

        "test_nodes": unit["test_nodes"],
        "test_files": unit.get("test_files", []),
        "warning": unit.get("warning"),
        "tip": (
            "Use 'functional' score for regression/QA reporting. "
            "Use 'unit' score for fine-grained developer analysis. "
            "For multi-repo projects use GET /projects/{id}/coverage."
        ),
    }


@router.get("/functional", response_model=dict, summary="Functional entry-point coverage detail")
def coverage_functional(
    graph_id: str,
    mode: Literal["covered", "uncovered", "all"] = "all",
    group_by: Literal["file", "entry_type"] = "file",
    limit: int = 100,
):
    """
    Per-entry-point functional coverage.

    Each row is one *functional entry point* (an API handler, CLI command,
    exported service method, or zero-in-degree public symbol) with:
    - whether it is covered by any test
    - the call chain it triggers (up to 4 hops)
    - grouping by file or entry type

    **This is the right view for QA gap analysis and regression planning.**
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    entry_pts = _functional_entry_points(G)
    test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
    reachable = _bfs_from(G, test_ids) if test_ids else set()

    # Reverse map: which test nodes reach each entry point?
    # (only computed if needed — costs O(test_nodes × BFS) )
    test_covers: dict[str, list[str]] = defaultdict(list)
    for tn in test_ids:
        tn_reachable = _bfs_from(G, {tn})
        for ep_id in entry_pts:
            if ep_id in tn_reachable:
                tn_label = G.nodes[tn].get("label", tn)
                test_covers[ep_id].append(tn_label)

    rows = []
    for nid, ep in entry_pts.items():
        is_covered = nid in reachable
        if mode == "covered"   and not is_covered: continue
        if mode == "uncovered" and is_covered:     continue

        call_chain = _call_chain(G, nid) if is_covered else []
        rows.append({
            **ep,
            "covered": is_covered,
            "covering_tests": test_covers.get(nid, [])[:5],
            "call_chain": call_chain,
            "risk": (
                "none"     if is_covered else
                "critical" if ep["degree"] > 15 else
                "high"     if ep["degree"] > 6  else
                "medium"
            ),
        })

    # Sort: uncovered first, then by degree desc
    rows.sort(key=lambda r: (r["covered"], -r["degree"]))

    # Group
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        key = r.get("source_file" if group_by == "file" else "entry_type", "unknown")
        groups[key].append(r)

    covered_count   = sum(1 for r in rows if r["covered"])
    uncovered_count = len(rows) - covered_count
    func_pct = round(covered_count / max(len(rows), 1) * 100, 1)

    return {
        "graph_id": graph_id,
        "functional_coverage_pct": func_pct,
        "grade": "A" if func_pct >= 80 else "B" if func_pct >= 60 else "C" if func_pct >= 40 else "D" if func_pct >= 20 else "F",
        "entry_points_total": len(rows),
        "entry_points_covered": covered_count,
        "entry_points_uncovered": uncovered_count,
        "mode": mode,
        "group_by": group_by,
        "grouped": {k: v[:limit] for k, v in groups.items()},
        "all_entry_points": rows[:limit],
    }


@router.get("/gaps", response_model=dict, summary="Uncovered functional entry points and unit gaps")
def coverage_gaps(
    graph_id: str,
    mode: Literal["functional", "unit"] = "functional",
    limit: int = 50,
):
    """
    Coverage gaps.

    - `mode=functional` *(default)*: returns uncovered entry points only.
      Each represents a whole untested feature flow.
    - `mode=unit`: returns all uncovered production nodes (noisy but complete).
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    if mode == "functional":
        entry_pts = _functional_entry_points(G)
        test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
        reachable = _bfs_from(G, test_ids) if test_ids else set()

        gaps = sorted(
            [ep for nid, ep in entry_pts.items() if nid not in reachable],
            key=lambda x: -x["degree"],
        )
        return {
            "graph_id": graph_id,
            "mode": "functional",
            "total_entry_points": len(entry_pts),
            "uncovered_entry_points": len(gaps),
            "gaps": gaps[:limit],
            "note": "Each gap = one untested feature flow / API surface entry",
        }
    else:
        unit = _compute_unit_coverage(G)
        return {
            "graph_id": graph_id,
            "mode": "unit",
            "total_gaps": unit["uncovered_nodes"],
            "coverage_pct": unit["coverage_pct"],
            "gaps": unit.get("uncovered", [])[:limit],
        }


@router.get("/critical", response_model=dict, summary="Highest-risk uncovered entry points")
def coverage_critical(graph_id: str, top_n: int = 20):
    """
    Returns uncovered functional entry points sorted by degree
    (the most-connected untested entry points are the highest risk).
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    entry_pts = _functional_entry_points(G)
    test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
    reachable = _bfs_from(G, test_ids) if test_ids else set()

    uncovered = sorted(
        [ep for nid, ep in entry_pts.items() if nid not in reachable],
        key=lambda x: -x["degree"],
    )

    for ep in uncovered[:top_n]:
        nid = ep["id"]
        ep["call_chain"] = _call_chain(G, nid, max_depth=3)
        ep["dependents"]  = G.in_degree(nid) if G.is_directed() else 0
        ep["risk"] = "critical" if ep["degree"] > 15 else "high" if ep["degree"] > 6 else "medium"

    total_eps   = len(entry_pts)
    covered_eps = total_eps - len(uncovered)
    func_pct    = round(covered_eps / max(total_eps, 1) * 100, 1)

    return {
        "graph_id": graph_id,
        "functional_coverage_pct": func_pct,
        "grade": "A" if func_pct >= 80 else "B" if func_pct >= 60 else "C" if func_pct >= 40 else "D" if func_pct >= 20 else "F",
        "critical_gaps": uncovered[:top_n],
        "total_entry_points": total_eps,
        "covered_entry_points": covered_eps,
        "total_uncovered": len(uncovered),
    }


@router.get("/hotspots", response_model=dict, summary="Most-tested entry points")
def coverage_hotspots(graph_id: str, top_n: int = 20):
    """
    Entry points covered by the most distinct test nodes.
    High counts indicate well-tested features; very high counts may indicate
    brittle tests or over-specification of a single flow.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    entry_pts = _functional_entry_points(G)
    test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}

    test_reach: dict[str, set[str]] = defaultdict(set)
    for tn in test_ids:
        tn_reachable = _bfs_from(G, {tn})
        for ep_id in entry_pts:
            if ep_id in tn_reachable:
                test_reach[ep_id].add(tn)

    hotspots = sorted(
        [
            {
                **entry_pts[nid],
                "test_count":  len(tests),
                "covering_tests": [G.nodes[t].get("label", t) for t in list(tests)[:5]],
            }
            for nid, tests in test_reach.items()
            if nid in entry_pts
        ],
        key=lambda x: -x["test_count"],
    )

    return {
        "graph_id": graph_id,
        "hotspots": hotspots[:top_n],
        "total_covered_entry_points": len(test_reach),
    }


@router.get("/files", response_model=dict, summary="Per-file functional coverage breakdown")
def coverage_files(graph_id: str, mode: Literal["functional", "unit"] = "functional"):
    """
    Per-source-file coverage breakdown.

    In `functional` mode each file is scored by what fraction of its
    *entry points* are covered — not raw node counts.
    In `unit` mode every node counts.
    """
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    if mode == "functional":
        entry_pts = _functional_entry_points(G)
        test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
        reachable = _bfs_from(G, test_ids) if test_ids else set()

        file_stats: dict[str, dict] = {}
        for nid, ep in entry_pts.items():
            src = ep["source_file"] or "unknown"
            if src not in file_stats:
                file_stats[src] = {"file": src, "total": 0, "covered": 0, "uncovered_labels": []}
            file_stats[src]["total"] += 1
            if nid in reachable:
                file_stats[src]["covered"] += 1
            else:
                file_stats[src]["uncovered_labels"].append(ep["label"])
    else:
        unit = _compute_unit_coverage(G)
        covered_ids   = {n["id"] for n in unit.get("covered",   [])}
        uncovered_ids = {n["id"] for n in unit.get("uncovered", [])}
        file_stats = {}
        for nid, d in G.nodes(data=True):
            src = d.get("source_file", "")
            if not src or _is_test_node(d):
                continue
            if nid not in covered_ids and nid not in uncovered_ids:
                continue
            if src not in file_stats:
                file_stats[src] = {"file": src, "total": 0, "covered": 0, "uncovered_labels": []}
            file_stats[src]["total"] += 1
            if nid in covered_ids:
                file_stats[src]["covered"] += 1
            else:
                file_stats[src]["uncovered_labels"].append(d.get("label", nid))

    result = []
    for src, stats in file_stats.items():
        total, covered = stats["total"], stats["covered"]
        pct = round(covered / max(total, 1) * 100, 1)
        result.append({
            "file":              src,
            "total_entry_points" if mode == "functional" else "total_nodes": total,
            "covered":           covered,
            "uncovered":         total - covered,
            "coverage_pct":      pct,
            "grade":             "A" if pct >= 80 else "B" if pct >= 60 else "C" if pct >= 40 else "D" if pct >= 20 else "F",
            "uncovered_labels":  stats["uncovered_labels"][:8],
        })

    result.sort(key=lambda x: x["coverage_pct"])
    overall = round(sum(r["covered"] for r in result) / max(sum(r.get("total_entry_points", r.get("total_nodes", 0)) for r in result), 1) * 100, 1)

    return {
        "graph_id": graph_id,
        "mode": mode,
        "overall_coverage_pct": overall,
        "files": result,
        "worst_files": result[:10],
    }


class CompareRequest(BaseModel):
    test_graph_id: str
    prod_graph_id: str | None = None


@router.post("/compare", response_model=dict, summary="Cross-graph functional coverage (separate test repo)")
def coverage_compare(graph_id: str, req: CompareRequest):
    """
    Cross-graph functional coverage for codebases with a separate test repository.

    Matches entry points in the production graph against labels referenced in the
    test graph to compute which features are exercised by the external test suite.
    """
    _require_ready(graph_id)
    prod_gid = req.prod_graph_id or graph_id
    test_gid = req.test_graph_id

    row_test = database.get_graph(test_gid)
    if not row_test:
        raise HTTPException(404, f"Test graph {test_gid!r} not found")
    if row_test["status"] != "ready":
        raise HTTPException(409, f"Test graph not ready — status: {row_test['status']}")

    G_prod = engine.load_graph(prod_gid)
    G_test = engine.load_graph(test_gid)

    entry_pts = _functional_entry_points(G_prod)

    # Build label index for entry points only
    ep_label_idx: dict[str, str] = {
        ep["label"].lower().rstrip("()"): nid
        for nid, ep in entry_pts.items()
    }

    # Collect all labels referenced in the test graph
    test_labels: set[str] = set()
    for u, v, d in G_test.edges(data=True):
        rel = d.get("relation", "") if "relation" in d else ""
        if rel in _COVERAGE_RELS or not rel:
            for nid in (u, v):
                lbl = G_test.nodes.get(nid, {}).get("label", "").lower().rstrip("()")
                if lbl:
                    test_labels.add(lbl)

    matched: dict[str, str] = {
        lbl: ep_label_idx[lbl] for lbl in test_labels if lbl in ep_label_idx
    }

    covered_eps   = len(matched)
    total_eps     = len(entry_pts)
    func_pct      = round(covered_eps / max(total_eps, 1) * 100, 1)
    uncovered_eps = [ep for nid, ep in entry_pts.items() if ep["label"].lower().rstrip("()") not in matched]
    uncovered_eps.sort(key=lambda x: -x["degree"])

    return {
        "prod_graph_id":          prod_gid,
        "test_graph_id":          test_gid,
        "functional_coverage_pct": func_pct,
        "grade": "A" if func_pct >= 80 else "B" if func_pct >= 60 else "C" if func_pct >= 40 else "D" if func_pct >= 20 else "F",
        "total_entry_points":     total_eps,
        "covered_entry_points":   covered_eps,
        "uncovered_entry_points": len(uncovered_eps),
        "covered_labels":         sorted(matched.keys())[:50],
        "top_uncovered":          uncovered_eps[:20],
        "method": "functional_label_matching",
    }


@router.get("/narrative", response_model=dict, summary="LLM narrative: functional coverage quality")
def coverage_narrative(graph_id: str, backend: str | None = None):
    """LLM assessment of functional coverage quality and top gap priorities."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)

    entry_pts = _functional_entry_points(G)
    test_ids  = {nid for nid, d in G.nodes(data=True) if _is_test_node(d)}
    reachable = _bfs_from(G, test_ids) if test_ids else set()

    covered_eps   = {nid for nid in entry_pts if nid in reachable}
    uncovered_eps = sorted(
        [ep for nid, ep in entry_pts.items() if nid not in covered_eps],
        key=lambda x: -x["degree"],
    )[:10]
    func_pct = round(len(covered_eps) / max(len(entry_pts), 1) * 100, 1)

    gap_text = "\n".join(
        f"  - [{ep['entry_type']}] {ep['label']} (degree {ep['degree']}) in {ep['source_file']}"
        for ep in uncovered_eps
    ) or "  (none)"

    prompt = (
        f"You are a senior QA/engineering lead reviewing functional test coverage.\n\n"
        f"FUNCTIONAL COVERAGE SUMMARY:\n"
        f"  - Functional coverage: {func_pct}%\n"
        f"  - Entry points total: {len(entry_pts)}, covered: {len(covered_eps)}, uncovered: {len(uncovered_eps)}\n"
        f"  - Test files found: {len(test_ids)}\n\n"
        f"TOP UNCOVERED ENTRY POINTS (highest-risk, sorted by degree):\n{gap_text}\n\n"
        f"Write 4-6 sentences assessing functional coverage quality. "
        f"Identify which user-visible features or API surface are untested. "
        f"Give specific, actionable recommendations ordered by risk."
    )

    narrative = engine.llm_ask(prompt, backend=backend or LLM_BACKEND, max_tokens=500)
    return {
        "graph_id": graph_id,
        "functional_coverage_pct": func_pct,
        "narrative": narrative,
        "backend": backend or LLM_BACKEND,
    }
