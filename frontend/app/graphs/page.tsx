"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { GraphCard } from "@/components/graphs/graph-card";
import { useGraphs } from "@/lib/hooks/use-graphs";
import { useProjects } from "@/lib/hooks/use-projects";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export default function GraphsPage() {
  const { data: graphs, isLoading } = useGraphs();
  const { data: projects } = useProjects();

  const orphans = (graphs ?? []).filter((g) => !g.project_id);
  const withProject = (graphs ?? []).filter((g) => g.project_id);

  return (
    <>
      <PageHeader
        title="Graphs"
        description="All graphs belong to a project. Ingest new repos from a project page."
        actions={
          <Button variant="outline" asChild>
            <Link href="/projects">Manage projects</Link>
          </Button>
        }
      />

      {orphans.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-medium text-yellow-400 mb-3">
            Legacy graphs (no project) — delete or re-ingest under a project
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {orphans.map((g) => (
              <GraphCard key={g.id} graph={g} />
            ))}
          </div>
        </section>
      )}

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      ) : withProject.length === 0 && orphans.length === 0 ? (
        <p className="text-muted-foreground text-sm">No graphs. Create a project and ingest a repository.</p>
      ) : (
        <div className="space-y-8">
          {(projects ?? []).map((p) => {
            const pGraphs = withProject.filter((g) => g.project_id === p.id);
            if (!pGraphs.length) return null;
            return (
              <section key={p.id}>
                <h2 className="text-lg font-semibold mb-3">
                  <Link href={`/projects/${p.id}`} className="hover:text-primary">
                    {p.name}
                  </Link>
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {pGraphs.map((g) => (
                    <GraphCard key={g.id} graph={g} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
