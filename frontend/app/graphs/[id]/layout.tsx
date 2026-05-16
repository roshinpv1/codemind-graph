"use client";

import { useGraph } from "@/lib/hooks/use-graphs";
import { GraphTabs } from "@/components/graphs/graph-tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useParams } from "next/navigation";

export default function GraphLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const id = params.id as string;
  const { data: graph, isLoading, error } = useGraph(id);

  if (isLoading) return <Skeleton className="h-24 mb-6" />;
  if (error || !graph) {
    return <p className="text-red-400">Graph not found.</p>;
  }

  return (
    <div>
      <GraphTabs graph={graph} />
      {children}
    </div>
  );
}
