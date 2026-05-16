"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { RichText } from "@/components/ui/rich-text";
import type { ProjectAskResult } from "@/lib/types";
import { repositoryPath } from "@/lib/routes";

interface AnswerCardProps {
  data: ProjectAskResult;
  projectId?: string;
}

export function AnswerCard({ data, projectId }: AnswerCardProps) {
  const [showProof, setShowProof] = useState(false);
  const card = data.answer_card as {
    summary?: string;
    confidence_label?: string;
    related?: { name: string; type?: string; test_status?: string; file?: string }[];
    gaps?: string[];
    suggested_next_steps?: string[];
  } | undefined;

  const summary = card?.summary ?? data.answer;
  const proof = data.technical_proof as {
    repositories?: { name: string; role: string }[];
    components?: { label?: string; file?: string; repository?: string }[];
  } | undefined;

  return (
    <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
      <div>
        <p className="text-xs text-muted-foreground mb-1">
          {data.persona_label}
          {card?.confidence_label ? ` · ${card.confidence_label}` : ""}
        </p>
        <RichText content={summary} mode="auto" variant="inline" className="max-w-none" />
      </div>

      {card?.related && card.related.length > 0 && (
        <section>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Related
          </h4>
          <ul className="text-sm space-y-1">
            {card.related.map((r) => (
              <li key={r.name}>
                <span className="font-medium">{r.name}</span>
                {r.test_status && (
                  <span className="text-muted-foreground"> · {r.test_status}</span>
                )}
                {r.file && (
                  <span className="text-muted-foreground text-xs block font-mono truncate">
                    {r.file}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {card?.gaps && card.gaps.length > 0 && (
        <section>
          <h4 className="text-xs font-semibold text-yellow-500/90 uppercase tracking-wide mb-2">
            Gaps
          </h4>
          <ul className="text-sm list-disc pl-4 text-yellow-400/80">
            {card.gaps.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </section>
      )}

      {card?.suggested_next_steps && card.suggested_next_steps.length > 0 && (
        <section>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Suggested next steps
          </h4>
          <ul className="text-sm list-disc pl-4 text-muted-foreground">
            {card.suggested_next_steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-border/50">
        <Button variant="outline" size="sm" onClick={() => setShowProof((v) => !v)}>
          {showProof ? "Hide technical proof" : "Show technical proof"}
        </Button>
      </div>

      {showProof && proof && (
        <div className="text-xs font-mono text-muted-foreground space-y-2 bg-background/50 p-3 rounded">
          {proof.repositories && proof.repositories.length > 0 && (
            <p>Repositories: {proof.repositories.map((r) => `${r.name} (${r.role})`).join(", ")}</p>
          )}
          {proof.components?.map((c, i) => (
            <p key={i}>
              {c.label} — {c.file}
              {c.repository ? ` [${c.repository}]` : ""}
            </p>
          ))}
          {data.sources?.map((s) => (
            <p key={s.graph_id}>
              <Link
                href={
                  projectId
                    ? repositoryPath(projectId, s.graph_id)
                    : `/graphs/${s.graph_id}`
                }
                className="text-primary hover:underline"
              >
                Open repository: {s.graph_name}
              </Link>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
