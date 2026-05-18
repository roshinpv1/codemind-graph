import type { GraphRole } from "@/lib/types";

/** User-facing names — CI slot holds application codebase. */
export const ROLE_LABELS: Record<GraphRole | "source", string> = {
  source: "Application",
  ci: "Application",
  test: "Test",
  cd: "CD",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role as GraphRole] ?? role;
}

export const PROJECT_SLOTS: { role: GraphRole; label: string; hint: string }[] = [
  { role: "ci", label: "Application", hint: "Main application codebase (required)" },
  { role: "test", label: "Test", hint: "Test suite or automation repo" },
  { role: "cd", label: "CD", hint: "Deploy, infra, Helm, Terraform" },
];
