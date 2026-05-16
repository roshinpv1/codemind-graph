"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import type { ProjectAskResult } from "@/lib/types";
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
import { AnswerCard } from "@/components/projects/answer-card";
import { repositoryPath } from "@/lib/routes";

const EXAMPLE_QUESTIONS = [
  "How does authentication work end to end?",
  "What are the highest-risk hub components?",
  "Which user-facing features lack test coverage?",
  "Give me an onboarding tour of the main modules.",
];

interface ProjectAskPanelProps {
  projectId: string;
  projectName?: string;
  showTitle?: boolean;
  onScenarioSelect?: (q: string, persona: string) => void;
}

function StructuredExtras({ data }: { data: ProjectAskResult }) {
  const s = data.structured as Record<string, unknown> | undefined;
  if (!s) return null;

  if (data.persona === "executive" && Array.isArray(s.top_risks)) {
    return (
      <ul className="text-xs text-muted-foreground list-disc pl-4">
        {(s.top_risks as string[]).map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    );
  }
  if (data.persona === "onboarding" && Array.isArray(s.start_here)) {
    return (
      <p className="text-xs text-muted-foreground">
        Start here: {(s.start_here as string[]).join(" → ")}
      </p>
    );
  }
  if (data.persona === "qa" && Array.isArray(s.untested_capabilities)) {
    const gaps = s.untested_capabilities as { label: string; source_file?: string }[];
    return (
      <ul className="text-xs space-y-1">
        {gaps.slice(0, 5).map((g) => (
          <li key={g.label} className="text-yellow-400/90">
            {g.label} <span className="text-muted-foreground">{g.source_file}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (Array.isArray(s.where_to_look)) {
    const items = s.where_to_look as { file?: string; label?: string }[];
    return (
      <ul className="text-xs font-mono text-muted-foreground space-y-0.5">
        {items.map((w, i) => (
          <li key={i}>{w.file ?? w.label}</li>
        ))}
      </ul>
    );
  }
  return null;
}

export function ProjectAskPanel({
  projectId,
  projectName = "this project",
  showTitle = true,
}: ProjectAskPanelProps) {
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

  const runAsk = (query: string, p?: string) => {
    setMode("ask");
    setQ(query);
    const usePersona = p ?? persona;
    if (p) setPersona(p);
    ask.mutate(query);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;
    if (mode === "ask") ask.mutate(query);
    else search.mutate(query);
  };

  const inner = (
    <div className="space-y-4">
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
          <Button type="submit" disabled={active.isPending} onClick={() => setMode("ask")}>
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
            Search structure only
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2">
        {EXAMPLE_QUESTIONS.map((ex) => (
          <button
            key={ex}
            type="button"
            className="text-xs rounded-full border border-border px-2 py-1 text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
            onClick={() => runAsk(ex)}
          >
            {ex}
          </button>
        ))}
      </div>

      {mode === "ask" && ask.data?.answer && (
        <>
          <AnswerCard data={ask.data} projectId={projectId} />
          <StructuredExtras data={ask.data} />
        </>
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
                  <Link
                    href={repositoryPath(projectId, node.graph_id)}
                    className="text-primary hover:underline"
                  >
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
          Request failed. Ensure repositories are indexed, refresh understanding, and set LLM keys in .env.
        </p>
      )}
    </div>
  );

  if (!showTitle) {
    return inner;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Ask about this project
        </CardTitle>
        <CardDescription>
          Ask anything about <span className="font-medium text-foreground">{projectName}</span>.
          Answers use your product map plus targeted code structure when needed.
        </CardDescription>
      </CardHeader>
      <CardContent>{inner}</CardContent>
    </Card>
  );
}
