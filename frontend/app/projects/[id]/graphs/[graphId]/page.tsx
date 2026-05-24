"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { graphsApi } from "@/lib/api";
import { useGraphStats } from "@/lib/hooks/use-graphs";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RichText } from "@/components/ui/rich-text";
import { LlmRegenerateButton } from "@/components/ui/llm-regenerate-button";

export default function GraphOverviewPage() {
  const { graphId } = useRepositoryParams();
  const qc = useQueryClient();
  const { data: stats, isLoading: statsLoading } = useGraphStats(graphId);
  const { data: communities } = useQuery({
    queryKey: ["graphs", graphId, "communities"],
    queryFn: () => graphsApi.communities(graphId),
    enabled: !!graphId,
  });
  const { data: gods } = useQuery({
    queryKey: ["graphs", graphId, "gods"],
    queryFn: () => graphsApi.gods(graphId),
    enabled: !!graphId,
  });
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["graphs", graphId, "summarize"],
    queryFn: () => graphsApi.summarize(graphId),
    enabled: !!graphId,
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <Skeleton className="h-24 col-span-4" />
        ) : stats ? (
          <>
            <StatCard label="Components" value={stats.node_count} />
            <StatCard label="Relationships" value={stats.edge_count} />
            <StatCard label="Modules" value={stats.community_count} />
            <StatCard label="Avg connections" value={stats.avg_degree.toFixed(2)} />
          </>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Largest modules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(communities ?? []).slice(0, 8).map((c) => (
              <div key={c.community_id} className="flex justify-between border-b border-border pb-2">
                <span className="font-mono text-xs">{c.hub_label}</span>
                <span className="text-muted-foreground">{c.size} members</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Highly connected hubs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(gods ?? []).slice(0, 8).map((g, i) => (
              <div key={i} className="flex justify-between border-b border-border pb-2">
                <span className="font-mono text-xs truncate">
                  {String((g as Record<string, unknown>).label ?? (g as Record<string, unknown>).id ?? i)}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <CardTitle className="text-base">Summary</CardTitle>
          {graphId && (
            <LlmRegenerateButton
              label="Generate summary"
              pendingLabel="Generating…"
              regenerateLabel="Regenerate summary"
              visibility="always"
              hasContent={Boolean(
                (summary as Record<string, unknown> | undefined)?.summary ??
                  (summary as Record<string, unknown> | undefined)?.narrative,
              )}
              onRegenerate={() => graphsApi.summarize(graphId)}
              onSuccess={() => qc.invalidateQueries({ queryKey: ["graphs", graphId, "summarize"] })}
            />
          )}
        </CardHeader>
        <CardContent>
          {summaryLoading ? (
            <Skeleton className="h-32" />
          ) : (
            <RichText
              content={String(
                (summary as Record<string, unknown>)?.summary ??
                  (summary as Record<string, unknown>)?.narrative ??
                  "",
              )}
              mode="auto"
              variant="panel"
              className="max-w-none"
              emptyMessage="Generate an executive summary with the button above (requires LLM in .env)."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
      </CardContent>
    </Card>
  );
}
