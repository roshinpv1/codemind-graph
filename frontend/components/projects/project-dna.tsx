"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { RichText } from "@/components/ui/rich-text";
import { Dna, Sparkles } from "lucide-react";

interface ProjectDnaProps {
  projectId: string;
  projectName?: string;
}

const healthColor: Record<string, string> = {
  green: "text-emerald-400",
  yellow: "text-yellow-400",
  red: "text-red-400",
  unknown: "text-muted-foreground",
};

export function ProjectDna({ projectId, projectName }: ProjectDnaProps) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["projects", projectId, "dna"],
    queryFn: () => projectsApi.dna(projectId),
  });

  const generate = useMutation({
    mutationFn: () => projectsApi.generateDna(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", projectId] });
    },
  });

  if (isLoading) return <Skeleton className="h-48" />;

  const healthKey = String(data?.health_key ?? "unknown");
  const hasFull = Boolean(data?.full_summary?.trim());

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-lg flex items-center gap-2">
            <Dna className="h-5 w-5 text-primary" />
            Code Project DNA
          </CardTitle>
          <CardDescription className="mt-1 max-w-2xl">
            Complete AI-written summary of {projectName ?? "this project"} — what it is, how it is
            organized, risks, and where to focus. Generated separately from the structural product map.
          </CardDescription>
        </div>
        <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
          <Sparkles className={`h-4 w-4 mr-1 ${generate.isPending ? "animate-pulse" : ""}`} />
          {generate.isPending ? "Generating…" : hasFull ? "Regenerate DNA" : "Generate DNA"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasFull ? (
          <div className="text-sm text-muted-foreground space-y-2">
            <p>{data?.message ?? "Generate DNA after repositories are indexed and understanding is refreshed."}</p>
            <p className="text-xs">
              Step 1: ingest repositories · Step 2: <strong>Refresh understanding</strong> · Step 3:{" "}
              <strong>Generate DNA</strong>
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 items-center">
              {data?.health_label && (
                <Badge variant="outline" className={healthColor[healthKey]}>
                  {data.health_label}
                </Badge>
              )}
              {data?.coverage_grade && (
                <Badge variant="outline">Coverage grade {data.coverage_grade}</Badge>
              )}
              {data?.generated_at && (
                <span className="text-xs text-muted-foreground">
                  Generated {new Date(data.generated_at).toLocaleString()}
                </span>
              )}
            </div>
            <RichText
              content={data?.full_summary}
              mode="markdown"
              variant="document"
              className="max-w-none"
            />
          </>
        )}
        {generate.isError && (
          <p className="text-sm text-destructive">
            DNA generation failed. Refresh understanding first, then check LLM settings in .env.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
