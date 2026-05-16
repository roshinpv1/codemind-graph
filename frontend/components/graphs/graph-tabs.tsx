"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { RoleBadge, StatusBadge } from "@/components/graphs/status-badge";
import { Button } from "@/components/ui/button";
import { useDeleteGraph } from "@/lib/hooks/use-graphs";
import { repositoryPath, projectPath } from "@/lib/routes";
import type { GraphMeta } from "@/lib/types";
import { Trash2, ChevronLeft } from "lucide-react";

const tabs = [
  { href: "", label: "Overview" },
  { href: "/coverage", label: "Coverage" },
  { href: "/architect", label: "Architecture" },
  { href: "/security", label: "Security" },
  { href: "/health", label: "Health" },
  { href: "/search", label: "Search" },
  { href: "/docs", label: "Docs" },
];

export function GraphTabs({ graph, projectId }: { graph: GraphMeta; projectId: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const base = repositoryPath(projectId, graph.id);
  const del = useDeleteGraph(projectId);

  const handleDelete = async () => {
    if (!confirm(`Delete repository "${graph.name}"?`)) return;
    await del.mutateAsync(graph.id);
    router.push(projectPath(projectId));
  };

  return (
    <div className="mb-6 border-b border-border pb-4">
      <Link
        href={projectPath(projectId)}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to project
      </Link>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <h1 className="text-2xl font-bold">{graph.name}</h1>
        <StatusBadge status={graph.status} />
        <RoleBadge role={graph.graph_role} />
        {graph.status === "ready" && (
          <span className="text-sm text-muted-foreground">
            {graph.node_count} components · {graph.edge_count} relationships
          </span>
        )}
        <Button
          variant="destructive"
          size="sm"
          className="ml-auto"
          onClick={handleDelete}
          disabled={del.isPending}
        >
          <Trash2 className="h-4 w-4 mr-1" />
          Delete
        </Button>
      </div>
      {graph.status !== "ready" && (
        <p className="text-sm text-yellow-400 mb-4">
          Indexing is {graph.status}. Analysis tabs unlock when this repository is ready.
        </p>
      )}
      <nav className="flex flex-wrap gap-1">
        {tabs.map(({ href, label }) => {
          const full = `${base}${href}`;
          const active = href === "" ? pathname === base : pathname.startsWith(full);
          return (
            <Link
              key={href}
              href={full}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
                graph.status !== "ready" && href !== "" && "pointer-events-none opacity-40",
              )}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
