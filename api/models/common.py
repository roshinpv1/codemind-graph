"""Shared Pydantic models for all routers."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class GraphStatus(str, Enum):
    pending = "pending"
    running = "running"
    ready = "ready"
    failed = "failed"


class GraphRole(str, Enum):
    """What a graph represents within a project."""
    source = "source"   # production / application code
    test   = "test"     # regression / automation test suite
    ci     = "ci"       # CI pipeline definitions (GitHub Actions, Jenkinsfile, etc.)
    cd     = "cd"       # CD / deployment / infra (Terraform, Helm, K8s manifests)


class GraphMeta(BaseModel):
    id: str
    name: str
    source_path: str
    status: GraphStatus
    graph_role: GraphRole = GraphRole.source
    project_id: str | None = None
    backend: str | None = None
    node_count: int = 0
    edge_count: int = 0
    community_count: int = 0
    error: str | None = None
    created_at: str
    updated_at: str


class IngestRequest(BaseModel):
    dedup_llm: bool = Field(False, description="Use LLM to resolve ambiguous entity deduplication pairs during build")
    use_semantic: bool = Field(
        True,
        description=(
            "Run LLM semantic extraction on documents, papers, and images. "
            "Set false for code-only indexing (AST only, no API key required)."
        ),
    )
    path: str = Field(..., description="Absolute local path to the repository or folder to index")
    name: str = Field(..., description="Human-readable name for this graph")
    backend: str = Field("openai", description="LLM backend for semantic extraction (ignored when use_semantic=false)")
    graph_role: GraphRole = Field(
        GraphRole.source,
        description=(
            "Role this graph plays within a project. "
            "'source' = production code, 'test' = regression/automation tests, "
            "'ci' = CI pipeline files, 'cd' = deployment/infra files."
        ),
    )
    project_id: str = Field(
        ...,
        description="Project this graph belongs to. Create via POST /projects first.",
    )


# ── Project models ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., description="Human-readable project name")
    description: str = Field("", description="Optional project description")


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    graphs: list[GraphMeta] = []


class AssignGraphRequest(BaseModel):
    graph_id: str = Field(..., description="ID of an existing ready graph")
    graph_role: GraphRole = Field(..., description="Role this graph plays in the project")


class NodeOut(BaseModel):
    id: str
    label: str | None = None
    file_type: str | None = None
    source_file: str | None = None
    source_location: str | None = None
    community: int | None = None
    degree: int = 0
    neighbors: list[dict] = []


class EdgeOut(BaseModel):
    source: str
    source_label: str = ""
    target: str
    target_label: str = ""
    relation: str = ""
    confidence: str = ""
    confidence_score: float = 0.0


class QueryResult(BaseModel):
    query: str = ""
    mode: str = "bfs"
    start_nodes: list[str] = []
    nodes: list[dict] = []
    edges: list[dict] = []
    message: str | None = None


class PathResult(BaseModel):
    path: list[dict] = []
    length: int = 0
    error: str | None = None


class StatsResult(BaseModel):
    node_count: int
    edge_count: int
    community_count: int
    avg_degree: float
    max_degree: int
    density: float
    is_connected: bool


class ViolationOut(BaseModel):
    rule: str
    severity: str = "error"
    source: str
    source_label: str = ""
    target: str
    target_label: str = ""
    relation: str = ""
    message: str = ""


class JobAccepted(BaseModel):
    graph_id: str
    status: str = "pending"
    message: str = "Extraction started in background"


class OkResponse(BaseModel):
    ok: bool = True
    message: str = ""
