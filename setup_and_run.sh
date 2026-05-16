#!/usr/bin/env zsh
# CodeMind API — one-shot setup and launch
# Requires: uv  (brew install uv)
set -e
cd "$(dirname "$0")"

VENV=".venv312"
PYTHON="$VENV/bin/python3"

# ── 1. Create venv if missing ────────────────────────────────────────────────
if [[ ! -x "$PYTHON" ]]; then
    echo "==> Creating Python 3.12 virtual environment via uv..."
    uv venv --python python3.12 "$VENV"
fi

# ── 2. Install graphify + API deps ───────────────────────────────────────────
echo "==> Installing graphify (editable) and API dependencies..."
uv pip install --python "$PYTHON" -e ".[mcp,pdf,watch,gemini,openai]" -q
uv pip install --python "$PYTHON" fastapi "uvicorn[standard]" pyyaml requests -q
echo "    Done."

# ── 3. Verify all imports ────────────────────────────────────────────────────
echo ""
echo "==> Verifying imports..."
PYTHONPATH=. "$PYTHON" -c "
import sys, os
sys.path.insert(0, '.')

from pathlib import Path
env = Path('.env')
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from api.config import API_TITLE, API_VERSION, GRAPHS_DIR
from api.core.database import init_db
init_db()

from api.routers import graphs, architect, docs, search, duediligence
from api.routers import memory, secure, infra, research, refactor, ops, compliance, autonomous
from api.main import app

routes = [r for r in app.routes]
print(f'  {API_TITLE} v{API_VERSION} — all imports OK')
print(f'  Graph storage: {GRAPHS_DIR}')
print(f'  Routes registered: {len(routes)}')
"

# ── 4. Launch ────────────────────────────────────────────────────────────────
echo ""
echo "==> Starting CodeMind API server..."
echo "    Swagger UI:  http://localhost:8000/docs"
echo "    ReDoc:       http://localhost:8000/redoc"
echo "    Health:      http://localhost:8000/health"
echo ""
PYTHONPATH=. "$PYTHON" run_api.py --host 0.0.0.0 --port 8000 --reload
