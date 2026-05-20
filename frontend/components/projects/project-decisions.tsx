"use client";

import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ProjectDecisionsProps {
  projectId: string;
}

export function ProjectDecisions({ projectId }: ProjectDecisionsProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["project", projectId, "decisions"],
    queryFn: () => projectsApi.decisions(projectId),
  });

  if (isLoading) return <Skeleton className="h-32" />;

  const decisions = (data?.decisions ?? []) as {
    kind?: string;
    title?: string;
    detail?: string;
    source_file?: string;
    line?: number;
    repository?: string;
  }[];

  if (isError || decisions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Architecture decisions</CardTitle>
          <CardDescription>
            Inline markers like <code className="text-xs"># WHY:</code> or{" "}
            <code className="text-xs"># DECISION:</code> in your application code appear here after
            refresh project understanding.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Architecture decisions</CardTitle>
        <CardDescription>
          {decisions.length} documented rationale{decisions.length === 1 ? "" : "s"} from code
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 max-h-96 overflow-auto text-sm">
        {decisions.map((d) => (
          <div
            key={`${d.source_file}-${d.line}-${d.title}`}
            className="border-b border-border/60 pb-3 last:border-0"
          >
            <p className="font-medium">
              <span className="text-xs uppercase text-muted-foreground mr-2">{d.kind}</span>
              {d.title}
            </p>
            {d.detail && d.detail !== d.title && (
              <p className="text-muted-foreground mt-1">{d.detail}</p>
            )}
            <p className="text-xs font-mono text-muted-foreground mt-1 truncate">
              {d.repository ? `${d.repository} · ` : ""}
              {d.source_file}
              {d.line ? `:${d.line}` : ""}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
