"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RoleBadge, StatusBadge } from "@/components/graphs/status-badge";
import { useDeleteGraph } from "@/lib/hooks/use-graphs";
import type { GraphMeta } from "@/lib/types";
import { repositoryPath } from "@/lib/routes";
import { Network, GitBranch, Trash2 } from "lucide-react";

export function GraphCard({ graph }: { graph: GraphMeta }) {
  const href =
    graph.project_id != null
      ? repositoryPath(graph.project_id, graph.id)
      : `/graphs/${graph.id}`;
  const del = useDeleteGraph(graph.project_id ?? undefined);

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete graph "${graph.name}"?`)) return;
    await del.mutateAsync(graph.id);
  };

  return (
    <Card className="hover:border-primary/50 transition-colors h-full relative group">
      <Link href={href} className="block">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base truncate pr-8">{graph.name}</CardTitle>
            <StatusBadge status={graph.status} />
          </div>
          <div className="flex gap-2 mt-1 flex-wrap">
            <RoleBadge role={graph.graph_role} />
          </div>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p className="truncate font-mono text-xs">{graph.source_path}</p>
          {graph.status === "ready" && (
            <div className="flex gap-4 text-xs">
              <span className="flex items-center gap-1">
                <Network className="h-3 w-3" />
                {graph.node_count} nodes
              </span>
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {graph.edge_count} edges
              </span>
            </div>
          )}
          {graph.error && <p className="text-red-400 text-xs">{graph.error}</p>}
        </CardContent>
      </Link>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-3 right-3 h-8 w-8 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive"
        onClick={handleDelete}
        disabled={del.isPending}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </Card>
  );
}
