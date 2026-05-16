"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
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
import { Sparkles, Search } from "lucide-react";
import Link from "next/link";

const EXAMPLE_QUESTIONS = [
  "How does authentication work end to end?",
  "What are the highest-risk hub components?",
  "Which user-facing features lack test coverage?",
  "Give me an onboarding tour of the main modules.",
];

interface ProjectAskPanelProps {
  projectId: string;
  projectName: string;
}

export function ProjectAskPanel({ projectId, projectName }: ProjectAskPanelProps) {
  const [q, setQ] = useState("");
  const [persona, setPersona] = useState("developer");
  const [mode, setMode] = useState<"ask" | "search">("ask");

  const { data: personaList } = useQuery({
    queryKey: ["projects", "personas"],
    queryFn: () => projectsApi.personas(),
  });

  const ask = useMutation({
    mutationFn: (query: string) => projectsApi.ask(projectId, query, persona),
  });

  const search = useMutation({
    mutationFn: (query: string) => projectsApi.search(projectId, query),
  });

  const active = mode === "ask" ? ask : search;
  const result = active.data;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;
    if (mode === "ask") ask.mutate(query);
    else search.mutate(query);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Project AI search
        </CardTitle>
        <CardDescription>
          Ask anything about <span className="font-medium text-foreground">{projectName}</span>{" "}
          across all ingested repos (source, tests, CI/CD). Answers use the knowledge graph, not
          raw file grep.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              placeholder="e.g. Where is payment processing handled?"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="flex-1"
            />
            <Select value={persona} onValueChange={setPersona} disabled={mode === "search"}>
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue placeholder="Persona" />
              </SelectTrigger>
              <SelectContent>
                {(personaList?.personas ?? []).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              disabled={active.isPending}
              onClick={() => setMode("ask")}
            >
              {active.isPending && mode === "ask" ? "Thinking…" : "Ask AI"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={active.isPending}
              onClick={() => {
                setMode("search");
                if (q.trim()) search.mutate(q.trim());
              }}
            >
              <Search className="h-4 w-4 mr-1" />
              Graph search only
            </Button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((ex) => (
            <button
              key={ex}
              type="button"
              className="text-xs rounded-full border border-border px-2 py-1 text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
              onClick={() => {
                setQ(ex);
                setMode("ask");
                ask.mutate(ex);
              }}
            >
              {ex}
            </button>
          ))}
        </div>

        {mode === "ask" && ask.data?.answer && (
          <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              {ask.data.persona_label} · {ask.data.context_nodes} nodes from{" "}
              {ask.data.graphs_used ?? ask.data.sources?.length ?? 0} graph(s)
            </p>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{ask.data.answer}</p>
            {ask.data.sources && ask.data.sources.length > 0 && (
              <div className="pt-2 border-t border-border/50">
                <p className="text-xs font-medium text-muted-foreground mb-2">Context from</p>
                <ul className="text-xs space-y-1">
                  {ask.data.sources.map((s) => (
                    <li key={s.graph_id}>
                      <Link
                        href={`/graphs/${s.graph_id}`}
                        className="text-primary hover:underline"
                      >
                        {s.graph_name}
                      </Link>{" "}
                      <span className="text-muted-foreground">({s.graph_role})</span>
                      {s.start_labels?.length > 0 && (
                        <span className="text-muted-foreground">
                          {" "}
                          — {s.start_labels.slice(0, 3).join(", ")}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {mode === "search" && search.data && (
          <div className="space-y-2">
            {search.data.message && (
              <p className="text-sm text-muted-foreground">{search.data.message}</p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {(search.data.nodes ?? []).map((node) => (
                <div
                  key={`${node.graph_id}-${node.id}`}
                  className="rounded-md border p-3 text-sm space-y-1"
                >
                  <p className="font-mono font-medium truncate">{node.label}</p>
                  <p className="text-xs text-muted-foreground truncate">{node.source_file}</p>
                  <p className="text-xs">
                    <Link href={`/graphs/${node.graph_id}`} className="text-primary hover:underline">
                      {node.graph_name}
                    </Link>{" "}
                    · {node.graph_role} · score {node.score}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {active.isError && (
          <p className="text-sm text-destructive">
            Request failed. Ensure graphs are ready and LLM keys are set in .env for AI answers.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
