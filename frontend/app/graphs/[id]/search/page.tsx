"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { searchApi, graphsApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { QueryNode } from "@/lib/types";

export default function SearchPage() {
  const id = useParams().id as string;
  const [q, setQ] = useState("");
  const [explaining, setExplaining] = useState<string | null>(null);
  const [explanation, setExplanation] = useState("");

  const search = useMutation({
    mutationFn: (query: string) => searchApi.search(id, query),
  });

  const handleExplain = async (nodeId: string) => {
    setExplaining(nodeId);
    try {
      const res = await graphsApi.explainNode(id, nodeId);
      setExplanation(String((res as Record<string, unknown>).explanation ?? JSON.stringify(res)));
    } finally {
      setExplaining(null);
    }
  };

  return (
    <div className="space-y-6">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) search.mutate(q.trim());
        }}
      >
        <Input
          placeholder="Search: authentication, payment handler, database…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={search.isPending}>
          {search.isPending ? "Searching…" : "Search"}
        </Button>
      </form>

      {search.data?.message && (
        <p className="text-sm text-muted-foreground">{search.data.message}</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {(search.data?.nodes ?? []).map((node) => (
          <Card key={node.id}>
            <CardContent className="pt-4 space-y-2">
              <p className="font-mono text-sm font-medium">{node.label ?? node.id}</p>
              <p className="text-xs text-muted-foreground">{node.source_file}</p>
              {node.degree !== undefined && <p className="text-xs">Degree: {node.degree}</p>}
              <Button
                size="sm"
                variant="outline"
                disabled={explaining === node.id}
                onClick={() => handleExplain(node.id)}
              >
                {explaining === node.id ? "…" : "Explain"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {explanation && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{explanation}</p>
        </Card>
      )}
    </div>
  );
}
