import type { GraphRole } from "@/lib/types";

export const ROLE_LABELS: Record<string, string> = {
  source: "Source",
  test: "Test",
  cd: "CD",
};

/** Legacy graphs may still report role `ci` — show as Source. */
export function roleLabel(role: string): string {
  const r = role === "ci" ? "source" : role;
  return ROLE_LABELS[r] ?? r;
}

export const PROJECT_SLOTS: { role: GraphRole; label: string; hint: string }[] = [
  { role: "source", label: "Source", hint: "Application codebase (required)" },
  { role: "test", label: "Test", hint: "Test suite or automation repo" },
  { role: "cd", label: "CD", hint: "Deploy, infra, Helm, Terraform" },
];
