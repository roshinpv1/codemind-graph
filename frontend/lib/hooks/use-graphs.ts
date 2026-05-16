"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { graphsApi } from "@/lib/api";
import type { GraphMeta, IngestRequest } from "@/lib/types";

export function useGraphs(projectId?: string) {
  return useQuery({
    queryKey: ["graphs", projectId ?? "all"],
    queryFn: () => graphsApi.list(projectId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const hasActive = data.some(
        (g) => g.status === "pending" || g.status === "running",
      );
      return hasActive ? 2000 : false;
    },
  });
}

export function useGraph(id: string) {
  return useQuery({
    queryKey: ["graphs", id],
    queryFn: () => graphsApi.get(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "pending" || status === "running") return 2000;
      return false;
    },
  });
}

export function useGraphStats(id: string, enabled = true) {
  return useQuery({
    queryKey: ["graphs", id, "stats"],
    queryFn: () => graphsApi.stats(id),
    enabled: !!id && enabled,
  });
}

export function useIngestGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: IngestRequest) => graphsApi.ingest(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["graphs"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteGraph(projectId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => graphsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["graphs"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      if (projectId) {
        qc.invalidateQueries({ queryKey: ["projects", projectId] });
      }
    },
  });
}

export function recentGraphs(graphs: GraphMeta[] | undefined, n = 5) {
  if (!graphs) return [];
  return [...graphs]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, n);
}
