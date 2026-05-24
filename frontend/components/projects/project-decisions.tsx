"use client";

import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function ProjectDecisions({ projectId }: { projectId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["projects", projectId, "decisions"],
    queryFn: () => projectsApi.decisions(projectId),
    enabled: !!projectId,
  });

  if (isLoading) return <Skeleton className="h-32" />;

  const decisions = data?.decisions ?? [];
  if (decisions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No architectural decisions found yet. Add # WHY, # DECISION, or # TRADEOFF comments in source, then re-ingest and refresh understanding.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {decisions.map((d, i) => {
        const row = d as Record<string, string>;
        return (
          <Card key={i}>
            <CardHeader className="py-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  {row.kind || "note"}
                </span>
                {row.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-sm text-muted-foreground">
              {row.detail}
              {row.source_file && (
                <p className="mt-1 font-mono text-xs">{row.source_file}</p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </ul>
  );
}
