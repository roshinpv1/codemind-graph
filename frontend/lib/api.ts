import type {
  AssignGraphRequest,
  CoverageSummary,
  FunctionalCoverage,
  GraphMeta,
  HealthScore,
  IngestRequest,
  JobAccepted,
  ProjectCoverage,
  ProjectCreate,
  ProjectOut,
  ProjectSummary,
  QueryResult,
  StatsResult,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text || `HTTP ${res.status}`);
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return res.text() as unknown as T;
}

// ── Graphs ────────────────────────────────────────────────────────────────────

export const graphsApi = {
  list: (projectId?: string) =>
    request<GraphMeta[]>(
      projectId ? `/graphs?project_id=${encodeURIComponent(projectId)}` : "/graphs",
    ),
  get: (id: string) => request<GraphMeta>(`/graphs/${id}`),
  ingest: (body: IngestRequest) =>
    request<JobAccepted>("/graphs", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: string) =>
    request<{ ok: boolean; message: string }>(`/graphs/${id}`, { method: "DELETE" }),
  update: (id: string) =>
    request<JobAccepted>(`/graphs/${id}/update`, { method: "POST" }),
  stats: (id: string) => request<StatsResult>(`/graphs/${id}/stats`),
  query: (id: string, q: string, mode = "bfs", depth = 3, llm = false) =>
    request<QueryResult & { answer?: string }>(
      `/graphs/${id}/query?q=${encodeURIComponent(q)}&mode=${mode}&depth=${depth}&llm=${llm}`,
    ),
  gods: (id: string) => request<Record<string, unknown>[]>(`/graphs/${id}/gods`),
  communities: (id: string) =>
    request<
      { community_id: number; size: number; hub_node: string; hub_label: string; members: string[] }[]
    >(`/graphs/${id}/communities`),
  surprising: (id: string) => request<Record<string, unknown>[]>(`/graphs/${id}/surprising`),
  summarize: (id: string, backend?: string) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/summarize${backend ? `?backend=${backend}` : ""}`,
    ),
  explainNode: (id: string, nodeId: string, backend?: string) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/explain/${encodeURIComponent(nodeId)}${backend ? `?backend=${backend}` : ""}`,
    ),
  node: (id: string, nodeId: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/nodes/${encodeURIComponent(nodeId)}`),
  path: (id: string, from: string, to: string) =>
    request<{ path: Record<string, unknown>[]; length: number; error?: string }>(
      `/graphs/${id}/path?from_=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    ),
  report: (id: string) => request<string>(`/graphs/${id}/report`),
  labelCommunities: (id: string, backend?: string) =>
    request<{ labels: Record<string, string>; count: number }>(
      `/graphs/${id}/communities/label`,
      { method: "POST", body: JSON.stringify({ backend }) },
    ),
};

// ── Coverage ──────────────────────────────────────────────────────────────────

export const coverageApi = {
  summary: (id: string) => request<CoverageSummary>(`/graphs/${id}/coverage/summary`),
  functional: (id: string, mode = "all", limit = 100) =>
    request<FunctionalCoverage>(
      `/graphs/${id}/coverage/functional?mode=${mode}&limit=${limit}`,
    ),
  gaps: (id: string, mode = "functional", limit = 50) =>
    request<{ gaps: Record<string, unknown>[]; total_gaps?: number; uncovered_entry_points?: number }>(
      `/graphs/${id}/coverage/gaps?mode=${mode}&limit=${limit}`,
    ),
  critical: (id: string, topN = 20) =>
    request<{ critical_gaps: Record<string, unknown>[]; functional_coverage_pct: number; grade: string }>(
      `/graphs/${id}/coverage/critical?top_n=${topN}`,
    ),
  files: (id: string, mode = "functional") =>
    request<{ files: Record<string, unknown>[]; overall_coverage_pct: number; worst_files: Record<string, unknown>[] }>(
      `/graphs/${id}/coverage/files?mode=${mode}`,
    ),
  hotspots: (id: string, topN = 20) =>
    request<{ hotspots: Record<string, unknown>[] }>(
      `/graphs/${id}/coverage/hotspots?top_n=${topN}`,
    ),
  narrative: (id: string, backend?: string) =>
    request<{ narrative: string; functional_coverage_pct: number }>(
      `/graphs/${id}/coverage/narrative${backend ? `?backend=${backend}` : ""}`,
    ),
};

// ── Architect ─────────────────────────────────────────────────────────────────

