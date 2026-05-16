"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, AlertTriangle } from "lucide-react";
import { RichText } from "@/components/ui/rich-text";
import { useEffect } from "react";

interface ProjectBriefingProps {
  projectId: string;
}

const healthColor: Record<string, string> = {
  green: "text-emerald-400",
  yellow: "text-yellow-400",
  red: "text-red-400",
  unknown: "text-muted-foreground",
};

export function ProjectBriefing({ projectId }: ProjectBriefingProps) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["projects", projectId, "briefing"],
    queryFn: () => projectsApi.briefing(projectId),
    refetchInterval: (q) => (q.state.data?.ready ? false : 15_000),
  });

  const { data: delta } = useQuery({
    queryKey: ["projects", projectId, "delta"],
    queryFn: () => projectsApi.delta(projectId),
    enabled: !!data?.ready,
  });

  const synthesize = useMutation({
    mutationFn: () => projectsApi.synthesize(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", projectId] });
    },
  });

  useEffect(() => {
    if (data?.ready) {
      projectsApi.visit(projectId).catch(() => {});
    }
  }, [data?.ready, projectId]);

  if (isLoading) return <Skeleton className="h-48" />;

  if (!data?.ready) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="text-base">Project briefing</CardTitle>
          <CardDescription>
            {data?.message ??
              "Structural snapshot (areas, findings, metrics). For the full AI narrative, use Code Project DNA above."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => synthesize.mutate()} disabled={synthesize.isPending}>
            {synthesize.isPending ? "Refreshing…" : "Refresh understanding"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const headline = data.headline ?? data.dna?.headline ?? "Project briefing";
  const summary = data.summary ?? data.dna?.summary;
  const healthKey = String(data.health_key ?? data.dna?.health ?? "unknown");
  const healthLabel = data.health_label ?? healthKey;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-lg">{headline}</CardTitle>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => synthesize.mutate()}
          disabled={synthesize.isPending}
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${synthesize.isPending ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {summary && (
          <RichText content={summary} mode="auto" variant="inline" className="max-w-3xl" />
        )}
        <div className="flex flex-wrap gap-3 text-sm">
          <Badge variant="outline" className={healthColor[healthKey]}>
            {healthLabel}
          </Badge>
          {data.capabilities_tested_pct != null && (
            <Badge variant="outline">{data.capabilities_tested_pct}% capabilities tested</Badge>
          )}
          {data.capabilities_untested != null && data.capabilities_untested > 0 && (
            <Badge variant="outline">{data.capabilities_untested} untested</Badge>
          )}
          {data.open_findings != null && (
            <Badge variant="outline">{data.open_findings} open findings</Badge>
          )}
        </div>

        {delta && Boolean(delta.has_delta) && (
          <div className="rounded-md border border-yellow-500/30 bg-yellow-500/5 p-3 text-sm">
            <p className="font-medium text-yellow-400/90 mb-1">Since your last visit</p>
            <ul className="list-disc pl-4 text-muted-foreground space-y-0.5">
              {((delta.metric_changes as string[]) ?? []).map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {data.top_findings && data.top_findings.length > 0 && (
          <section>
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              Top findings
            </h3>
            <ul className="space-y-2 text-sm">
              {data.top_findings.slice(0, 5).map((f) => (
                <li key={f.id} className="rounded-md border p-2">
                  <span className="text-xs uppercase text-muted-foreground">
                    {f.severity_label ?? f.severity}
                  </span>
                  {f.category && (
                    <span className="text-xs text-muted-foreground ml-2">· {f.category}</span>
                  )}
                  <p className="font-medium">{f.title}</p>
                  {f.why_it_matters && (
                    <p className="text-muted-foreground text-xs mt-0.5">{f.why_it_matters}</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {data.top_areas && data.top_areas.length > 0 && (
          <section>
            <h3 className="text-sm font-semibold mb-2">Product areas</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              {data.top_areas.map((a) => (
                <li key={a.id}>
                  <span className="text-foreground font-medium">{a.name}</span>
                  {a.component_count != null && ` · ${a.component_count} components`}
                </li>
              ))}
            </ul>
          </section>
        )}

        <p className="text-xs text-muted-foreground">
          Updated{" "}
          {data.understanding_updated_at ?? data.synthesized_at
            ? new Date(
                (data.understanding_updated_at ?? data.synthesized_at) as string,
              ).toLocaleString()
            : "—"}
          {" · "}
          <Link href={`/projects/${projectId}/investigate`} className="text-primary hover:underline">
            Investigate
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
