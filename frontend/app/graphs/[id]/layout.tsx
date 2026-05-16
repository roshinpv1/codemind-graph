"use client";

import { useEffect } from "react";
import { useParams, useRouter, usePathname } from "next/navigation";
import { useGraph } from "@/lib/hooks/use-graphs";
import { repositoryPath } from "@/lib/routes";
import { Skeleton } from "@/components/ui/skeleton";

/** Legacy /graphs/:id/* URLs → /projects/:projectId/graphs/:id/* */
export default function LegacyGraphRedirectLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams();
  const graphId = id as string;
  const pathname = usePathname();
  const router = useRouter();
  const { data: graph, isLoading } = useGraph(graphId);

  useEffect(() => {
    if (!graph?.project_id) return;
    const suffix = pathname.replace(`/graphs/${graphId}`, "") || "";
    router.replace(repositoryPath(graph.project_id, graphId, suffix));
  }, [graph, graphId, pathname, router]);

  if (isLoading) return <Skeleton className="h-24" />;
  if (!graph?.project_id) {
    return (
      <p className="text-muted-foreground text-sm">
        This repository is not linked to a project. Open it from{" "}
        <a href="/projects" className="text-primary hover:underline">
          Projects
        </a>
        .
      </p>
    );
  }

  return <Skeleton className="h-64" />;
}
