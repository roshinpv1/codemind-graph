"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import type { AssignGraphRequest, ProjectCreate } from "@/lib/types";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["projects", id],
    queryFn: () => projectsApi.get(id),
    enabled: !!id,
  });
}

export function useProjectSummary(id: string) {
  return useQuery({
    queryKey: ["projects", id, "summary"],
    queryFn: () => projectsApi.summary(id),
    enabled: !!id,
  });
}

export function useProjectCoverage(id: string) {
  return useQuery({
    queryKey: ["projects", id, "coverage"],
    queryFn: () => projectsApi.coverage(id),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectCreate) => projectsApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useAssignGraph(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignGraphRequest) =>
      projectsApi.assignGraph(projectId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", projectId] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["graphs"] });
    },
  });
}

export function useDeleteProjectGraph(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (graphId: string) => projectsApi.deleteGraph(projectId, graphId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", projectId] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["graphs"] });
    },
  });
}
