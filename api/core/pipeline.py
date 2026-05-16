"""Extraction pipeline — wraps graphify internals to build a graph from a local path."""
from __future__ import annotations
import sys
import traceback
from pathlib import Path

from api.config import LLM_BACKEND
from api.core import storage, database


def run_extraction(
    graph_id: str,
    source_path: str,
    backend: str = LLM_BACKEND,
    dedup_llm: bool = False,
    use_semantic: bool = True,
) -> None:
    """Full extraction pipeline. Runs in a background thread."""
    try:
        database.upsert_graph(graph_id, status="running")
        _extract(graph_id, Path(source_path), backend, dedup_llm=dedup_llm, use_semantic=use_semantic)
        database.upsert_graph(graph_id, status="ready")
        row = database.get_graph(graph_id)
        if row and row["project_id"]:
            from api.core.project_synthesis import maybe_synthesize_project
            maybe_synthesize_project(row["project_id"], backend=backend)
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        print(f"[pipeline] graph {graph_id} failed: {exc}\n{tb}", file=sys.stderr)
        database.upsert_graph(graph_id, status="failed", error=str(exc)[:2000])


def _extract(
    graph_id: str,
    root: Path,
    backend: str,
    dedup_llm: bool = False,
    use_semantic: bool = True,
) -> None:
    # ── Step 1: detect files ────────────────────────────────────────────────
    from graphify.detect import detect, is_graphify_output_path
    detection = detect(root, include_graphify_memory=False)
    files_by_type = detection.get("files", {})

    # ── Step 2: AST extraction (code files — no LLM) ───────────────────────
    from graphify.extract import extract, collect_files
    code_paths: list[Path] = []
    for f in files_by_type.get("code", []):
        p = Path(f)
        if is_graphify_output_path(p, root):
            continue
        collected = collect_files(p, root=root) if p.is_dir() else [p]
        code_paths.extend(x for x in collected if not is_graphify_output_path(x, root))

    ast_result: dict = {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}
    if code_paths:
        ast_result = extract(code_paths, cache_root=root)
        print(f"[pipeline] AST: {len(ast_result['nodes'])} nodes, {len(ast_result['edges'])} edges")

    # ── Step 3: semantic extraction (docs/papers/images — LLM) ─────────────
    # detect() returns FileType.value keys: "document", "paper", "image", "video"
    semantic_files: list[Path] = []
    for ftype in ("document", "paper", "image"):
        for f in files_by_type.get(ftype, []):
            p = Path(f)
            if not is_graphify_output_path(p, root):
                semantic_files.append(p)

    sem_result: dict = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
    if semantic_files and not use_semantic:
        print(
            f"[pipeline] Semantic skipped (use_semantic=false): "
            f"{len(semantic_files)} document/image files not indexed"
        )
    if semantic_files and use_semantic:
        from graphify.llm import extract_corpus_parallel
        print(f"[pipeline] Semantic: {len(semantic_files)} files via {backend}")
        sem_result = extract_corpus_parallel(
            semantic_files,
            backend=backend,
            root=root,
            max_concurrency=2,
        )
        print(
            f"[pipeline] Semantic done: {len(sem_result['nodes'])} nodes, "
            f"{len(sem_result['edges'])} edges"
        )

    # ── Step 4: merge AST + semantic ────────────────────────────────────────
    seen_ids: set[str] = {n["id"] for n in ast_result["nodes"]}
    merged_nodes = list(ast_result["nodes"])
    for n in sem_result.get("nodes", []):
        if n["id"] not in seen_ids:
            merged_nodes.append(n)
            seen_ids.add(n["id"])

    extraction: dict = {
        "nodes": merged_nodes,
        "edges": ast_result["edges"] + sem_result.get("edges", []),
        "hyperedges": sem_result.get("hyperedges", []),
        "input_tokens": ast_result.get("input_tokens", 0) + sem_result.get("input_tokens", 0),
        "output_tokens": ast_result.get("output_tokens", 0) + sem_result.get("output_tokens", 0),
    }

    # ── Step 5: build NetworkX graph (build() runs dedup; build_from_json does not)
    from graphify.build import build
    dedup_llm_backend = backend if dedup_llm else None
    G = build([extraction], dedup=True, dedup_llm_backend=dedup_llm_backend)
    if G.number_of_nodes() == 0:
        raise RuntimeError("Extraction produced an empty graph — check source path and backend config")

    # ── Step 6: cluster ─────────────────────────────────────────────────────
    from graphify.cluster import cluster, score_all
    communities = cluster(G)
    cohesion = score_all(G, communities)

    # ── Step 7: analyze ─────────────────────────────────────────────────────
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    labels = {cid: f"Community {cid}" for cid in communities}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)

    # ── Step 8: generate report ─────────────────────────────────────────────
    from graphify.report import generate
    tokens = {
        "input": extraction.get("input_tokens", 0),
        "output": extraction.get("output_tokens", 0),
    }
    report_md = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, str(root), suggested_questions=questions)
    storage.report_path(graph_id).write_text(report_md, encoding="utf-8")

    # ── Step 9: export graph.json ────────────────────────────────────────────
    from graphify.export import to_json
    to_json(G, communities, str(storage.graph_json_path(graph_id)))

    # ── Step 9b: wiki, callflow, dependency tree ─────────────────────────────
    from api.core.docgen import generate_docs_artifacts
    docgen = generate_docs_artifacts(graph_id, G, communities, cohesion, labels)
    print(f"[pipeline] docgen for {graph_id}: {docgen}")

    # ── Step 10: update metadata ─────────────────────────────────────────────
    database.upsert_graph(
        graph_id,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        community_count=len(communities),
    )
    print(f"[pipeline] graph {graph_id} complete — {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")