export const architectApi = {
  violations: (id: string, narrative = false) =>
    request<{
      violations: import("./types").Violation[];
      count: number;
      structural_findings?: import("./types").Violation[];
      structural_count?: number;
      policies_configured?: boolean;
      narrative?: string;
    }>(`/graphs/${id}/architect/violations?narrative=${narrative}`),
  circularDeps: (id: string) =>
    request<{
      cycles: { cycle: { id: string; label: string }[]; length: number; approximate_group?: boolean }[];
      count: number;
      approximate?: boolean;
    }>(`/graphs/${id}/architect/circular-deps`),
  layerViolations: (id: string, layers?: string) =>
    request<Record<string, unknown>[]>(
      `/graphs/${id}/architect/layer-violations${layers ? `?layers=${layers}` : ""}`,
    ),
  healthTrend: (id: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/architect/health-trend`).catch(() =>
      autonomousApi.healthTrend(id),
    ),
  anomalies: (id: string) => autonomousApi.anomalies(id),
};

// ── Autonomous ────────────────────────────────────────────────────────────────

export const autonomousApi = {
  anomalies: (id: string) =>
    request<import("./types").Anomaly[]>(`/graphs/${id}/autonomous/anomalies`),
  healthTrend: (id: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/autonomous/health-trend`),
  proposals: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/autonomous/proposals`),
};

// ── Security ──────────────────────────────────────────────────────────────────

export const securityApi = {
  authFlows: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/security/auth-flows`),
  trustBoundaries: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/security/trust-boundaries`),
  attackPaths: (id: string, target?: string) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/security/attack-paths${target ? `?target=${encodeURIComponent(target)}` : ""}`,
    ),
  secretExposure: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/security/secret-exposure`),
  report: (id: string, narrative = false) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/security/report?narrative=${narrative}`,
    ),
};

// ── Due Diligence / Health ──────────────────────────────────────────────────────

export const dueDiligenceApi = {
  score: (id: string) => request<HealthScore>(`/graphs/${id}/due-diligence/score`),
  debt: (id: string) => request<Record<string, unknown>[]>(`/graphs/${id}/due-diligence/debt`),
  deadCode: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/due-diligence/dead-code`),
  deadCodeTiered: (id: string) =>
    request<{
      safe_to_remove: Record<string, unknown>[];
      review_first: Record<string, unknown>[];
      safe_count: number;
      review_count: number;
    }>(`/graphs/${id}/due-diligence/dead-code/tiered`),
  complexity: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/due-diligence/complexity`),
  report: (id: string, narrative = false) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/due-diligence/report?narrative=${narrative}`,
    ),
};

// ── Search ──────────────────────────────────────────────────────────────────────

export const searchApi = {
  search: (id: string, q: string, mode = "bfs", depth = 3) =>
    request<QueryResult>(
      `/graphs/${id}/search?q=${encodeURIComponent(q)}&mode=${mode}&depth=${depth}`,
    ),
  dependents: (id: string, node: string, depth = 2) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/search/dependents?node=${encodeURIComponent(node)}&depth=${depth}`,
    ),
};

// ── Docs ────────────────────────────────────────────────────────────────────────

export interface DocsOverview {
  graph_id: string;
  repository_name?: string;
  ready: boolean;
  message?: string;
  audience_note?: string;
  plain_summary?: string | null;
  plain_summary_available?: boolean;
  product_areas?: {
    id: string;
    name: string;
    centerpiece?: string;
    component_count: number;
    source_files?: string[];
  }[];
  wiki_guides?: {
    id: string;
    title: string;
    summary?: string | null;
    key_items?: string[];
    source_files?: string[];
  }[];
  report_highlights?: {
    stats_line?: string | null;
    key_components?: { name: string; connection_count: number }[];
    notable_connections?: string[];
    suggested_questions?: string[];
  };
  artifacts?: { report?: boolean; wiki?: boolean; callflow?: boolean; tree?: boolean };
  suggested_actions?: string[];
}

export const docsApi = {
  overview: (id: string) => request<DocsOverview>(`/graphs/${id}/docs/overview`),
  generatePlainSummary: (id: string) =>
    request<{ ok: boolean; plain_summary?: string }>(
      `/graphs/${id}/docs/overview/summary`,
      { method: "POST" },
    ),
  report: (id: string) => request<string>(`/graphs/${id}/docs/report`),
  wiki: (id: string) => request<Record<string, string>>(`/graphs/${id}/docs/wiki`),
  generate: (id: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/docs/generate`, { method: "POST" }),
  callflowUrl: (id: string) => `${API}/graphs/${id}/docs/callflow`,
  treeUrl: (id: string) => `${API}/graphs/${id}/docs/tree`,
};

// ── Compliance ──────────────────────────────────────────────────────────────────

export const complianceApi = {
  piiFlows: (id: string, standard = "gdpr") =>
    request<Record<string, unknown>[]>(
      `/graphs/${id}/compliance/pii-flows?standard=${standard}`,
    ),
  violations: (id: string) =>
    request<Record<string, unknown>[]>(`/graphs/${id}/compliance/violations`),
  evidence: (id: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/compliance/evidence`),
};

// ── Ops ─────────────────────────────────────────────────────────────────────────

export const opsApi = {
  healthSummary: (id: string) =>
    request<Record<string, unknown>>(`/graphs/${id}/ops/health-summary`),
  blastRadius: (id: string, service: string, depth = 3) =>
    request<Record<string, unknown>>(
      `/graphs/${id}/ops/blast-radius?service=${encodeURIComponent(service)}&depth=${depth}`,
    ),
};

