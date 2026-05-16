"use client";

import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface ProjectScenariosProps {
  projectId: string;
  onSelectQuestion?: (q: string, persona: string) => void;
}

export function ProjectScenarios({ projectId, onSelectQuestion }: ProjectScenariosProps) {
  const { data } = useQuery({
    queryKey: ["projects", projectId, "scenarios"],
    queryFn: () => projectsApi.scenarios(projectId),
  });

  const scenarios = data?.scenarios ?? {};
  if (Object.keys(scenarios).length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Scenario packs</CardTitle>
        <CardDescription>Pre-built questions for common workflows</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {Object.entries(scenarios).map(([key, pack]) => (
          <div key={key} className="space-y-2">
            <p className="text-sm font-medium">{pack.title}</p>
            <div className="flex flex-col gap-1 items-start">
              {pack.questions.map((q) => (
                <Button
                  key={q}
                  variant="ghost"
                  size="sm"
                  className="h-auto py-1 px-2 text-left text-xs font-normal justify-start whitespace-normal"
                  onClick={() => onSelectQuestion?.(q, pack.persona)}
                >
                  {q}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
