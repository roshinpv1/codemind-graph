"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { RoleBadge, StatusBadge } from "@/components/graphs/status-badge";
import { Button } from "@/components/ui/button";
import { useDeleteGraph } from "@/lib/hooks/use-graphs";
import type { GraphMeta } from "@/lib/types";
import { Trash2 } from "lucide-react";

const tabs = [
  { href: "", label: "Overview" },
  { href: "/coverage", label: "Coverage" },
  { href: "/architect", label: "Architecture" },
  { href: "/security", label: "Security" },
  { href: "/health", label: "Health" },
  { href: "/search", label: "Search" },
  { href: "/docs", label: "Docs" },
];

export function GraphTabs({ graph }: { graph: GraphMeta }) {
  const pathname = usePathname();
  const router = useRouter();
  const base = `/graphs/${graph.id}`;
  const del = useDeleteGraph(graph.project_id ?? undefined);

  const handleDelete = async () => {
    if (!confirm(`Delete graph "${graph.name}"?`)) return;
    await del.mutateAsync(graph.id);
    if (graph.project_id) {
      router.push(`/projects/${graph.project_id}`);
    } else {
      router.push("/projects");
    }
  };

  return (
    <div className="mb-6 border-b border-border pb-4">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <h1 className="text-2xl font-bold">{graph.name}</h1>
        <StatusBadge status={graph.status} />
        <RoleBadge role={graph.graph_role} />
        {graph.project_id && (
          <Link href={`/projects/${graph.project_id}`} className="text-sm text-primary hover:underline">
            View project
          </Link>
        )}
        {graph.status === "ready" && (
          <span className="text-sm text-muted-foreground">
            {graph.node_count} nodes · {graph.edge_count} edges
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
          Graph is {graph.status}. Analysis tabs unlock when indexing completes.
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
