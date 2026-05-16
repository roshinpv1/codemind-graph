export type GraphStatus = "pending" | "running" | "ready" | "failed";
export type GraphRole = "source" | "test" | "ci" | "cd";

export interface GraphMeta {
  id: string;
  name: string;
  source_path: string;
  status: GraphStatus;
  graph_role: GraphRole;
  project_id: string | null;
  backend: string | null;
  node_count: number;
  edge_count: number;
  community_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobAccepted {
  graph_id: string;
  status: string;
  message: string;
}

export interface IngestRequest {
  path: string;
  name: string;
  project_id: string;
  backend?: string;
  graph_role?: GraphRole;
  dedup_llm?: boolean;
  /** false = AST/code only, no LLM for docs/images */
  use_semantic?: boolean;
}

export interface StatsResult {
  node_count: number;
  edge_count: number;
  community_count: number;
  avg_degree: number;
  max_degree: number;
  density: number;
  is_connected: boolean;
}

export interface ProjectOut {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  graphs: GraphMeta[];
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface AssignGraphRequest {
  graph_id: string;
  graph_role: GraphRole;
}

export interface CoverageSummary {
  graph_id: string;
  functional: {
    coverage_pct: number;
    grade: string;
    entry_points_total: number;
    entry_points_covered: number;
    entry_points_uncovered: number;
    description: string;
  };
  unit: {
    coverage_pct: number;
    grade: string;
    prod_nodes_total: number;
    prod_nodes_covered: number;
    prod_nodes_uncovered: number;
    description: string;
  };
  test_nodes: number;
  test_files: string[];
  warning?: string | null;
}

export interface EntryPoint {
  id: string;
  label: string;
  source_file: string;
  module?: string;
  degree: number;
  entry_type: string;
  covered?: boolean;
  risk?: string;
  call_chain?: string[];
  covering_tests?: string[];
}

export interface FunctionalCoverage {
  graph_id: string;
  functional_coverage_pct: number;
  grade: string;
  entry_points_total: number;
  entry_points_covered: number;
  entry_points_uncovered: number;
  all_entry_points: EntryPoint[];
  grouped?: Record<string, EntryPoint[]>;
}

export interface Violation {
  rule: string;
  severity: string;
  source: string;
  source_label: string;
  target: string;
  target_label: string;
  relation: string;
  message: string;
}

export interface Community {
  community_id: number;
  size: number;
  hub_node: string;
  hub_label: string;
  members?: string[];
}

export interface QueryNode {
  id: string;
  label?: string;
  source_file?: string;
  degree?: number;
  file_type?: string;
  community?: number;
}

export interface QueryResult {
  query?: string;
  mode?: string;
  start_nodes?: string[];
  nodes: QueryNode[];
  edges: { source: string; target: string; relation?: string }[];
  message?: string;
}

export interface ProjectCoverage {
  project_id: string;
  functional_coverage_pct: number;
  grade: string;
  entry_points_total: number;
  entry_points_covered: number;
  entry_points_uncovered: number;
  coverage_gap: EntryPoint[];
  warning?: string | null;
  test_graph_info?: { graph_id: string; name: string; node_count: number }[];
}

export interface ProjectSummary {
  project_id: string;
  completeness_pct: number;
  present_roles: string[];
  missing_roles: string[];
  graphs_by_role: Record<string, { id: string; name: string; status: string; node_count: number; edge_count: number }[]>;
  recommendations: string[];
}

export interface HealthScore {
  score: number;
  rating: string;
  breakdown?: Record<string, number>;
  summary?: Record<string, unknown>;
}

export interface Anomaly {
  type: string;
  severity: string;
  message: string;
  [key: string]: unknown;
}

export interface ProjectAskSource {
  graph_id: string;
  graph_name: string;
  graph_role: string;
  context_nodes: number;
  start_labels: string[];
}

export interface ProjectAskResult {
  project_id: string;
  project_name?: string;
  question: string;
  persona: string;
  persona_label: string;
  answer: string;
  context_nodes: number;
  graphs_used?: number;
  sources: ProjectAskSource[];
  backend: string;
  mode?: string;
  depth?: number;
}

export interface ProjectSearchNode {
  id: string;
  label: string;
  source_file: string;
  community?: number;
  degree: number;
  score: number;
  graph_id: string;
  graph_name: string;
  graph_role: string;
}

export interface ProjectSearchResult {
  project_id: string;
  query: string;
  graphs_searched?: number;
  nodes: ProjectSearchNode[];
  message?: string | null;
}
