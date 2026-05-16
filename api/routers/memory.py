"""CodeMind Memory — organizational engineering brain: ingest multi-source docs into the graph."""
from __future__ import annotations
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.core import engine, database, storage
from api.config import LLM_BACKEND

router = APIRouter(prefix="/memory", tags=["Memory"])


class IngestDocRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    source_type: str = "document"  # slack | notion | jira | pr | meeting | document | arxiv
    author: str | None = None
    title: str | None = None
    graph_id: str | None = None  # attach to an existing graph, or create standalone


class MemoryQueryRequest(BaseModel):
    question: str
    graph_id: str
    mode: str = "bfs"
    depth: int = 3


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


def _ingest_url_to_raw(url: str, graph_id: str, author: str | None = None) -> Path:
    """Fetch a URL and write it to the graph's raw/ directory for future extraction."""
    raw_dir = storage.graph_dir(graph_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        from graphify.ingest import ingest
        out_path = ingest(url, raw_dir, author=author or "")
        return Path(out_path)
    except Exception as exc:
        raise HTTPException(502, f"Failed to fetch {url!r}: {exc}")


def _ingest_text_to_raw(text: str, title: str, graph_id: str, source_type: str) -> Path:
    raw_dir = storage.graph_dir(graph_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in "- _" else "_" for c in title)[:60]
    out = raw_dir / f"{source_type}_{safe_title}.md"
    out.write_text(text, encoding="utf-8")
    return out


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=dict, status_code=202, summary="Ingest a document or URL into memory")
def ingest_document(req: IngestDocRequest, background_tasks: BackgroundTasks):
    if not req.url and not req.text:
        raise HTTPException(400, "Provide either url or text")

    # If no graph_id, create a new standalone memory graph
    if not req.graph_id:
        gid = str(uuid.uuid4())
        name = req.title or req.url or "memory"
        database.insert_graph(gid, f"memory:{name}", "memory", LLM_BACKEND)
        graph_id = gid
    else:
        graph_id = req.graph_id
        database.get_graph(graph_id)  # ensure exists

    if req.url:
        background_tasks.add_task(_bg_ingest_url, req.url, graph_id, req.author)
    else:
        background_tasks.add_task(_bg_ingest_text, req.text, req.title or "untitled", graph_id, req.source_type)

    return {"ok": True, "graph_id": graph_id, "status": "queued", "message": "Document ingestion queued"}


def _bg_ingest_url(url: str, graph_id: str, author: str | None):
    try:
        raw_dir = storage.graph_dir(graph_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        from graphify.ingest import ingest
        ingest(url, raw_dir, author=author or "")
        _rebuild_from_raw(graph_id)
    except Exception as exc:
        import sys; print(f"[memory] ingest_url failed: {exc}", file=sys.stderr)


def _bg_ingest_text(text: str, title: str, graph_id: str, source_type: str):
    try:
        _ingest_text_to_raw(text, title, graph_id, source_type)
        _rebuild_from_raw(graph_id)
    except Exception as exc:
        import sys; print(f"[memory] ingest_text failed: {exc}", file=sys.stderr)


def _rebuild_from_raw(graph_id: str):
    from api.core.pipeline import run_extraction
    row = database.get_graph(graph_id)
    if not row:
        return
    raw_dir = str(storage.graph_dir(graph_id) / "raw")
    backend = row["backend"] or LLM_BACKEND
    run_extraction(graph_id, raw_dir, backend)


@router.get("/query", response_model=dict, summary="NL question → answer with provenance")
def query_memory(graph_id: str, q: str, mode: str = "bfs", depth: int = 3):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    result = engine.query_graph(G, q, mode=mode, depth=depth)
    result["provenance"] = [
        {
            "source_file": G.nodes[n["id"]].get("source_file", ""),
            "source_url": G.nodes[n["id"]].get("source_url", ""),
            "author": G.nodes[n["id"]].get("author", ""),
            "captured_at": G.nodes[n["id"]].get("captured_at", ""),
        }
        for n in result.get("nodes", [])[:10]
        if n.get("id") in G
    ]
    return result


@router.get("/decisions", response_model=list[dict], summary="Architecture decision log with rationale")
def get_decisions(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    decisions = []
    for nid, data in G.nodes(data=True):
        if data.get("file_type") == "rationale":
            decisions.append({
                "id": nid,
                "label": data.get("label", nid),
                "source_file": data.get("source_file", ""),
                "source_url": data.get("source_url", ""),
                "author": data.get("author", ""),
                "captured_at": data.get("captured_at", ""),
                "connected_to": [
                    {"id": nb, "label": G.nodes[nb].get("label", nb)}
                    for nb in G.neighbors(nid)
                ][:5],
            })
    return decisions


@router.get("/gaps", response_model=list[dict], summary="Under-documented areas (low-confidence nodes)")
def knowledge_gaps(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    ambiguous = []
    for u, v, data in G.edges(data=True):
        if data.get("confidence") == "AMBIGUOUS":
            ambiguous.append({
                "source": u,
                "source_label": G.nodes[u].get("label", u),
                "target": v,
                "target_label": G.nodes[v].get("label", v),
                "relation": data.get("relation", ""),
                "confidence_score": data.get("confidence_score", 0),
            })
    return sorted(ambiguous, key=lambda x: x["confidence_score"])[:50]


@router.get("/ownership", response_model=list[dict], summary="Who knows what, based on author participation")
def knowledge_ownership(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    author_map: dict[str, list[dict]] = {}
    for nid, data in G.nodes(data=True):
        author = data.get("author", "")
        if author:
            author_map.setdefault(author, []).append({
                "id": nid,
                "label": data.get("label", nid),
                "source_file": data.get("source_file", ""),
            })
    return [{"author": a, "node_count": len(nodes), "nodes": nodes[:20]} for a, nodes in author_map.items()]
