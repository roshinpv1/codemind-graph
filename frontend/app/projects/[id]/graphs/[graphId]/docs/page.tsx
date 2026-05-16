"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import { docsApi, ApiError } from "@/lib/api";
import { useGraph } from "@/lib/hooks/use-graphs";
import { useRepositoryParams } from "@/lib/hooks/use-repository-params";
import { RepositoryDocsGuide } from "@/components/graphs/repository-docs-guide";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RichText } from "@/components/ui/rich-text";

export default function DocsPage() {
  const { graphId } = useRepositoryParams();
  const queryClient = useQueryClient();
  const { data: graph } = useGraph(graphId);

  const generate = useMutation({
    mutationFn: () => docsApi.generate(graphId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["docs", graphId] });
    },
  });

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["docs", graphId, "overview"],
    queryFn: () => docsApi.overview(graphId),
    enabled: graph?.status === "ready",
  });

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ["docs", graphId, "report"],
    queryFn: () => docsApi.report(graphId),
    enabled: graph?.status === "ready",
    retry: false,
  });

  const {
    data: wiki,
    isLoading: wikiLoading,
    isError: wikiIsError,
    error: wikiErr,
  } = useQuery({
    queryKey: ["docs", graphId, "wiki"],
    queryFn: () => docsApi.wiki(graphId),
    enabled: graph?.status === "ready" && !generate.isPending,
    retry: false,
  });

  const wikiMissing =
    wikiIsError &&
    wikiErr instanceof ApiError &&
    (wikiErr.status === 404 || wikiErr.message.includes("not generated"));

  const hasWiki = Boolean(wiki && Object.keys(wiki).length > 0);
  const needsDocs =
    graph?.status === "ready" &&
    !overviewLoading &&
    !wikiLoading &&
    !generate.isPending &&
    !hasWiki &&
    !overview?.artifacts?.wiki;

  if (graph && graph.status !== "ready") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Documentation</CardTitle>
          <CardDescription>
            Available after indexing finishes. Current status:{" "}
            <span className="font-medium text-foreground">{graph.status}</span>.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (overviewLoading || wikiLoading || generate.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64" />
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          {generate.isPending
            ? "Generating guides, flow diagram, and technical reference…"
            : "Loading documentation…"}
        </p>
      </div>
    );
  }

  if (needsDocs) {
    return (
      <Card className="border-dashed max-w-lg">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Generate documentation
          </CardTitle>
          <CardDescription>
            Indexing analyzed this repository. Generate area guides, interactive flow views, and a
            technical audit trail for engineers.
            {wikiMissing ? " (Guides not generated yet.)" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            Generate documentation
          </Button>
        </CardContent>
        {generate.isError && (
          <CardContent className="pt-0">
            <p className="text-sm text-destructive">
              Generation failed. Check API logs and try again.
            </p>
          </CardContent>
        )}
        {overview?.ready && (
          <CardContent className="pt-0 border-t">
            <RepositoryDocsGuide graphId={graphId} data={overview} />
          </CardContent>
        )}
      </Card>
    );
  }

  const wikiPages = wiki ? Object.entries(wiki).filter(([t]) => t !== "index") : [];

  return (
    <Tabs defaultValue="overview">
      <div className="flex items-center justify-between gap-4 mb-2 flex-wrap">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="flows">Flows & structure</TabsTrigger>
          <TabsTrigger value="technical">Technical reference</TabsTrigger>
        </TabsList>
        <Button
          variant="outline"
          size="sm"
          disabled={generate.isPending}
          onClick={() => generate.mutate()}
        >
          Regenerate all
        </Button>
      </div>
      {generate.isError && (
        <p className="text-sm text-destructive mb-2">
          Regeneration failed. Try again or check API logs.
        </p>
      )}

      <TabsContent value="overview" className="mt-4">
        {overview?.ready ? (
          <RepositoryDocsGuide graphId={graphId} data={overview} />
        ) : (
          <p className="text-sm text-muted-foreground">{overview?.message ?? "Overview unavailable."}</p>
        )}
      </TabsContent>

      <TabsContent value="flows" className="mt-4 space-y-6">
        <p className="text-sm text-muted-foreground">
          Interactive diagrams for exploring how code connects. Best for engineers and tech leads.
        </p>
        <section>
          <h2 className="text-sm font-semibold mb-2">Call flow</h2>
          {overview?.artifacts?.callflow ? (
            <iframe
              src={docsApi.callflowUrl(graphId)}
              className="w-full h-[560px] rounded-lg border bg-white"
              title="Call flow"
            />
          ) : (
            <p className="text-sm text-muted-foreground">Generate documentation to build the call flow.</p>
          )}
        </section>
        <section>
          <h2 className="text-sm font-semibold mb-2">Dependency tree</h2>
          {overview?.artifacts?.tree ? (
            <iframe
              src={docsApi.treeUrl(graphId)}
              className="w-full h-[560px] rounded-lg border bg-white"
              title="Dependency tree"
            />
          ) : (
            <p className="text-sm text-muted-foreground">Generate documentation to build the tree.</p>
          )}
        </section>
      </TabsContent>

      <TabsContent value="technical" className="mt-4 space-y-6">
        <Card className="border-yellow-500/30 bg-yellow-500/5">
          <CardContent className="pt-4 text-sm text-muted-foreground">
            Technical reference is for engineers and auditors. It uses graph terminology (nodes,
            edges, EXTRACTED/INFERRED confidence) and is not intended for general product or
            business readers.
          </CardContent>
        </Card>

        <Tabs defaultValue="report">
          <TabsList>
            <TabsTrigger value="report">Graph report</TabsTrigger>
            <TabsTrigger value="wiki">Raw wiki</TabsTrigger>
          </TabsList>
          <TabsContent value="report" className="mt-4">
            {reportLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <RichText
                content={typeof report === "string" ? report : ""}
                mode="markdown"
                variant="document"
                className="max-w-none"
                emptyMessage="No report available."
              />
            )}
          </TabsContent>
          <TabsContent value="wiki" className="mt-4 space-y-6">
            {wikiPages.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No wiki pages. Use Regenerate all to rebuild.
              </p>
            ) : (
              wikiPages.map(([title, md]) => (
                <section key={title}>
                  <h2 className="text-lg font-semibold mb-2">{title}</h2>
                  <RichText content={md} mode="markdown" variant="panel" className="max-w-none" />
                </section>
              ))
            )}
          </TabsContent>
        </Tabs>
      </TabsContent>
    </Tabs>
  );
}
