#!/usr/bin/env python3
"""Start the CodeMind API server.

Usage:
    python run_api.py
    python run_api.py --host 0.0.0.0 --port 8000 --reload
"""
import sys
import os
from pathlib import Path

# Ensure the project root is on sys.path so `api` and `graphify` are importable.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load .env if it exists
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="CodeMind API server")
    parser.add_argument("--host", default=os.environ.get("CODEMIND_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CODEMIND_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", default=False)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    print(f"Starting CodeMind API on http://{args.host}:{args.port}")
    print(f"Swagger UI:  http://localhost:{args.port}/docs")
    print(f"ReDoc:       http://localhost:{args.port}/redoc")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )
