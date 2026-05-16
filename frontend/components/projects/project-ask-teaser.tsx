"use client";

import Link from "next/link";
import { MessageCircleQuestion } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const EXAMPLES = [
  "How does authentication work end to end?",
  "What are the highest-risk components?",
  "Which features lack test coverage?",
];

interface ProjectAskTeaserProps {
  projectId: string;
}

export function ProjectAskTeaser({ projectId }: ProjectAskTeaserProps) {
  const base = `/projects/${projectId}/investigate`;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <MessageCircleQuestion className="h-5 w-5 text-primary" />
          Ask about this project
        </CardTitle>
        <CardDescription>
          One place for natural-language questions across every repository in this project.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button asChild>
          <Link href={base}>Open Q&A</Link>
        </Button>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <Link
              key={q}
              href={`${base}?q=${encodeURIComponent(q)}`}
              className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground transition-colors"
            >
              {q}
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
