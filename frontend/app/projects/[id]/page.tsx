"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  useProject,
  useProjectSummary,
  useProjectCoverage,
  useDeleteProject,
  useDeleteProjectGraph,
} from "@/lib/hooks/use-projects";
import { PageHeader } from "@/components/layout/page-header";
import { IngestDialog } from "@/components/graphs/ingest-dialog";
import { CoverageRing } from "@/components/coverage/coverage-ring";
import { EntryPointTable } from "@/components/coverage/entry-point-table";
import { StatusBadge, RoleBadge } from "@/components/graphs/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { GraphRole } from "@/lib/types";
import { Trash2 } from "lucide-react";
import { repositoryPath } from "@/lib/routes";
import { ProjectDna } from "@/components/projects/project-dna";
import { ProductMap } from "@/components/projects/product-map";
import { ProjectBriefing } from "@/components/projects/project-briefing";
<<<<<<< Updated upstream
import { ProjectAskPanel } from "@/components/projects/project-ask-panel";

const ROLES: GraphRole[] = ["source", "test", "ci", "cd"];
=======
import { ProjectOnboarding } from "@/components/projects/project-onboarding";
import { ProjectSubnav } from "@/components/projects/project-subnav";
import { ProjectSection } from "@/components/projects/project-section";
import { ProjectAskTeaser } from "@/components/projects/project-ask-teaser";
import { ProjectDecisions } from "@/components/projects/project-decisions";
>>>>>>> Stashed changes

export default function ProjectDetailPage() {
  const id = useParams().id as string;
  const router = useRouter();
  const { data: project, isLoading } = useProject(id);
  const { data: summary } = useProjectSummary(id);
  const { data: coverage } = useProjectCoverage(id);
  const deleteProject = useDeleteProject();
  const deleteGraph = useDeleteProjectGraph(id);

  if (isLoading) return <Skeleton className="h-64" />;

  if (!project) return <p className="text-red-400">Project not found.</p>;

  const graphsByRole: Record<string, typeof project.graphs> = {};
  for (const role of ROLES) {
    graphsByRole[role] = project.graphs.filter((g) => g.graph_role === role);
  }

  const handleDeleteProject = async () => {
    if (
      !confirm(
        `Delete project "${project.name}" and all ${project.graphs.length} repository index(es)? This cannot be undone.`,
      )
    ) {
      return;
    }
    await deleteProject.mutateAsync(id);
    router.push("/projects");
  };

  const handleDeleteGraph = async (graphId: string, graphName: string) => {
    if (!confirm(`Delete repository index "${graphName}"?`)) return;
    await deleteGraph.mutateAsync(graphId);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title={project.name}
        description={project.description || undefined}
        actions={
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDeleteProject}
            disabled={deleteProject.isPending}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete project
          </Button>
        }
      />

<<<<<<< Updated upstream
      <ProjectDna projectId={id} projectName={project.name} />
=======
      <ProjectOnboarding
        projectId={id}
        repositoryCount={
          project.graphs.some((g) => g.graph_role === "ci" || g.graph_role === "source")
            ? 1
            : project.graphs.some((g) => g.graph_role === "test")
              ? 1
              : 0
        }
      />
      <ProjectSubnav projectId={id} />
>>>>>>> Stashed changes

      <ProductMap projectId={id} />

      <ProjectBriefing projectId={id} />

      <div className="flex justify-end">
        <Button variant="outline" size="sm" asChild>
          <Link href={`/projects/${id}/investigate`}>Open investigate →</Link>
        </Button>
      </div>

      <ProjectAskPanel projectId={id} projectName={project.name} />

      {summary && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Role completeness</p>
          <div className="h-2 bg-muted rounded-full mt-2 overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${summary.completeness_pct}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {summary.present_roles.join(", ") || "none"}
            {summary.missing_roles.length > 0 &&
              ` · missing: ${summary.missing_roles.join(", ")}`}
          </p>
          {summary.recommendations.length > 0 && (
            <ul className="mt-3 text-sm text-yellow-400/90 list-disc pl-4">
              {summary.recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <section>
        <h2 className="text-lg font-semibold mb-4">Repository slots</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Ingest one repository per role. Graphs stay in this project only — they cannot be shared
          across projects.
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {ROLES.map((role) => {
            const assigned = graphsByRole[role]?.[0];
            return (
              <Card key={role}>
                <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-sm capitalize flex items-center gap-2">
                    <RoleBadge role={role} />
                    {role}
                  </CardTitle>
                  {assigned && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => handleDeleteGraph(assigned.id, assigned.name)}
                      disabled={deleteGraph.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </CardHeader>
                <CardContent className="text-sm space-y-3">
                  {assigned ? (
                    <>
                      <Link
                        href={repositoryPath(id, assigned.id)}
                        className="hover:text-primary block"
                      >
                        <p className="font-medium truncate">{assigned.name}</p>
                        <StatusBadge status={assigned.status} />
                      </Link>
                    </>
                  ) : (
                    <IngestDialog
                      projectId={id}
                      defaultRole={role}
                      lockRole
                      trigger={
                        <Button variant="outline" size="sm" className="w-full">
                          Ingest {role}
                        </Button>
                      }
                    />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
<<<<<<< Updated upstream
      </section>
=======
      </ProjectSection>

      <ProjectSection
        id="understanding"
        title="Understanding"
        description="Structural snapshot from your repositories — briefing, product map, and findings."
      >
        <ProjectBriefing projectId={id} />
        <ProductMap projectId={id} />
      </ProjectSection>

      <ProjectSection
        id="decisions"
        title="Decisions"
        description="WHY / DECISION / TRADEOFF markers extracted from application code."
      >
        <ProjectDecisions projectId={id} />
      </ProjectSection>

      <ProjectSection
        id="dna"
        title="Project DNA"
        description="Optional AI-written narrative of the whole product (separate from the structural map)."
      >
        <ProjectDna projectId={id} projectName={project.name} />
      </ProjectSection>

      <ProjectSection id="ask" title="Questions">
        <ProjectAskTeaser projectId={id} />
      </ProjectSection>
>>>>>>> Stashed changes

      {coverage && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Functional Coverage</h2>
          {coverage.warning && (
            <p className="text-sm text-yellow-400">{coverage.warning}</p>
          )}
          <div className="flex flex-col sm:flex-row gap-8 items-start">
            <CoverageRing
              pct={coverage.functional_coverage_pct}
              grade={coverage.grade}
              label="Entry points covered"
            />
            <div className="text-sm space-y-1">
              <p>
                <span className="text-muted-foreground">Covered:</span>{" "}
                {coverage.entry_points_covered} / {coverage.entry_points_total}
              </p>
              <p>
                <span className="text-muted-foreground">Gaps:</span>{" "}
                {coverage.entry_points_uncovered}
              </p>
            </div>
          </div>
          <EntryPointTable rows={coverage.coverage_gap ?? []} />
        </section>
      )}
    </div>
  );
}
