"use client";

import { cn } from "@/lib/utils";

const links = [
  { id: "repositories", label: "Repositories" },
  { id: "understanding", label: "Understanding" },
  { id: "dna", label: "DNA" },
  { id: "ask", label: "Q&A" },
  { id: "coverage", label: "Coverage" },
] as const;

interface ProjectSubnavProps {
  projectId?: string;
}

export function ProjectSubnav({ projectId }: ProjectSubnavProps) {
  return (
    <nav
      aria-label="On this page"
      className="sticky top-0 z-10 -mx-1 mb-2 flex gap-1 overflow-x-auto border-b border-border bg-background/95 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/80"
    >
      {links.map(({ id, label }) => (
        <a
          key={id}
          href={`#${id}`}
          className={cn(
            "shrink-0 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors",
            "hover:bg-accent hover:text-foreground",
          )}
        >
          {label}
        </a>
      ))}
      {projectId && (
        <a
          href={`/projects/${projectId}/risk`}
          className={cn(
            "shrink-0 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors",
            "hover:bg-accent hover:text-foreground",
          )}
        >
          PR risk
        </a>
      )}
    </nav>
  );
}
