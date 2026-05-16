"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import type { ProductArea, ProductCapability, ProductFinding, ProductMapData } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Map, AlertTriangle, Layers, Route } from "lucide-react";
import { RichText } from "@/components/ui/rich-text";

interface ProductMapProps {
  projectId: string;
}

const healthStyles: Record<string, string> = {
  green: "border-emerald-500/40 text-emerald-400",
  yellow: "border-yellow-500/40 text-yellow-400",
  red: "border-red-500/40 text-red-400",
  unknown: "text-muted-foreground",
};

function AreaCard({ area }: { area: ProductArea }) {
  return (
    <div className="rounded-md border p-3 space-y-1">
      <p className="font-medium text-sm">{area.name}</p>
      {area.centerpiece && (
        <p className="text-xs text-muted-foreground">Center: {area.centerpiece}</p>
      )}
      <p className="text-xs text-muted-foreground">
        {area.component_count} components
        {area.repository ? ` · ${area.repository}` : ""}
      </p>
      {area.summary && (
        <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{area.summary}</p>
      )}
    </div>
  );
}

function CapabilityRow({ cap }: { cap: ProductCapability }) {
  const untested = cap.test_status_key === "untested";
  return (
    <li className="flex items-start justify-between gap-2 text-sm py-1.5 border-b border-border/40 last:border-0">
      <div className="min-w-0">
        <p className="font-medium truncate">{cap.name}</p>
        {cap.source_file && (
          <p className="text-xs font-mono text-muted-foreground truncate">{cap.source_file}</p>
        )}
      </div>
      <Badge variant="outline" className={untested ? "text-yellow-400 shrink-0" : "text-emerald-400 shrink-0"}>
        {cap.test_status}
      </Badge>
    </li>
  );
}

function FindingRow({ f }: { f: ProductFinding }) {
  return (
    <li className="rounded-md border p-2 text-sm space-y-0.5">
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs uppercase text-muted-foreground">{f.severity_label ?? f.severity}</span>
        {f.category && (
          <Badge variant="secondary" className="text-xs">
            {f.category}
          </Badge>
        )}
      </div>
      <p className="font-medium">{f.title}</p>
      {f.why_it_matters && (
        <p className="text-xs text-muted-foreground">{f.why_it_matters}</p>
      )}
    </li>
  );
}

export function ProductMap({ projectId }: ProductMapProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["projects", projectId, "map"],
    queryFn: () => projectsApi.map(projectId),
    refetchInterval: (q) => (q.state.data?.ready ? false : 15_000),
  });

  if (isLoading) return <Skeleton className="h-64" />;

  const map = data as ProductMapData | undefined;
  if (!map?.ready) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Map className="h-4 w-4" />
            Product map
          </CardTitle>
          <CardDescription>
            {map?.message ??
              "After repositories finish indexing, refresh understanding to see areas, capabilities, and findings."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const healthKey = String(map.health?.status_key ?? "unknown");
  const healthLabel = String(map.health?.status_label ?? "Unknown");

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-lg">{map.headline ?? "Product map"}</CardTitle>
              {map.summary && (
                <div className="mt-2 max-w-3xl">
                  <RichText content={map.summary} mode="auto" variant="inline" className="max-w-none" />
                </div>
              )}
            </div>
            <Badge variant="outline" className={healthStyles[healthKey]}>
              {healthLabel}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
            <span>{map.health?.product_areas ?? map.areas?.length ?? 0} product areas</span>
            <span>·</span>
            <span>
              {map.health?.capabilities_tested_pct ?? 0}% capabilities tested
            </span>
            <span>·</span>
            <span>{map.health?.open_findings ?? map.findings?.length ?? 0} open findings</span>
            <span>·</span>
            <span>{map.repositories?.length ?? 0} repositories</span>
          </div>
        </CardContent>
      </Card>

      {map.areas && map.areas.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <Layers className="h-4 w-4" />
            Product areas
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {map.areas.map((a) => (
              <AreaCard key={a.id} area={a} />
            ))}
          </div>
        </section>
      )}

      {map.capabilities && map.capabilities.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold mb-3">Capabilities</h2>
          <Card>
            <CardContent className="pt-4">
              <ul>
                {map.capabilities.slice(0, 12).map((c) => (
                  <CapabilityRow key={c.id} cap={c} />
                ))}
              </ul>
              {map.capabilities.length > 12 && (
                <p className="text-xs text-muted-foreground mt-2">
                  +{map.capabilities.length - 12} more in full map
                </p>
              )}
            </CardContent>
          </Card>
        </section>
      )}

      {map.findings && map.findings.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            Open findings
          </h2>
          <ul className="space-y-2">
            {map.findings.slice(0, 6).map((f) => (
              <FindingRow key={f.id} f={f} />
            ))}
          </ul>
        </section>
      )}

      {map.journeys && map.journeys.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <Route className="h-4 w-4" />
            User journeys
          </h2>
          <ul className="text-sm space-y-2 text-muted-foreground">
            {map.journeys.map((j) => (
              <li key={j.name} className="rounded-md border px-3 py-2">
                <span className="font-medium text-foreground">{j.name}</span>
                <span className={j.test_status === "Tested" ? " text-emerald-500" : " text-yellow-500"}>
                  {" "}
                  · {j.test_status}
                </span>
                {j.summary && <p className="text-xs mt-0.5">{j.summary}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {map.understanding_updated_at && (
        <p className="text-xs text-muted-foreground">
          Understanding updated {new Date(map.understanding_updated_at).toLocaleString()}
          {" · "}
          <Link href={`/projects/${projectId}/investigate`} className="text-primary hover:underline">
            Open Q&A
          </Link>
        </p>
      )}
    </div>
  );
}
