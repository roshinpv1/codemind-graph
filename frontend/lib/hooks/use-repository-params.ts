"use client";

import { useParams } from "next/navigation";

/** Route: /projects/[id]/graphs/[graphId]/… */
export function useRepositoryParams() {
  const params = useParams();
  return {
    projectId: params.id as string,
    graphId: params.graphId as string,
  };
}
