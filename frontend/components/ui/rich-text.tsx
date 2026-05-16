"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { looksLikeMarkdown, normalizeTextContent, splitPlainParagraphs } from "@/lib/normalize-text";

export type RichTextVariant = "document" | "panel" | "inline";
export type RichTextMode = "auto" | "markdown" | "plain";

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h2 className="cm-rich-heading cm-rich-h1">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="cm-rich-heading cm-rich-h2">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="cm-rich-heading cm-rich-h3">{children}</h4>
  ),
  h4: ({ children }) => (
    <h5 className="cm-rich-heading cm-rich-h4">{children}</h5>
  ),
  p: ({ children }) => <p className="cm-rich-p">{children}</p>,
  ul: ({ children }) => <ul className="cm-rich-ul">{children}</ul>,
  ol: ({ children }) => <ol className="cm-rich-ol">{children}</ol>,
  li: ({ children }) => <li className="cm-rich-li">{children}</li>,
  strong: ({ children }) => <strong className="cm-rich-strong">{children}</strong>,
  em: ({ children }) => <em className="cm-rich-em">{children}</em>,
  a: ({ href, children }) => (
    <a href={href} className="cm-rich-link" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return <code className={cn("cm-rich-code-block", className)}>{children}</code>;
    }
    return <code className="cm-rich-code">{children}</code>;
  },
  pre: ({ children }) => <pre className="cm-rich-pre">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="cm-rich-quote">{children}</blockquote>,
  hr: () => <hr className="cm-rich-hr" />,
};

const variantShell: Record<RichTextVariant, string> = {
  document: "cm-rich-text cm-rich-text--document",
  panel: "cm-rich-text cm-rich-text--panel",
  inline: "cm-rich-text cm-rich-text--inline",
};

export interface RichTextProps {
  content: string | null | undefined;
  mode?: RichTextMode;
  variant?: RichTextVariant;
  className?: string;
  emptyMessage?: string;
}

export function RichText({
  content,
  mode = "auto",
  variant = "panel",
  className,
  emptyMessage,
}: RichTextProps) {
  const normalized = normalizeTextContent(content);
  if (!normalized) {
    return emptyMessage ? (
      <p className="text-sm text-muted-foreground">{emptyMessage}</p>
    ) : null;
  }

  const useMarkdown =
    mode === "markdown" || (mode === "auto" && looksLikeMarkdown(normalized));

  if (useMarkdown) {
    return (
      <div className={cn(variantShell[variant], className)}>
        <ReactMarkdown components={markdownComponents}>{normalized}</ReactMarkdown>
      </div>
    );
  }

  const paragraphs = splitPlainParagraphs(normalized);
  return (
    <div className={cn(variantShell[variant], "cm-rich-text--plain", className)}>
      {paragraphs.map((para, i) => (
        <p key={i} className="cm-rich-p">
          {para}
        </p>
      ))}
    </div>
  );
}
