"""CodeMind Docs — living architecture documentation generation."""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel

from api.core import engine, database
from api.core.docgen import generate_docs_artifacts
from api.core.storage import graph_dir, report_path, wiki_path, graph_json_path

router = APIRouter(prefix="/graphs/{graph_id}/docs", tags=["Docs"])


def _require_ready(graph_id: str):
    row = database.get_graph(graph_id)
    if not row:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    if row["status"] != "ready":
        raise HTTPException(409, f"Graph not ready — status: {row['status']}")
    return row


class PublishRequest(BaseModel):
    target: str  # "confluence" | "notion" | "github_wiki"
    base_url: str | None = None
    token: str | None = None
    space_key: str | None = None
    page_id: str | None = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=dict, summary="Trigger documentation regeneration")
def generate_docs(graph_id: str):
    row = _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    labels = {cid: f"Community {cid}" for cid in communities}

    # Regenerate GRAPH_REPORT.md
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.cluster import score_all
    from graphify.report import generate
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    detection = {"files": {}, "total_files": G.number_of_nodes(), "total_words": 0}
    tokens = {"input": 0, "output": 0}
    md = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, row["source_path"], suggested_questions=questions)
    report_path(graph_id).write_text(md, encoding="utf-8")

    artifacts = generate_docs_artifacts(graph_id, G, communities, cohesion, labels)

    return {
        "ok": True,
        "message": "Documentation regenerated",
        "graph_id": graph_id,
        **artifacts,
    }


@router.get("/report", response_class=PlainTextResponse, summary="Architecture report (Markdown)")
def get_report(graph_id: str):
    _require_ready(graph_id)
    p = report_path(graph_id)
    if not p.exists():
        raise HTTPException(404, "Report not generated. Call POST /docs/generate first.")
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/wiki", response_model=dict, summary="Wiki content as a dict of page → markdown")
def get_wiki(graph_id: str):
    _require_ready(graph_id)
    wiki_dir = wiki_path(graph_id)
    if not wiki_dir.exists():
        raise HTTPException(404, "Wiki not generated. Call POST /docs/generate first.")
    pages: dict[str, str] = {}
    for md_file in sorted(wiki_dir.glob("*.md")):
        pages[md_file.stem] = md_file.read_text(encoding="utf-8")
    return pages


@router.get("/callflow", response_class=HTMLResponse, summary="Architecture call-flow diagram (HTML)")
def get_callflow(graph_id: str):
    _require_ready(graph_id)
    p = graph_dir(graph_id) / "callflow.html"
    if not p.exists():
        raise HTTPException(404, "Callflow not generated. Call POST /docs/generate first.")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@router.get("/tree", response_class=HTMLResponse, summary="Dependency tree (HTML)")
def get_tree(graph_id: str):
    _require_ready(graph_id)
    p = graph_dir(graph_id) / "tree.html"
    if not p.exists():
        raise HTTPException(404, "Tree not generated. Call POST /docs/generate first.")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@router.get("/ownership", response_model=list[dict], summary="Subsystem ownership map by community")
def get_ownership(graph_id: str):
    _require_ready(graph_id)
    G = engine.load_graph(graph_id)
    communities = engine.communities_from_graph(G)
    result = []
    for cid, members in communities.items():
        source_files = list({G.nodes[n].get("source_file", "") for n in members if G.nodes[n].get("source_file")})
        hub = max(members, key=lambda n: G.degree(n), default=None)
        result.append({
            "community_id": cid,
            "hub_node": hub,
            "hub_label": G.nodes[hub].get("label", hub) if hub else None,
            "member_count": len(members),
            "source_files": source_files[:20],
        })
    return sorted(result, key=lambda x: x["member_count"], reverse=True)


@router.post("/publish", response_model=dict, summary="Publish docs to Confluence / Notion / GitHub Wiki")
def publish_docs(graph_id: str, req: PublishRequest):
    _require_ready(graph_id)
    p = report_path(graph_id)
    if not p.exists():
        raise HTTPException(400, "Generate docs first via POST /docs/generate")
    content = p.read_text(encoding="utf-8")

    if req.target == "confluence":
        return _publish_confluence(content, req)
    if req.target == "notion":
        return _publish_notion(content, req)
    if req.target == "github_wiki":
        return _publish_github_wiki(content, req, graph_id)
    raise HTTPException(400, f"Unknown target: {req.target!r}. Use confluence, notion, or github_wiki")


def _publish_confluence(content: str, req: PublishRequest) -> dict:
    if not req.base_url or not req.token or not req.space_key:
        raise HTTPException(400, "confluence requires base_url, token, and space_key")
    try:
        import requests
        title = "CodeMind Architecture Report"
        url = f"{req.base_url.rstrip('/')}/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": req.space_key},
            "body": {"storage": {"value": f"<ac:plain-text-body><![CDATA[{content}]]></ac:plain-text-body>", "representation": "storage"}},
        }
        if req.page_id:
            r = requests.put(f"{url}/{req.page_id}", json=payload, headers={"Authorization": f"Bearer {req.token}"}, timeout=30)
        else:
            r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {req.token}"}, timeout=30)
        r.raise_for_status()
        return {"ok": True, "url": r.json().get("_links", {}).get("webui", "")}
    except ImportError:
        raise HTTPException(500, "requests library not installed")
    except Exception as exc:
        raise HTTPException(502, f"Confluence publish failed: {exc}")


def _publish_notion(content: str, req: PublishRequest) -> dict:
    if not req.token or not req.page_id:
        raise HTTPException(400, "notion requires token and page_id (parent page ID)")
    try:
        import requests
        blocks = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}}
                  for chunk in [content[i:i+2000] for i in range(0, min(len(content), 100000), 2000)]]
        r = requests.patch(
            f"https://api.notion.com/v1/blocks/{req.page_id}/children",
            json={"children": blocks},
            headers={"Authorization": f"Bearer {req.token}", "Notion-Version": "2022-06-28"},
            timeout=30,
        )
        r.raise_for_status()
        return {"ok": True, "page_id": req.page_id}
    except ImportError:
        raise HTTPException(500, "requests library not installed")
    except Exception as exc:
        raise HTTPException(502, f"Notion publish failed: {exc}")


def _publish_github_wiki(content: str, req: PublishRequest, graph_id: str) -> dict:
    if not req.base_url:
        raise HTTPException(400, "github_wiki requires base_url (e.g. https://github.com/org/repo.wiki.git)")
    try:
        import subprocess, tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            if req.token:
                repo_url = req.base_url.replace("https://", f"https://{req.token}@")
            else:
                repo_url = req.base_url
            subprocess.run(["git", "clone", repo_url, tmpdir], check=True, capture_output=True, env=env)
            wiki_file = Path(tmpdir) / "Architecture.md"
            wiki_file.write_text(content, encoding="utf-8")
            subprocess.run(["git", "add", "Architecture.md"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "chore: update CodeMind architecture docs"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "push"], cwd=tmpdir, check=True, capture_output=True, env=env)
        return {"ok": True, "message": "Pushed to GitHub Wiki"}
    except Exception as exc:
        raise HTTPException(502, f"GitHub Wiki publish failed: {exc}")
