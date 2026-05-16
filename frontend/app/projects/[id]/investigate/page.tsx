"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { useProject } from "@/lib/hooks/use-projects";
import { ProjectScenarios } from "@/components/projects/project-scenarios";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sparkles } from "lucide-react";
import { AnswerCard } from "@/components/projects/answer-card";
import { projectPath } from "@/lib/routes";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectInvestigatePage() {
  const id = useParams().id as string;
  const searchParams = useSearchParams();
  const { data: project, isLoading } = useProject(id);
  const [q, setQ] = useState("");
  const [persona, setPersona] = useState("developer");
  const [prefilled, setPrefilled] = useState(false);

  const { data: personaList } = useQuery({
    queryKey: ["projects", "personas"],
    queryFn: () => projectsApi.personas(),
  });

  const ask = useMutation({
    mutationFn: ({ query, p }: { query: string; p: string }) =>
      projectsApi.ask(id, query, p),
  });

  useEffect(() => {
    const initial = searchParams.get("q");
    if (initial && !prefilled) {
      setQ(initial);
      setPrefilled(true);
    }
  }, [searchParams, prefilled]);

  const submit = (query: string, p: string) => {
    setQ(query);
    setPersona(p);
    ask.mutate({ query, p });
  };

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-8 max-w-4xl">
      <Breadcrumbs
        items={[
          { label: "Projects", href: "/projects" },
          { label: project?.name ?? "Project", href: projectPath(id) },
          { label: "Q&A" },
        ]}
      />
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ask about {project?.name ?? "this project"}</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          Natural-language answers across all repositories, with optional evidence from the code graph.
        </p>
      </div>

      <ProjectScenarios projectId={id} onSelectQuestion={submit} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Your question</CardTitle>
          <CardDescription>Pick a scenario above or type your own.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-col sm:flex-row gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) submit(q.trim(), persona);
            }}
          >
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. How does authentication work end to end?"
              className="flex-1"
            />
            <Select value={persona} onValueChange={setPersona}>
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue placeholder="Perspective" />
              </SelectTrigger>
              <SelectContent>
                {(personaList?.personas ?? []).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={ask.isPending || !q.trim()}>
              <Sparkles className="h-4 w-4 mr-1" />
              {ask.isPending ? "Thinking…" : "Ask"}
            </Button>
          </form>

          {ask.data?.answer && <AnswerCard data={ask.data} projectId={id} />}
        </CardContent>
      </Card>
    </div>
  );
}
