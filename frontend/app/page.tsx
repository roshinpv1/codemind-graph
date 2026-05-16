"use client";

import { PageHeader } from "@/components/layout/page-header";
import { StatCards } from "@/components/dashboard/stat-cards";
import { GraphCard } from "@/components/graphs/graph-card";
import { useGraphs, recentGraphs } from "@/lib/hooks/use-graphs";
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

  const recent = recentGraphs(graphs, 5);

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
                      {p.graphs.length} graph{p.graphs.length !== 1 ? "s" : ""} assigned
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        )}

        <section>
          <h2 className="text-lg font-semibold mb-4">Recent Graphs</h2>
          {graphsLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          ) : recent.length === 0 ? (
            <Card className="p-8 text-center text-muted-foreground">
              <p>No graphs yet. Open a project and ingest repositories into role slots.</p>
              <Button className="mt-4" asChild>
                <Link href="/projects">Go to projects</Link>
              </Button>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {recent.map((g) => (
                <GraphCard key={g.id} graph={g} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
