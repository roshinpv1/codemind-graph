"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProjectOnboardingProps {
  projectId: string;
  repositoryCount: number;
}

export function ProjectOnboarding({ projectId, repositoryCount }: ProjectOnboardingProps) {
  const qc = useQueryClient();
  const { data: briefing } = useQuery({
    queryKey: ["projects", projectId, "briefing"],
    queryFn: () => projectsApi.briefing(projectId),
  });
  const { data: dna } = useQuery({
    queryKey: ["projects", projectId, "dna"],
    queryFn: () => projectsApi.dna(projectId),
  });

  const synthesize = useMutation({
    mutationFn: () => projectsApi.synthesize(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", projectId] }),
  });
  const generateDna = useMutation({
    mutationFn: () => projectsApi.generateDna(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", projectId] }),
  });

  const hasRepos = repositoryCount > 0;
  const hasUnderstanding = Boolean(briefing?.ready);
  const hasDna = Boolean(dna?.full_summary?.trim());

  if (hasRepos && hasUnderstanding && hasDna) return null;

  const steps = [
    {
      key: "repos",
      label: "Add repositories",
      done: hasRepos,
      hint: hasRepos ? "Application repo in Test slot" : "Add your application codebase in the Test slot",
    },
    {
      key: "understanding",
      label: "Refresh understanding",
      done: hasUnderstanding,
      hint: hasUnderstanding ? "Product map and briefing ready" : "Builds areas, findings, and metrics",
    },
    {
      key: "dna",
      label: "Generate project DNA",
      done: hasDna,
      hint: hasDna ? "Full AI narrative saved" : "Optional deep narrative of the whole project",
    },
  ];

  let action: React.ReactNode = null;
  if (!hasRepos) {
    action = (
      <p className="text-sm text-muted-foreground">
        Use the <strong className="text-foreground font-medium">repository slots</strong> below to ingest
        your codebase.
      </p>
    );
  } else if (!hasUnderstanding) {
    action = (
      <Button size="sm" onClick={() => synthesize.mutate()} disabled={synthesize.isPending}>
        {synthesize.isPending ? "Refreshing…" : "Refresh understanding"}
      </Button>
    );
  } else if (!hasDna) {
    action = (
      <Button size="sm" variant="secondary" onClick={() => generateDna.mutate()} disabled={generateDna.isPending}>
        {generateDna.isPending ? "Generating…" : "Generate DNA"}
      </Button>
    );
  }

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardContent className="pt-5 pb-5 space-y-4">
        <p className="text-sm font-medium">Getting started</p>
        <ol className="grid gap-3 sm:grid-cols-3">
          {steps.map((step, i) => (
            <li key={step.key} className="flex gap-3 text-sm">
              <span
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs",
                  step.done
                    ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                    : "border-muted-foreground/40 text-muted-foreground",
                )}
              >
                {step.done ? <Check className="h-3.5 w-3.5" /> : <span>{i + 1}</span>}
              </span>
              <div className="min-w-0">
                <p className={cn("font-medium", !step.done && i === steps.findIndex((s) => !s.done) && "text-foreground")}>
                  {step.label}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">{step.hint}</p>
              </div>
            </li>
          ))}
        </ol>
        {action}
      </CardContent>
    </Card>
  );
}
