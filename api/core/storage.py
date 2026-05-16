"""Graph file storage — each graph lives under data/graphs/{graph_id}/."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from api.config import GRAPHS_DIR


def graph_dir(graph_id: str) -> Path:
    d = GRAPHS_DIR / graph_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def graph_json_path(graph_id: str) -> Path:
    return graph_dir(graph_id) / "graph.json"


def report_path(graph_id: str) -> Path:
    return graph_dir(graph_id) / "GRAPH_REPORT.md"


def wiki_path(graph_id: str) -> Path:
    return graph_dir(graph_id) / "wiki"


def callflow_path(graph_id: str) -> Path:
    return graph_dir(graph_id) / "callflow.html"


def tree_path(graph_id: str) -> Path:
    return graph_dir(graph_id) / "tree.html"


def graph_exists(graph_id: str) -> bool:
    return graph_json_path(graph_id).exists()


def load_graph_json(graph_id: str) -> dict:
    p = graph_json_path(graph_id)
    if not p.exists():
        raise FileNotFoundError(f"Graph {graph_id} not found on disk")
    return json.loads(p.read_text(encoding="utf-8"))


def save_graph_json(graph_id: str, data: dict) -> None:
    graph_json_path(graph_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def delete_graph(graph_id: str) -> None:
    d = GRAPHS_DIR / graph_id
    if d.exists():
        shutil.rmtree(d)
