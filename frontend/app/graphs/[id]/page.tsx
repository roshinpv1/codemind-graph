"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { graphsApi } from "@/lib/api";
import { useGraphStats } from "@/lib/hooks/use-graphs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import ReactMarkdown from "react-markdown";

export default function GraphOverviewPage() {
  const id = useParams().id as string;
  const { data: stats, isLoading: statsLoading } = useGraphStats(id);
  const { data: communities } = useQuery({
    queryKey: ["graphs", id, "communities"],
    queryFn: () => graphsApi.communities(id),
    enabled: !!id,
  });
  const { data: gods } = useQuery({
    queryKey: ["graphs", id, "gods"],
    queryFn: () => graphsApi.gods(id),
    enabled: !!id,
  });
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["graphs", id, "summarize"],
    queryFn: () => graphsApi.summarize(id),
    enabled: !!id,
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <Skeleton className="h-24 col-span-4" />
        ) : stats ? (
          <>
            <StatCard label="Nodes" value={stats.node_count} />
            <StatCard label="Edges" value={stats.edge_count} />
            <StatCard label="Communities" value={stats.community_count} />
            <StatCard label="Avg degree" value={stats.avg_degree.toFixed(2)} />
          </>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Communities</CardTitle>
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
            <CardTitle className="text-base">God Nodes</CardTitle>
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
        <CardHeader>
          <CardTitle className="text-base">Executive Summary</CardTitle>
        </CardHeader>
        <CardContent className="prose prose-invert prose-sm max-w-none">
          {summaryLoading ? (
            <Skeleton className="h-32" />
          ) : (
            <ReactMarkdown>
              {String((summary as Record<string, unknown>)?.summary ?? (summary as Record<string, unknown>)?.narrative ?? "Run LLM summarize to generate an executive summary.")}
            </ReactMarkdown>
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
