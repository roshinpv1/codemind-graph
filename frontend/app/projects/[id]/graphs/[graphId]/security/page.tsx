"use client";

import { useQuery } from "@tanstack/react-query";
import { securityApi, complianceApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { RichText } from "@/components/ui/rich-text";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";

export default function SecurityPage() {
  const { graphId } = useRepositoryParams();
  const { data: authFlows, isLoading } = useQuery({
    queryKey: ["security", graphId, "auth"],
    queryFn: () => securityApi.authFlows(graphId),
    enabled: !!graphId,
  });
  const { data: secrets } = useQuery({
    queryKey: ["security", graphId, "secrets"],
    queryFn: () => securityApi.secretExposure(graphId),
    enabled: !!graphId,
  });
  const { data: pii } = useQuery({
    queryKey: ["compliance", graphId, "pii"],
    queryFn: () => complianceApi.piiFlows(graphId),
    enabled: !!graphId,
  });
  const { data: report } = useQuery({
    queryKey: ["security", graphId, "report"],
    queryFn: () => securityApi.report(graphId, true),
    enabled: !!graphId,
  });

  if (isLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-base">Auth Flows</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-2 max-h-64 overflow-auto">
            {(authFlows ?? []).slice(0, 10).map((f, i) => (
              <div key={i} className="border-b pb-2 font-mono text-xs">
                {String((f as Record<string, unknown>).auth_label)}
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Secret Exposure</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-2 max-h-64 overflow-auto">
            {(secrets ?? []).slice(0, 10).map((s, i) => (
              <div key={i} className="flex justify-between border-b pb-2">
                <span className="font-mono text-xs">{String((s as Record<string, unknown>).secret_label)}</span>
                <Badge variant="destructive">{String((s as Record<string, unknown>).exposure_count ?? 0)}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">PII Flows</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-2 max-h-64 overflow-auto">
            {(pii ?? []).slice(0, 10).map((p, i) => (
              <div key={i} className="border-b pb-2 font-mono text-xs">
                {String((p as Record<string, unknown>).pii_label)}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      {report && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Risk Report</CardTitle>
            <Badge>{String((report as Record<string, unknown>).risk_level ?? "unknown")}</Badge>
          </CardHeader>
          <CardContent>
            <RichText
              content={String((report as Record<string, unknown>).narrative ?? "")}
              mode="auto"
              variant="panel"
              className="max-w-none"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
