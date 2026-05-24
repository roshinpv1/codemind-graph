"use client";

import { useQuery } from "@tanstack/react-query";
import { dueDiligenceApi, ApiError } from "@/lib/api";
import { useGraph } from "@/lib/hooks/use-graphs";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

function QueryError({ message }: { message: string }) {
  return <p className="text-sm text-destructive">{message}</p>;
}

export default function HealthPage() {
  const { graphId } = useRepositoryParams();
  const { data: graph } = useGraph(graphId);

  const enabled = graph?.status === "ready";

  const {
    data: score,
    isLoading: scoreLoading,
    isError: scoreError,
    error: scoreErr,
  } = useQuery({
    queryKey: ["health", graphId, "score"],
    queryFn: () => dueDiligenceApi.score(graphId),
    enabled,
    retry: 1,
  });

  const { data: debt, isLoading: debtLoading, isError: debtError } = useQuery({
    queryKey: ["health", graphId, "debt"],
    queryFn: () => dueDiligenceApi.debt(graphId),
    enabled,
    retry: 1,
  });

  const { data: deadTiered, isLoading: deadLoading, isError: deadError } = useQuery({
    queryKey: ["health", graphId, "dead-tiered"],
    queryFn: () => dueDiligenceApi.deadCodeTiered(graphId),
    enabled,
    retry: 1,
  });

  if (graph && graph.status !== "ready") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Architecture health</CardTitle>
          <CardDescription>
            Available after indexing completes. Current status: {graph.status}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (scoreLoading || debtLoading || deadLoading) {
    return <Skeleton className="h-64" />;
  }

  if (scoreError) {
    const msg =
      scoreErr instanceof ApiError
        ? scoreErr.message
        : "Could not load health score. Restart the API after an update and try again.";
    return <QueryError message={msg} />;
  }

  const breakdown = score?.breakdown ?? {};
  const breakdownChart = Object.entries(breakdown).map(([key, value]) => ({
    name: key.replace(/_/g, " "),
    points: Number(value),
  }));

  const debtChart = (debt ?? [])
    .map((d) => d as Record<string, unknown>)
    .filter((d) => d.hub_label)
    .slice(0, 12)
    .map((d) => ({
      name: String(d.hub_label ?? "").slice(0, 24),
      debt: Number(d.debt_score ?? 0),
    }));

  const summary = score?.summary as Record<string, unknown> | undefined;

  return (
    <div className="space-y-6">
      {score && (
        <Card className="p-8 text-center">
          <p className="text-sm text-muted-foreground">Architecture health score</p>
          <p className="text-6xl font-bold text-primary mt-2">{score.score}</p>
          <p className="text-lg text-muted-foreground mt-1">Grade {score.rating}</p>
          {summary && (
            <p className="text-xs text-muted-foreground mt-4">
              {String(summary.nodes)} components · {String(summary.edges)} relationships ·{" "}
              {String(summary.communities)} areas
              {summary.circular_deps_approximate ? " · cycle estimate" : ""}
            </p>
          )}
        </Card>
      )}

      {breakdownChart.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Score breakdown</CardTitle>
          </CardHeader>
          <CardContent className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={breakdownChart} layout="vertical" margin={{ left: 8 }}>
                <XAxis type="number" domain={[0, 30]} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="points" fill="hsl(var(--primary))" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coupling by product area</CardTitle>
          <CardDescription>Higher bars suggest more cross-area coupling debt</CardDescription>
        </CardHeader>
        <CardContent className="h-64">
          {debtError ? (
            <QueryError message="Could not load coupling data." />
          ) : debtChart.length === 0 ? (
            <p className="text-sm text-muted-foreground">No community data yet — re-index this repository.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={debtChart}>
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="debt" fill="hsl(var(--primary))" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dead code tiers</CardTitle>
          <CardDescription>
            Safe to remove (no incoming or outgoing) vs review first (possible entry/orchestrator)
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm space-y-4 max-h-96 overflow-auto">
          {deadError ? (
            <QueryError message="Could not load dead-code tiers." />
          ) : (
            <>
              <div>
                <p className="text-xs font-medium text-green-600/90 mb-2">
                  Safe to remove ({deadTiered?.safe_count ?? 0})
                </p>
                {(deadTiered?.safe_to_remove ?? []).length === 0 ? (
                  <p className="text-muted-foreground text-xs">None</p>
                ) : (
                  (deadTiered?.safe_to_remove ?? []).slice(0, 15).map((n) => (
                    <div key={String(n.id)} className="flex justify-between border-b pb-1 font-mono text-xs gap-2">
                      <span className="truncate">{String(n.label)}</span>
                      <span className="text-muted-foreground truncate max-w-[45%]">{String(n.source_file)}</span>
                    </div>
                  ))
                )}
              </div>
              <div>
                <p className="text-xs font-medium text-amber-500/90 mb-2">
                  Review first ({deadTiered?.review_count ?? 0})
                </p>
                {(deadTiered?.review_first ?? []).slice(0, 15).map((n) => (
                  <div key={String(n.id)} className="flex justify-between border-b pb-1 font-mono text-xs gap-2">
                    <span className="truncate">{String(n.label)}</span>
                    <span className="text-muted-foreground truncate max-w-[45%]">
                      {String(n.source_file)} · out {String(n.out_degree)}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
