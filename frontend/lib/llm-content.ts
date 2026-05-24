/** Detect fallback community labels from failed or skipped LLM naming. */
export function isPlaceholderAreaName(name: string | undefined | null): boolean {
  if (!name) return true;
  return /^Community\s+\d+$/i.test(name.trim());
}

/** Template briefs start with **ModuleName** — treat as non-LLM placeholder. */
export function isPlaceholderBrief(summary: string | undefined | null): boolean {
  if (!summary?.trim()) return true;
  return /^\*\*[^*]+\*\*\s+groups\s+\d+\s+components/i.test(summary.trim());
}
