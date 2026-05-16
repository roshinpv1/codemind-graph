"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useProjectCoverage } from "@/lib/hooks/use-projects";
import { CoverageRing } from "@/components/coverage/coverage-ring";
import { EntryPointTable } from "@/components/coverage/entry-point-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export default function ProjectCoveragePage() {
  const id = useParams().id as string;
  const { data: coverage, isLoading } = useProjectCoverage(id);

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Project Functional Coverage</h2>
        <Button variant="outline" size="sm" asChild>
          <Link href={`/projects/${id}`}>← Back to project</Link>
        </Button>
      </div>
      {coverage && (
        <>
          <CoverageRing
            pct={coverage.functional_coverage_pct}
            grade={coverage.grade}
            size={160}
          />
          <EntryPointTable rows={coverage.coverage_gap ?? []} />
        </>
      )}
    </div>
  );
}