// ── Projects ────────────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => request<ProjectOut[]>("/projects"),
  get: (id: string) => request<ProjectOut>(`/projects/${id}`),
  create: (body: ProjectCreate) =>
    request<ProjectOut>("/projects", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: string) =>
    request<{ ok: boolean; graphs_deleted?: number }>(`/projects/${id}`, { method: "DELETE" }),
  deleteGraph: (projectId: string, graphId: string) =>
    request<{ ok: boolean; message: string }>(
      `/projects/${projectId}/graphs/${graphId}`,
      { method: "DELETE" },
    ),
  assignGraph: (projectId: string, body: AssignGraphRequest) =>
    request<{ ok: boolean; graph_id: string; role: string }>(
      `/projects/${projectId}/graphs`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  coverage: (id: string, limit = 50) =>
    request<ProjectCoverage>(`/projects/${id}/coverage?limit=${limit}`),
  summary: (id: string) => request<ProjectSummary>(`/projects/${id}/summary`),
  graphs: (id: string) =>
    request<{ by_role: Record<string, GraphMeta[]>; total: number }>(
      `/projects/${id}/graphs`,
    ),
  personas: () =>
    request<{ personas: { id: string; label: string }[] }>("/projects/personas"),
  ask: (id: string, q: string, persona = "developer", mode = "bfs", depth = 3) =>
    request<import("./types").ProjectAskResult & { structured?: Record<string, unknown>; intent?: string; pkb_available?: boolean }>(
      `/projects/${id}/ask?q=${encodeURIComponent(q)}&persona=${encodeURIComponent(persona)}&mode=${mode}&depth=${depth}`,
    ),
  search: (id: string, q: string, mode = "bfs", depth = 3) =>
    request<import("./types").ProjectSearchResult>(
      `/projects/${id}/search?q=${encodeURIComponent(q)}&mode=${mode}&depth=${depth}`,
    ),
  synthesize: (id: string, useLlm = true) =>
    request<Record<string, unknown>>(
      `/projects/${id}/synthesize?use_llm=${useLlm}`,
      { method: "POST" },
    ),
  dna: (id: string) => request<import("./types").ProjectDna>(`/projects/${id}/dna`),
  generateDna: (id: string, useLlm = true) =>
    request<import("./types").ProjectDna>(
      `/projects/${id}/dna/generate?use_llm=${useLlm}`,
      { method: "POST" },
    ),
  briefing: (id: string) =>
    request<import("./types").ProjectBriefing>(`/projects/${id}/briefing`),
  map: (id: string) =>
    request<import("./types").ProductMapData>(`/projects/${id}/map`),
  findings: (id: string, category?: string, limit = 30) =>
    request<{ project_id: string; findings: import("./types").ProductFinding[]; count: number }>(
      `/projects/${id}/findings?limit=${limit}${category ? `&category=${encodeURIComponent(category)}` : ""}`,
    ),
  risks: (id: string, limit = 30) =>
    request<{ risks: Record<string, unknown>[]; count: number }>(
      `/projects/${id}/risks?limit=${limit}`,
    ),
  capabilities: (id: string, uncoveredOnly = false) =>
    request<{ capabilities: Record<string, unknown>[]; metrics: Record<string, unknown> }>(
      `/projects/${id}/capabilities?uncovered_only=${uncoveredOnly}`,
    ),
  scenarios: (id: string) =>
    request<{ scenarios: Record<string, { title: string; persona: string; questions: string[] }> }>(
      `/projects/${id}/scenarios`,
    ),
  visit: (id: string) =>
    request<{ ok: boolean; visited_at: string }>(`/projects/${id}/visit`, { method: "POST" }),
  delta: (id: string) => request<Record<string, unknown>>(`/projects/${id}/delta`),
  memory: (id: string, limit = 20) =>
    request<{ items: Record<string, unknown>[] }>(`/projects/${id}/memory?limit=${limit}`),
  view: (id: string) =>
    request<Record<string, unknown>>(`/projects/${id}/view`),
  decisions: (id: string, limit = 30) =>
    request<{ decisions: Record<string, unknown>[]; count: number }>(
      `/projects/${id}/decisions?limit=${limit}`,
    ),
  blastRadius: (id: string, paths: string[], depth = 4) =>
    request<Record<string, unknown>>(`/projects/${id}/blast-radius`, {
      method: "POST",
      body: JSON.stringify({ paths, depth }),
    }),
  delivery: (id: string) =>
    request<Record<string, unknown>>(`/projects/${id}/delivery`),
  clusterSnapshot: (id: string, body?: { kubeconfig?: string; context?: string; namespace?: string }) =>
    request<Record<string, unknown>>(`/projects/${id}/cluster/snapshot`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  getClusterSnapshot: (id: string) =>
    request<Record<string, unknown>>(`/projects/${id}/cluster/snapshot`),
};

export { ApiError };
