"use client";

import { useQuery } from "@tanstack/react-query";
import { architectApi } from "@/lib/api";
import { useGraph } from "@/lib/hooks/use-graphs";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";
import { ViolationsTable } from "@/components/architect/violations-table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Violation } from "@/lib/types";

export default function ArchitectPage() {
  const { graphId } = useRepositoryParams();
  const { data: graph } = useGraph(graphId);
  const enabled = graph?.status === "ready";

  const { data: violations, isLoading: violationsLoading } = useQuery({
    queryKey: ["architect", graphId, "violations"],
    queryFn: () => architectApi.violations(graphId),
    enabled,
  });
  const { data: cycleData, isLoading: cyclesLoading } = useQuery({
    queryKey: ["architect", graphId, "cycles"],
    queryFn: () => architectApi.circularDeps(graphId),
    enabled,
  });
  const { data: anomalies, isLoading: anomaliesLoading } = useQuery({
    queryKey: ["architect", graphId, "anomalies"],
    queryFn: () => architectApi.anomalies(graphId),
    enabled,
  });

  const loading = violationsLoading || cyclesLoading || anomaliesLoading;

  if (graph && graph.status !== "ready") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Architecture governance</CardTitle>
          <CardDescription>Available after indexing completes.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (loading) return <Skeleton className="h-64" />;

  const policyViolations = (violations?.violations ?? []) as Violation[];
  const structuralFindings = (violations?.structural_findings ?? []) as Violation[];
  const cycles = cycleData?.cycles ?? [];
  const cycleApprox = cycleData?.approximate;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Custom policy violations ({violations?.count ?? 0})
          </CardTitle>
          <CardDescription>
            {violations?.policies_configured
              ? "Edges that break your uploaded architecture rules."
              : "No custom policy file yet — upload rules via the API to enforce team standards."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ViolationsTable violations={policyViolations} emptyMessage="No custom policy violations." />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Built-in structural signals ({structuralFindings.length})
          </CardTitle>
          <CardDescription>
            Automatic checks for hubs, cyclic groups, coupling, and unreferenced code — no setup required.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ViolationsTable
            violations={structuralFindings}
            emptyMessage="No structural issues detected with current heuristics."
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Circular dependencies ({cycleData?.count ?? cycles.length})
          </CardTitle>
          {cycleApprox && (
            <CardDescription>
              Large graph: showing cyclic groups (strongly connected components), not every simple cycle.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {cycles.length === 0 ? (
            <p className="text-muted-foreground">No circular dependency groups detected.</p>
          ) : (
            cycles.slice(0, 12).map((c, i) => (
              <div key={i} className="border rounded p-3 font-mono text-xs">
                {(c.cycle ?? []).map((n) => n.label).join(" → ")}
                <span className="text-muted-foreground ml-2">
                  ({c.length} {c.approximate_group ? "in group" : "hops"})
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Anomalies ({(anomalies ?? []).length})</CardTitle>
          <CardDescription>Drift signals: god objects, fragmentation, coupling, isolation.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(anomalies ?? []).length === 0 ? (
            <p className="text-muted-foreground">No anomalies flagged.</p>
          ) : (
            (anomalies ?? []).slice(0, 15).map((a, i) => (
              <div key={i} className="flex gap-2 border-b border-border pb-2">
                <span className="text-yellow-400 uppercase text-xs shrink-0">{a.severity}</span>
                <span>{a.message}</span>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
