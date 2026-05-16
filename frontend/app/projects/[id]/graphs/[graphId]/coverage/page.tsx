"use client";

import { useState } from "react";
import { useCoverageSummary, useFunctionalCoverage, useCoverageFiles } from "@/lib/hooks/use-coverage";
import { CoverageRing } from "@/components/coverage/coverage-ring";
import { EntryPointTable } from "@/components/coverage/entry-point-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { gradeColor, cn } from "@/lib/utils";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";

export default function CoveragePage() {
  const { graphId } = useRepositoryParams();
  const [mode, setMode] = useState<"all" | "covered" | "uncovered">("uncovered");
  const { data: summary, isLoading } = useCoverageSummary(graphId);
  const { data: functional } = useFunctionalCoverage(graphId, mode);
  const { data: files } = useCoverageFiles(graphId, "functional");

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 sm:grid-cols-2 max-w-xl">
        {summary && (
          <>
            <Card className="p-6 flex flex-col items-center">
              <CoverageRing
                pct={summary.functional.coverage_pct}
                grade={summary.functional.grade}
                label="Functional"
              />
              <p className="text-xs text-muted-foreground mt-4 text-center">
                {summary.functional.entry_points_covered} / {summary.functional.entry_points_total} entry points
              </p>
            </Card>
            <Card className="p-6 flex flex-col items-center">
              <CoverageRing
                pct={summary.unit.coverage_pct}
                grade={summary.unit.grade}
                label="Unit (all nodes)"
              />
              <p className="text-xs text-muted-foreground mt-4 text-center">
                {summary.unit.prod_nodes_covered} / {summary.unit.prod_nodes_total} nodes
              </p>
            </Card>
          </>
        )}
      </div>

      <Tabs defaultValue="gaps">
        <TabsList>
          <TabsTrigger value="gaps">Entry Points</TabsTrigger>
          <TabsTrigger value="files">By File</TabsTrigger>
        </TabsList>
        <TabsContent value="gaps" className="space-y-4">
          <div className="flex gap-2">
            {(["all", "covered", "uncovered"] as const).map((m) => (
              <Button
                key={m}
                size="sm"
                variant={mode === m ? "default" : "outline"}
                onClick={() => setMode(m)}
              >
                {m}
              </Button>
            ))}
          </div>
          <EntryPointTable rows={functional?.all_entry_points ?? []} />
        </TabsContent>
        <TabsContent value="files">
          <div className="space-y-2">
            {(files?.worst_files ?? files?.files ?? []).slice(0, 20).map((f, i) => {
              const file = f as Record<string, unknown>;
              const pct = Number(file.coverage_pct ?? 0);
              const grade = String(file.grade ?? "F");
              return (
                <div key={i} className="flex items-center justify-between border rounded-lg p-3 text-sm">
                  <span className="font-mono text-xs truncate flex-1">{String(file.file)}</span>
                  <span className={cn("font-bold ml-4", gradeColor(grade))}>{grade}</span>
                  <span className="text-muted-foreground ml-2 w-16 text-right">{pct}%</span>
                </div>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
