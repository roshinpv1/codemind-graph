"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { architectApi } from "@/lib/api";
import { ViolationsTable } from "@/components/architect/violations-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Violation } from "@/lib/types";

export default function ArchitectPage() {
  const id = useParams().id as string;
  const { data: violations, isLoading } = useQuery({
    queryKey: ["architect", id, "violations"],
    queryFn: () => architectApi.violations(id),
  });
  const { data: cycles } = useQuery({
    queryKey: ["architect", id, "cycles"],
    queryFn: () => architectApi.circularDeps(id),
  });
  const { data: anomalies } = useQuery({
    queryKey: ["architect", id, "anomalies"],
    queryFn: () => architectApi.anomalies(id),
  });

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Policy Violations ({violations?.count ?? 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <ViolationsTable violations={(violations?.violations ?? []) as Violation[]} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Circular Dependencies ({(cycles ?? []).length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(cycles ?? []).slice(0, 10).map((c, i) => (
            <div key={i} className="border rounded p-3 font-mono text-xs">
              {(c.cycle ?? []).map((n) => n.label).join(" → ")}
              <span className="text-muted-foreground ml-2">({c.length} hops)</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Anomalies</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(anomalies ?? []).slice(0, 15).map((a, i) => (
            <div key={i} className="flex gap-2 border-b border-border pb-2">
              <span className="text-yellow-400 uppercase text-xs">{a.severity}</span>
              <span>{a.message}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
