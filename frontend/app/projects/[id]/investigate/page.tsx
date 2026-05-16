"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { ProjectScenarios } from "@/components/projects/project-scenarios";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Sparkles } from "lucide-react";
import { AnswerCard } from "@/components/projects/answer-card";

export default function ProjectInvestigatePage() {
  const id = useParams().id as string;
  const [q, setQ] = useState("");
  const [persona, setPersona] = useState("developer");

  const { data: personaList } = useQuery({
    queryKey: ["projects", "personas"],
    queryFn: () => projectsApi.personas(),
  });

  const ask = useMutation({
    mutationFn: ({ query, p }: { query: string; p: string }) =>
      projectsApi.ask(id, query, p),
  });

  const submit = (query: string, p: string) => {
    setQ(query);
    setPersona(p);
    ask.mutate({ query, p });
  };

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${id}`}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Project
          </Link>
        </Button>
        <div>
          <h1 className="text-xl font-semibold">Investigate</h1>
          <p className="text-sm text-muted-foreground">
            Ask questions with structured answers and optional technical proof
          </p>
        </div>
      </div>

      <ProjectScenarios projectId={id} onSelectQuestion={submit} />

      <Card>
        <CardContent className="pt-6 space-y-4">
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
              placeholder="Your question…"
              className="flex-1"
            />
            <Select value={persona} onValueChange={setPersona}>
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue />
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
