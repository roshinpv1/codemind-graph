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

export interface ProductArea {
  id: string;
  name: string;
  component_count?: number;
  centerpiece?: string;
  repository?: string;
  repository_role?: string;
  summary?: string;
}

export interface ProductCapability {
  id: string;
  name: string;
  source_file?: string;
  test_status: string;
  test_status_key?: string;
  importance?: string;
  type?: string;
}

export interface ProductFinding {
  id: string;
  title: string;
  why_it_matters?: string;
  severity?: string;
  severity_label?: string;
  category?: string;
  category_key?: string;
  suggested_action?: string;
}

export interface ProductJourney {
  name: string;
  summary?: string;
  test_status?: string;
  steps?: string[];
}

export interface ProductHealth {
  status_key?: string;
  status_label?: string;
  capabilities_tested_pct?: number;
  capabilities_total?: number;
  capabilities_untested?: number;
  open_findings?: number;
  product_areas?: number;
}

export interface ProductMapData {
  project_id: string;
  ready: boolean;
  message?: string;
  headline?: string;
  summary?: string;
  health?: ProductHealth;
  areas?: ProductArea[];
  capabilities?: ProductCapability[];
  findings?: ProductFinding[];
  journeys?: ProductJourney[];
  repositories?: { id: string; name: string; role: string; role_label?: string; status?: string; indexed_components?: number }[];
  understanding_updated_at?: string;
}

export interface ProjectDna {
  project_id: string;
  project_name?: string;
  ready: boolean;
  message?: string | null;
  headline?: string;
  summary?: string;
  full_summary?: string | null;
  health_label?: string;
  health_key?: string;
  coverage_grade?: string;
  generated_at?: string;
  graphs_ready?: number;
  metrics?: Record<string, number | string>;
}

export interface ProjectBriefing {
  project_id: string;
  ready: boolean;
  message?: string;
  headline?: string;
  summary?: string;
  health_label?: string;
  health_key?: string;
  capabilities_tested_pct?: number;
  capabilities_untested?: number;
  open_findings?: number;
  top_findings?: ProductFinding[];
  top_areas?: ProductArea[];
  understanding_updated_at?: string;
  /** @deprecated legacy shape */
  dna?: { headline?: string; summary?: string; health?: string; coverage_grade?: string };
  metrics?: Record<string, number | string>;
  risks?: { title: string; severity: string; category?: string; detail?: string }[];
  flows?: { name: string; description?: string; covered?: boolean }[];
  synthesized_at?: string;
}

export interface AnswerCard {
  summary?: string;
  confidence?: string;
  confidence_label?: string;
  related?: { name: string; type?: string; test_status?: string; file?: string }[];
  gaps?: string[];
  suggested_next_steps?: string[];
}

export interface TechnicalProof {
  repositories?: { name: string; role: string }[];
  components?: { label?: string; file?: string; repository?: string }[];
}

export interface ProjectAskResult {
  project_id: string;
  project_name?: string;
  question: string;
  persona: string;
  persona_label: string;
  intent?: string;
  answer: string;
  answer_card?: AnswerCard;
  technical_proof?: TechnicalProof;
  understanding_ready?: boolean;
  structured?: Record<string, unknown>;
  context_nodes: number;
  graphs_used?: number;
  sources: ProjectAskSource[];
  backend: string;
  pkb_available?: boolean;
}

export interface ProjectAskSource {
  graph_id: string;
  graph_name: string;
  graph_role: string;
  context_nodes?: number;
  start_labels?: string[];
}
