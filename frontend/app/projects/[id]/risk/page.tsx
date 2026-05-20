"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ProjectRiskPage() {
  const { id } = useParams<{ id: string }>();
  const [paths, setPaths] = useState("");

  const mutation = useMutation({
    mutationFn: () => {
      const files = paths
        .split("\n")
        .map((p) => p.trim())
        .filter(Boolean);
      return projectsApi.blastRadius(id, files);
    },
  });

  const result = mutation.data as {
    ready?: boolean;
    message?: string;
    hubs?: { label?: string; degree?: number; repository?: string }[];
    dependents?: { label?: string; source_file?: string; repository?: string }[];
    hub_findings?: { title?: string; why_it_matters?: string }[];
  } | undefined;

  return (
    <div className="max-w-3xl mx-auto space-y-6 p-4">
      <div>
        <Link href={`/projects/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to project
        </Link>
        <h1 className="text-2xl font-semibold mt-2">PR blast radius</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Paste changed file paths (one per line) to see structural dependents and hub overlap.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Changed files</CardTitle>
          <CardDescription>Paths relative to repo root, e.g. src/api/handlers.py</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            value={paths}
            onChange={(e) => setPaths(e.target.value)}
            placeholder={"src/main.py\napi/core/auth.py"}
            rows={6}
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
          />
          <Button
            onClick={() => mutation.mutate()}
            disabled={!paths.trim() || mutation.isPending}
          >
            {mutation.isPending ? "Analyzing…" : "Analyze blast radius"}
          </Button>
          {mutation.isError && (
            <p className="text-sm text-destructive">
              {mutation.error instanceof ApiError
                ? mutation.error.message
                : "Analysis failed."}
            </p>
          )}
        </CardContent>
      </Card>

      {result && !result.ready && (
        <p className="text-sm text-amber-400/90">{result.message}</p>
      )}

      {result?.ready && (
        <>
          {result.hub_findings && result.hub_findings.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Known hub findings</CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                {result.hub_findings.map((f, i) => (
                  <p key={i}>
                    <span className="font-medium">{f.title}</span>
                    {f.why_it_matters && (
                      <span className="text-muted-foreground"> — {f.why_it_matters}</span>
                    )}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}

          {result.hubs && result.hubs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Structural hubs</CardTitle>
              </CardHeader>
              <CardContent className="text-sm font-mono space-y-1">
                {result.hubs.slice(0, 10).map((h, i) => (
                  <p key={i}>
                    {h.label} (degree {h.degree}) [{h.repository}]
                  </p>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Likely dependents</CardTitle>
              <CardDescription>Downstream from matched seeds (BFS depth 2)</CardDescription>
            </CardHeader>
            <CardContent className="text-sm max-h-80 overflow-auto space-y-2 font-mono">
              {(result.dependents ?? []).length === 0 ? (
                <p className="text-muted-foreground font-sans">No dependents matched — try full paths.</p>
              ) : (
                result.dependents!.slice(0, 40).map((d, i) => (
                  <p key={i} className="truncate">
                    {d.label} — {d.source_file} [{d.repository}]
                  </p>
                ))
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
