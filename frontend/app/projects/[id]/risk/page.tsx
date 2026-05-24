"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { useProject } from "@/lib/hooks/use-projects";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function ProjectRiskPage() {
  const id = useParams().id as string;
  const { data: project } = useProject(id);
  const [pathsText, setPathsText] = useState("");

  const blast = useMutation({
    mutationFn: (paths: string[]) => projectsApi.blastRadius(id, paths),
  });

  const handleAnalyze = () => {
    const paths = pathsText
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean);
    if (paths.length) blast.mutate(paths);
  };

  const result = blast.data as Record<string, unknown> | undefined;
  const impacted = (result?.impacted ?? []) as Record<string, unknown>[];
  const hubs = (result?.hub_findings ?? []) as Record<string, unknown>[];

  return (
    <div className="space-y-8 max-w-4xl">
      <Breadcrumbs
        items={[
          { label: "Projects", href: "/projects" },
          { label: project?.name ?? "Project", href: `/projects/${id}` },
          { label: "PR risk" },
        ]}
      />
      <PageHeader
        title="Change impact (blast radius)"
        description="Paste changed file paths from your PR — no git integration required."
        className="mb-0"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Changed files</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={pathsText}
            onChange={(e) => setPathsText(e.target.value)}
            placeholder={"src/api/handlers.py\nfrontend/lib/auth.ts"}
            rows={6}
            className="font-mono text-sm"
          />
          <Button onClick={handleAnalyze} disabled={blast.isPending || !pathsText.trim()}>
            {blast.isPending ? "Analyzing…" : "Analyze blast radius"}
          </Button>
          {blast.isError && (
            <p className="text-sm text-destructive">{(blast.error as Error).message}</p>
          )}
        </CardContent>
      </Card>

      {result && (
        <>
          <p className="text-sm text-muted-foreground">
            Matched {String(result.seeds_matched ?? 0)} seed nodes ·{" "}
            {String(result.impacted_count ?? impacted.length)} impacted components
          </p>
          {hubs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Hub warnings</CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                {hubs.map((h, i) => (
                  <p key={i}>
                    <span className="font-medium">{String(h.title)}</span>
                    {" — "}
                    {String(h.why_it_matters)}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Impacted components</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-1 font-mono max-h-96 overflow-y-auto">
                {impacted.map((row, i) => (
                  <li key={i} className="flex justify-between gap-4 border-b border-border/40 py-1">
                    <span>{String(row.label)}</span>
                    <span className="text-muted-foreground shrink-0">
                      {String(row.direction)} · deg {String(row.degree)}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </>
      )}

      <Link href={`/projects/${id}`} className="text-sm text-primary hover:underline">
        ← Back to project
      </Link>
    </div>
  );
}
