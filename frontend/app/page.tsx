"use client";

import { PageHeader } from "@/components/layout/page-header";
import { StatCards } from "@/components/dashboard/stat-cards";
import { useGraphs } from "@/lib/hooks/use-graphs";
import { useProjects } from "@/lib/hooks/use-projects";
import { useQuery } from "@tanstack/react-query";
import { coverageApi } from "@/lib/api";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardPage() {
  const { data: graphs, isLoading: graphsLoading } = useGraphs();
  const { data: projects } = useProjects();

  const readyGraphs = (graphs ?? []).filter((g) => g.status === "ready");

  const { data: coverageSamples } = useQuery({
    queryKey: ["dashboard-coverage"],
    queryFn: async () => {
      const samples = readyGraphs.slice(0, 5);
      const results = await Promise.allSettled(
        samples.map((g) => coverageApi.summary(g.id)),
      );
      const pcts = results
        .filter((r): r is PromiseFulfilledResult<Awaited<ReturnType<typeof coverageApi.summary>>> => r.status === "fulfilled")
        .map((r) => r.value.functional.coverage_pct);
      return pcts.length ? pcts.reduce((a, b) => a + b, 0) / pcts.length : null;
    },
    enabled: readyGraphs.length > 0,
  });

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Architecture health at a glance"
        actions={null}
      />

      <div className="space-y-8">
        <StatCards
          graphCount={graphs?.length ?? 0}
          projectCount={projects?.length ?? 0}
          avgCoverage={coverageSamples ?? null}
          violationCount={null}
        />

        {projects && projects.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4">Projects</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((p) => (
                <Link key={p.id} href={`/projects/${p.id}`}>
                  <Card className="hover:border-primary/50 transition-colors">
                    <CardHeader>
                      <CardTitle className="text-base">{p.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                      {p.graphs.length} repositor{p.graphs.length !== 1 ? "ies" : "y"} indexed
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        )}

        {!graphsLoading && (projects?.length ?? 0) === 0 && (
          <Card className="p-8 text-center text-muted-foreground">
            <p>Create a project, then ingest repositories into role slots (source, test, CI, CD).</p>
            <Button className="mt-4" asChild>
              <Link href="/projects">Create a project</Link>
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
}
