"""CodeMind API — FastAPI application wiring all product routers."""
from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import config
from api.core.database import init_db
from api.routers import (
    graphs,
    architect,
    docs,
    search,
    duediligence,
    memory,
    secure,
    infra,
    research,
    refactor,
    ops,
    compliance,
    autonomous,
    coverage,
    projects,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core platform ──────────────────────────────────────────────────────────────
app.include_router(graphs.router)

# ── Product routers ────────────────────────────────────────────────────────────
app.include_router(architect.router)
app.include_router(docs.router)
app.include_router(search.router)
app.include_router(duediligence.router)
app.include_router(memory.router)
app.include_router(secure.router)
app.include_router(infra.router)
app.include_router(research.router)
app.include_router(refactor.router)
app.include_router(ops.router)
app.include_router(compliance.router)
app.include_router(autonomous.router)
app.include_router(coverage.router)
app.include_router(projects.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "name": config.API_TITLE,
        "version": config.API_VERSION,
        "status": "ok",
        "products": [
            "Context API  — /graphs",
            "Architect    — /graphs/{id}/architect",
            "Docs         — /graphs/{id}/docs",
            "Search       — /graphs/{id}/search",
            "Due Diligence— /graphs/{id}/due-diligence",
            "Memory       — /memory",
            "Secure       — /graphs/{id}/security",
            "Infra        — /infra",
            "Research     — /research",
            "Refactor     — /graphs/{id}/refactor",
            "Ops          — /graphs/{id}/ops",
            "Compliance   — /graphs/{id}/compliance",
            "Autonomous   — /graphs/{id}/autonomous",
            "Coverage     — /graphs/{id}/coverage",
            "Projects     — /projects",
        ],
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
