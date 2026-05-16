"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useGraph } from "@/lib/hooks/use-graphs";
import { GraphTabs } from "@/components/graphs/graph-tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { projectPath } from "@/lib/routes";

export default function RepositoryLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const projectId = params.id as string;
  const graphId = params.graphId as string;
  const { data: graph, isLoading, error } = useGraph(graphId);

  if (isLoading) return <Skeleton className="h-24 mb-6" />;

  if (error || !graph) {
    return (
      <p className="text-red-400">
        Repository not found.{" "}
        <Link href={projectPath(projectId)} className="text-primary hover:underline">
          Back to project
        </Link>
      </p>
    );
  }

  if (graph.project_id && graph.project_id !== projectId) {
    return (
      <p className="text-red-400">
        This repository belongs to another project.{" "}
        <Link href={projectPath(graph.project_id)} className="text-primary hover:underline">
          Open correct project
        </Link>
      </p>
    );
  }

  return (
    <div>
      <GraphTabs graph={graph} projectId={projectId} />
      {children}
    </div>
  );
}
