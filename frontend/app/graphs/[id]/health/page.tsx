"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { dueDiligenceApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function HealthPage() {
  const id = useParams().id as string;
  const { data: score, isLoading } = useQuery({
    queryKey: ["health", id, "score"],
    queryFn: () => dueDiligenceApi.score(id),
  });
  const { data: debt } = useQuery({
    queryKey: ["health", id, "debt"],
    queryFn: () => dueDiligenceApi.debt(id),
  });
  const { data: deadCode } = useQuery({
    queryKey: ["health", id, "dead"],
    queryFn: () => dueDiligenceApi.deadCode(id),
  });

  if (isLoading) return <Skeleton className="h-64" />;

  const debtChart = (debt ?? []).slice(0, 12).map((d) => ({
    name: String((d as Record<string, unknown>).hub_label ?? "").slice(0, 20),
    debt: Number((d as Record<string, unknown>).debt_score ?? 0),
  }));

  return (
    <div className="space-y-6">
      {score && (
        <Card className="p-8 text-center">
          <p className="text-sm text-muted-foreground">Architecture Health Score</p>
          <p className="text-6xl font-bold text-primary mt-2">{score.score}</p>
          <p className="text-lg text-muted-foreground mt-1">Rating: {score.rating}</p>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">Technical Debt by Community</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={debtChart}>
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="debt" fill="hsl(var(--primary))" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Dead Code Candidates</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-2 max-h-80 overflow-auto">
          {(deadCode ?? []).slice(0, 20).map((n, i) => (
            <div key={i} className="flex justify-between border-b pb-2 font-mono text-xs">
              <span>{String((n as Record<string, unknown>).label)}</span>
              <span className="text-muted-foreground">{String((n as Record<string, unknown>).source_file)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
