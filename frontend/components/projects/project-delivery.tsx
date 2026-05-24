"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export function ProjectDelivery({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const [namespace, setNamespace] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["projects", projectId, "delivery"],
    queryFn: () => projectsApi.delivery(projectId),
    enabled: !!projectId,
    retry: false,
  });

  const snapshot = useMutation({
    mutationFn: () =>
      projectsApi.clusterSnapshot(projectId, {
        namespace: namespace.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", projectId, "delivery"] });
      qc.invalidateQueries({ queryKey: ["projects", projectId, "briefing"] });
    },
  });

  if (isLoading) return <Skeleton className="h-40" />;
  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        Refresh project understanding after indexing a CD repository to see delivery intelligence.
      </p>
    );
  }

  const delivery = (data?.delivery ?? {}) as Record<string, unknown>;
  const drift = (delivery.drift ?? []) as Record<string, unknown>[];
  const snap = data?.snapshot as Record<string, unknown> | null | undefined;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Static CD + live cluster</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2">
          <p>
            <span className="text-muted-foreground">Static resources:</span>{" "}
            {String(delivery.static_resource_count ?? 0)}
          </p>
          <p>
            <span className="text-muted-foreground">Last snapshot:</span>{" "}
            {snap?.captured_at
              ? `${snap.captured_at} (${snap.resource_count} resources)`
              : "none — capture below"}
          </p>
          <div className="flex flex-wrap gap-2 items-end pt-2">
            <div className="flex-1 min-w-[140px]">
              <label className="text-xs text-muted-foreground">Namespace (optional)</label>
              <Input
                value={namespace}
                onChange={(e) => setNamespace(e.target.value)}
                placeholder="default"
                className="mt-1"
              />
            </div>
            <Button
              size="sm"
              onClick={() => snapshot.mutate()}
              disabled={snapshot.isPending}
            >
              {snapshot.isPending ? "Capturing…" : "Refresh cluster snapshot"}
            </Button>
          </div>
          {snapshot.isError && (
            <p className="text-xs text-destructive">
              {(snapshot.error as Error).message}
            </p>
          )}
        </CardContent>
      </Card>

      {drift.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Drift (declared vs running)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="py-2 pr-4">Resource</th>
                    <th className="py-2 pr-4">Declared</th>
                    <th className="py-2 pr-4">Running</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {drift.slice(0, 20).map((row, i) => (
                    <tr key={i} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono text-xs">{String(row.resource)}</td>
                      <td className="py-2 pr-4">{row.declared ? "yes" : "—"}</td>
                      <td className="py-2 pr-4">{row.running ? "yes" : "—"}</td>
                      <td className="py-2">{String(row.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
