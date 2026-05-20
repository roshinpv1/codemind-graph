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

  const { data: deadCode, isLoading: deadLoading, isError: deadError } = useQuery({
    queryKey: ["health", graphId, "dead"],
    queryFn: () => dueDiligenceApi.deadCode(graphId),
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
          <CardTitle className="text-base">Unreferenced code</CardTitle>
          <CardDescription>Components with no incoming references (possible dead or entry-only code)</CardDescription>
        </CardHeader>
        <CardContent className="text-sm space-y-2 max-h-80 overflow-auto">
          {deadError ? (
            <QueryError message="Could not load dead-code list." />
          ) : (deadCode ?? []).length === 0 ? (
            <p className="text-muted-foreground">None detected with current heuristics.</p>
          ) : (
            (deadCode ?? []).slice(0, 25).map((n) => {
              const row = n as Record<string, unknown>;
              const tier = String(row.tier ?? "");
              const tierLabel = String(row.tier_label ?? "");
              const conf = row.confidence != null ? Number(row.confidence) : null;
              const tierClass =
                tier === "safe_to_remove"
                  ? "text-emerald-500/90"
                  : tier === "review_first"
                    ? "text-yellow-500/90"
                    : "text-muted-foreground";
              return (
                <div
                  key={String(row.id)}
                  className="flex flex-col sm:flex-row sm:justify-between border-b pb-2 font-mono text-xs gap-1"
                >
                  <span className="truncate">{String(row.label)}</span>
                  <span className="flex items-center gap-2 shrink-0">
                    {tierLabel && (
                      <span className={`font-sans text-[10px] uppercase ${tierClass}`}>
                        {tierLabel}
                        {conf != null ? ` (${Math.round(conf * 100)}%)` : ""}
                      </span>
                    )}
                    <span className="text-muted-foreground truncate max-w-[12rem]">
                      {String(row.source_file)}
                    </span>
                  </span>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
