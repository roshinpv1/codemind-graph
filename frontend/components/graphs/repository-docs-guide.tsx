"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import type { DocsOverview } from "@/lib/api";
import { docsApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RichText } from "@/components/ui/rich-text";

interface RepositoryDocsGuideProps {
  graphId: string;
  data: DocsOverview;
}

export function RepositoryDocsGuide({ graphId, data }: RepositoryDocsGuideProps) {
  const qc = useQueryClient();
  const genSummary = useMutation({
    mutationFn: () => docsApi.generatePlainSummary(graphId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docs", graphId, "overview"] });
    },
  });

  const highlights = data.report_highlights;

  return (
    <div className="space-y-6">
      {data.audience_note && (
        <p className="text-sm text-muted-foreground border-l-2 border-primary/40 pl-3">
          {data.audience_note}
        </p>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">At a glance</CardTitle>
          <CardDescription>Plain-language summary of this repository</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.plain_summary ? (
            <RichText content={data.plain_summary} mode="auto" variant="panel" className="max-w-none" />
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                Generate a short executive summary in everyday language (requires LLM in .env).
              </p>
              <Button
                size="sm"
                onClick={() => genSummary.mutate()}
                disabled={genSummary.isPending}
              >
                <Sparkles className="h-4 w-4 mr-1" />
                {genSummary.isPending ? "Generating…" : "Generate summary"}
              </Button>
            </>
          )}
          {highlights?.stats_line && (
            <p className="text-xs text-muted-foreground">{highlights.stats_line}</p>
          )}
        </CardContent>
      </Card>

      {highlights?.key_components && highlights.key_components.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-2">Most connected parts</h3>
          <ul className="text-sm space-y-1">
            {highlights.key_components.slice(0, 8).map((c) => (
              <li key={c.name} className="flex justify-between gap-2 border-b border-border/50 py-1">
                <span className="font-medium">{c.name}</span>
                <span className="text-muted-foreground shrink-0">{c.connection_count} links</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.product_areas && data.product_areas.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-3">Product areas</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.product_areas.map((a) => (
              <Card key={a.id}>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm">{a.centerpiece ?? a.name}</CardTitle>
                  <CardDescription>{a.component_count} components</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
      )}

      {data.wiki_guides && data.wiki_guides.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-3">Area guides</h3>
          <div className="space-y-3">
            {data.wiki_guides.map((g) => (
              <Card key={g.id}>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm">{g.title}</CardTitle>
                  {g.summary && <CardDescription>{g.summary}</CardDescription>}
                </CardHeader>
                {g.key_items && g.key_items.length > 0 && (
                  <CardContent className="pt-0">
                    <ul className="text-sm list-disc pl-4 text-muted-foreground space-y-0.5">
                      {g.key_items.slice(0, 6).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </section>
      )}

      {highlights?.suggested_questions && highlights.suggested_questions.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-2">Good questions to ask</h3>
          <ul className="text-sm space-y-1">
            {highlights.suggested_questions.map((q) => (
              <li key={q} className="text-muted-foreground">
                · {q}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.suggested_actions && data.suggested_actions.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold mb-2">Next steps</h3>
          <ul className="text-sm list-disc pl-4 text-muted-foreground space-y-1">
            {data.suggested_actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}

      {data.artifacts && (
        <div className="flex flex-wrap gap-2">
          {data.artifacts.callflow && <Badge variant="outline">Call flow ready</Badge>}
          {data.artifacts.tree && <Badge variant="outline">Dependency tree ready</Badge>}
          {data.artifacts.report && <Badge variant="outline">Technical report</Badge>}
        </div>
      )}
    </div>
  );
}
