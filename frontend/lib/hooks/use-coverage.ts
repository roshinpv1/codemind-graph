"use client";

import { useQuery } from "@tanstack/react-query";
import { coverageApi } from "@/lib/api";

export function useCoverageSummary(graphId: string, enabled = true) {
  return useQuery({
    queryKey: ["coverage", graphId, "summary"],
    queryFn: () => coverageApi.summary(graphId),
    enabled: !!graphId && enabled,
  });
}

export function useFunctionalCoverage(
  graphId: string,
  mode: "all" | "covered" | "uncovered" = "all",
  enabled = true,
) {
  return useQuery({
    queryKey: ["coverage", graphId, "functional", mode],
    queryFn: () => coverageApi.functional(graphId, mode),
    enabled: !!graphId && enabled,
  });
}

export function useCoverageFiles(graphId: string, mode = "functional") {
  return useQuery({
    queryKey: ["coverage", graphId, "files", mode],
    queryFn: () => coverageApi.files(graphId, mode),
    enabled: !!graphId,
  });
}

export function useCoverageCritical(graphId: string) {
  return useQuery({
    queryKey: ["coverage", graphId, "critical"],
    queryFn: () => coverageApi.critical(graphId),
    enabled: !!graphId,
  });
}
