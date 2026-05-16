/** Normalize AI / markdown text for consistent display. */

export function normalizeTextContent(raw: string | null | undefined): string {
  if (!raw) return "";
  let text = raw.replace(/\r\n/g, "\n").trim();
  // Collapse runs of 3+ blank lines to double newline
  text = text.replace(/\n{3,}/g, "\n\n");
  // Trim trailing spaces on each line
  text = text
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/g, ""))
    .join("\n");
  return text;
}

export function looksLikeMarkdown(text: string): boolean {
  if (!text) return false;
  return (
    /^#{1,6}\s/m.test(text) ||
    /^\s*[-*+]\s+/m.test(text) ||
    /^\s*\d+\.\s+/m.test(text) ||
    /\*\*[^*]+\*\*/.test(text) ||
    /^>\s/m.test(text) ||
    /`[^`]+`/.test(text)
  );
}

export function splitPlainParagraphs(text: string): string[] {
  return normalizeTextContent(text)
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}
