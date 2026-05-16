/** App route helpers — repositories (graphs) live under projects. */

export function projectPath(projectId: string, sub = "") {
  return `/projects/${projectId}${sub}`;
}

export function repositoryPath(projectId: string, graphId: string, sub = "") {
  return `/projects/${projectId}/graphs/${graphId}${sub}`;
}
