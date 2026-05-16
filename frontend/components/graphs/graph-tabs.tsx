"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { RoleBadge, StatusBadge } from "@/components/graphs/status-badge";
import { Button } from "@/components/ui/button";
import { useDeleteGraph } from "@/lib/hooks/use-graphs";
import { repositoryPath, projectPath } from "@/lib/routes";
import type { GraphMeta } from "@/lib/types";
import { Trash2 } from "lucide-react";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";

const primaryTabs = [
  { href: "", label: "Overview" },
  { href: "/coverage", label: "Coverage" },
  { href: "/health", label: "Health" },
  { href: "/architect", label: "Structure" },
] as const;

const exploreTabs = [
  { href: "/security", label: "Security" },
  { href: "/search", label: "Search" },
  { href: "/docs", label: "Docs" },
] as const;

export function GraphTabs({
  graph,
  projectId,
  projectName,
}: {
  graph: GraphMeta;
  projectId: string;
  projectName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const base = repositoryPath(projectId, graph.id);
  const del = useDeleteGraph(projectId);

  const handleDelete = async () => {
    if (!confirm(`Delete repository "${graph.name}"?`)) return;
    await del.mutateAsync(graph.id);
    router.push(projectPath(projectId));
  };

  const renderTab = (href: string, label: string, size: "md" | "sm" = "md") => {
    const full = `${base}${href}`;
    const active = href === "" ? pathname === base : pathname.startsWith(full);
    return (
      <Link
        key={href || "overview"}
        href={full}
        className={cn(
          "shrink-0 rounded-md transition-colors whitespace-nowrap",
          size === "md" ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs",
          active
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
          graph.status !== "ready" && href !== "" && "pointer-events-none opacity-40",
        )}
      >
        {label}
      </Link>
    );
  };

  return (
    <div className="mb-6 border-b border-border pb-4">
      <Breadcrumbs
        className="mb-3"
        items={[
          { label: "Projects", href: "/projects" },
          { label: projectName ?? "Project", href: projectPath(projectId) },
          { label: graph.name },
        ]}
      />
      <div className="flex flex-wrap items-start gap-3 gap-y-2 mb-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold truncate">{graph.name}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            <StatusBadge status={graph.status} />
            <RoleBadge role={graph.graph_role} />
            {graph.status === "ready" && (
              <span className="text-sm text-muted-foreground">
                {graph.node_count} components · {graph.edge_count} relationships
              </span>
            )}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
          onClick={handleDelete}
          disabled={del.isPending}
        >
          <Trash2 className="h-4 w-4 mr-1" />
          Remove
        </Button>
      </div>
      {graph.status !== "ready" && (
        <p className="text-sm text-amber-400/90 mb-4 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2">
          Indexing is <strong className="font-medium">{graph.status}</strong>. Other tabs unlock when this
          repository is ready.
        </p>
      )}
      <nav className="space-y-2" aria-label="Repository sections">
        <div className="flex gap-1 overflow-x-auto pb-0.5 scrollbar-thin">
          {primaryTabs.map(({ href, label }) => renderTab(href, label))}
        </div>
        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-muted-foreground shrink-0 pr-1">More</span>
          {exploreTabs.map(({ href, label }) => renderTab(href, label, "sm"))}
        </div>
      </nav>
    </div>
  );
}
