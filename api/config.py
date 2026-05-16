"""Central configuration — all settings loaded from environment variables."""
from __future__ import annotations
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CODEMIND_DATA_DIR", str(BASE_DIR / "data")))
GRAPHS_DIR = DATA_DIR / "graphs"
PROJECTS_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "codemind.db"

GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PKB_VERSION = "1"

# ── Extraction backend ─────────────────────────────────────────────────────────
# Auto-detected from env keys; can be overridden explicitly.
LLM_BACKEND: str = os.environ.get("CODEMIND_LLM_BACKEND", "openai")

# ── API server ─────────────────────────────────────────────────────────────────
API_HOST: str = os.environ.get("CODEMIND_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("CODEMIND_PORT", "8000"))
API_TITLE: str = "CodeMind API"
API_VERSION: str = "0.1.0"
API_DESCRIPTION: str = (
    "Graph-native software intelligence platform. "
    "Converts repositories into persistent knowledge graphs and exposes "
    "architecture governance, semantic search, documentation generation, "
    "security analysis, and more."
)
