"""CodeMind Research — knowledge graphs for R&D: papers, experiments, concepts."""
from __future__ import annotations
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.core import engine, database, pipeline, storage
from api.config import LLM_BACKEND
from api.models.common import JobAccepted

router = APIRouter(prefix="/research", tags=["Research"])


class ResearchIngestRequest(BaseModel):
    path: str | None = None
    urls: list[str] = []
    name: str
    backend: str = LLM_BACKEND


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Research graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Research graph not ready — status: {row['status']}")
    return row


@router.post("/graphs", response_model=JobAccepted, status_code=202, summary="Ingest research papers / notebooks / URLs")
def create_research_graph(req: ResearchIngestRequest, background_tasks: BackgroundTasks):
    gid = str(uuid.uuid4())
    source = req.path or "urls"
    database.insert_graph(gid, f"research:{req.name}", source, req.backend)

    if req.urls:
        background_tasks.add_task(_ingest_urls_and_extract, gid, req.urls, req.backend)
    elif req.path:
        background_tasks.add_task(pipeline.run_extraction, gid, req.path, req.backend)
    else:
        raise HTTPException(400, "Provide path or urls")

    return JobAccepted(graph_id=gid, message=f"Research ingestion started for '{req.name}'")


def _ingest_urls_and_extract(graph_id: str, urls: list[str], backend: str):
    raw_dir = storage.graph_dir(graph_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        from graphify.ingest import ingest
        for url in urls:
            try:
                ingest(url, raw_dir)
            except Exception as exc:
                import sys; print(f"[research] failed to ingest {url}: {exc}", file=sys.stderr)
        pipeline.run_extraction(graph_id, str(raw_dir), backend)
    except Exception as exc:
        import sys; print(f"[research] pipeline failed: {exc}", file=sys.stderr)
        database.upsert_graph(graph_id, status="failed", error=str(exc)[:2000])


@router.get("/graphs/{graph_id}/concepts", response_model=list[dict], summary="Semantic concept cluster map")
def concept_map(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    result = []
    for cid, members in communities.items():
        hub = max(members, key=lambda n: G.degree(n), default=None)
        concepts = [
            {"id": n, "label": G.nodes[n].get("label", n), "file_type": G.nodes[n].get("file_type", "")}
            for n in sorted(members, key=lambda n: G.degree(n), reverse=True)[:10]
        ]
        result.append({
            "cluster_id": cid,
            "hub": hub,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "size": len(members),
            "concepts": concepts,
        })
    return sorted(result, key=lambda x: x["size"], reverse=True)


@router.get("/graphs/{graph_id}/citations", response_model=list[dict], summary="Citation relationships")
def citations(graph_id: str, paper: str | None = None):
    """Return citation edges (cites / references relations). Optionally filter by paper."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    result = []
    for u, v, data in G.edges(data=True):
        if data.get("relation") in ("cites", "references", "conceptually_related_to"):
            if paper and paper.lower() not in (G.nodes[u].get("label") or "").lower():
                continue
            result.append({
                "source": u,
                "source_label": G.nodes[u].get("label", u),
                "target": v,
                "target_label": G.nodes[v].get("label", v),
                "relation": data.get("relation", ""),
                "confidence": data.get("confidence", ""),
                "source_file": G.nodes[u].get("source_file", ""),
            })
    return result[:200]


@router.get("/graphs/{graph_id}/related", response_model=dict, summary="Semantically related work")
def related_work(graph_id: str, node: str, depth: int = 2):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    matches = engine.find_nodes(G, node)
    if not matches:
        return {"node": node, "related": [], "message": "Not found"}
    nid = matches[0]
    node_ids, edges = engine.bfs(G, [nid], depth)
    node_ids.discard(nid)
    related = [
        {
            "id": n,
            "label": G.nodes[n].get("label", n),
            "file_type": G.nodes[n].get("file_type", ""),
            "source_file": G.nodes[n].get("source_file", ""),
            "source_url": G.nodes[n].get("source_url", ""),
        }
        for n in node_ids if n in G
    ]
    return {"node": nid, "node_label": G.nodes[nid].get("label", nid), "related": related}


@router.get("/graphs/{graph_id}/gaps", response_model=list[dict], summary="Under-explored research areas")
def research_gaps(graph_id: str):
    """Nodes with few connections relative to their community — candidate blind spots."""
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    node_community = {n: cid for cid, members in communities.items() for n in members}
    avg_degrees = {}
    for cid, members in communities.items():
        if members:
            avg_degrees[cid] = sum(G.degree(n) for n in members) / len(members)
    gaps = []
    for nid, data in G.nodes(data=True):
        cid = node_community.get(nid)
        if cid is None:
            continue
        avg = avg_degrees.get(cid, 1)
        deg = G.degree(nid)
        if deg < avg * 0.3 and data.get("file_type") in ("document", "paper", "rationale"):
            gaps.append({
                "id": nid,
                "label": data.get("label", nid),
                "file_type": data.get("file_type"),
                "degree": deg,
                "community_avg_degree": round(avg, 2),
                "source_file": data.get("source_file", ""),
                "source_url": data.get("source_url", ""),
            })
    return sorted(gaps, key=lambda x: x["degree"])[:50]


@router.get("/graphs/{graph_id}/query", response_model=dict, summary="NL query over research graph")
def research_query(graph_id: str, q: str, mode: str = "bfs", depth: int = 3):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    return engine.query_graph(G, q, mode=mode, depth=depth)
