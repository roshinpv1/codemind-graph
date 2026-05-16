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
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
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
import { ProjectOnboarding } from "@/components/projects/project-onboarding";
import { ProjectSubnav } from "@/components/projects/project-subnav";
import { ProjectSection } from "@/components/projects/project-section";
import { ProjectAskTeaser } from "@/components/projects/project-ask-teaser";

/** Application + supporting repos — Test holds primary codebase; CI/CD are optional. */
const SLOT_ROLES: { role: GraphRole; label: string; hint: string }[] = [
  { role: "test", label: "Application & tests", hint: "Main codebase (required)" },
  { role: "ci", label: "CI", hint: "Pipelines, GitHub Actions, Jenkins" },
  { role: "cd", label: "CD", hint: "Deploy, infra, Helm, Terraform" },
];

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
  const legacySource = project.graphs.filter((g) => g.graph_role === "source");
  for (const { role } of SLOT_ROLES) {
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
    if (!confirm(`Remove repository index "${graphName}"?`)) return;
    await deleteGraph.mutateAsync(graphId);
  };

  return (
    <div className="space-y-10">
      <Breadcrumbs
        items={[
          { label: "Projects", href: "/projects" },
          { label: project.name },
        ]}
      />
      <PageHeader
        title={project.name}
        description={project.description || "Code intelligence for this product"}
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
        className="mb-0"
      />

      <ProjectOnboarding
        projectId={id}
        repositoryCount={
          project.graphs.filter((g) => g.graph_role === "test" || g.graph_role === "source").length
        }
      />
      <ProjectSubnav />

      <ProjectSection
        id="repositories"
        title="Repositories"
        description="Test, CI, and CD are your repository slots. Put application code in Test; CI and CD are optional."
      >
        {legacySource.length > 0 && (
          <Card className="p-4 border-amber-500/30 bg-amber-500/5">
            <p className="text-sm">
              <span className="font-medium text-amber-400/90">Legacy source repo: </span>
              {legacySource.map((g) => (
                <Link
                  key={g.id}
                  href={repositoryPath(id, g.id)}
                  className="text-primary hover:underline ml-1"
                >
                  {g.name}
                </Link>
              ))}
              <span className="text-muted-foreground"> — still used for analysis until you re-ingest under Test.</span>
            </p>
          </Card>
        )}
        {summary && (
          <Card className="p-4 border-dashed">
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
              <ul className="mt-3 text-sm text-amber-400/90 list-disc pl-4">
                {summary.recommendations.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </Card>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SLOT_ROLES.map(({ role, label, hint }) => {
            const assigned = graphsByRole[role]?.[0];
            const required = role === "test";
            return (
              <Card key={role}>
                <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-sm flex items-center gap-2 flex-wrap">
                    <RoleBadge role={role} />
                    {label}
                    {required && (
                      <span className="text-[10px] uppercase tracking-wide text-primary">Required</span>
                    )}
                  </CardTitle>
                  {assigned && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      title="Remove repository index"
                      onClick={() => handleDeleteGraph(assigned.id, assigned.name)}
                      disabled={deleteGraph.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </CardHeader>
                <CardContent className="text-sm space-y-3">
                  <p className="text-xs text-muted-foreground">{hint}</p>
                  {assigned ? (
                    <Link
                      href={repositoryPath(id, assigned.id)}
                      className="hover:text-primary block rounded-md -m-1 p-1"
                    >
                      <p className="font-medium truncate">{assigned.name}</p>
                      <StatusBadge status={assigned.status} />
                      {assigned.status === "ready" && (
                        <p className="text-xs text-muted-foreground mt-2">Open analysis →</p>
                      )}
                    </Link>
                  ) : (
                    <IngestDialog
                      projectId={id}
                      defaultRole={role}
                      lockRole
                      trigger={
                        <Button variant="outline" size="sm" className="w-full">
                          Add {label}
                        </Button>
                      }
                    />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
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
        id="dna"
        title="Project DNA"
        description="Optional AI-written narrative of the whole product (separate from the structural map)."
      >
        <ProjectDna projectId={id} projectName={project.name} />
      </ProjectSection>

      <ProjectSection id="ask" title="Questions">
        <ProjectAskTeaser projectId={id} />
      </ProjectSection>

      {coverage && (
        <ProjectSection
          id="coverage"
          title="Test coverage"
          description="Functional entry-point coverage rolled up across repositories in this project."
        >
          {coverage.warning && (
            <p className="text-sm text-amber-400/90">{coverage.warning}</p>
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
        </ProjectSection>
      )}
    </div>
  );
}
