"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import { docsApi, ApiError } from "@/lib/api";
import { useGraph } from "@/lib/hooks/use-graphs";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";

export default function DocsPage() {
  const id = useParams().id as string;
  const queryClient = useQueryClient();
  const { data: graph } = useGraph(id);

  const generate = useMutation({
    mutationFn: () => docsApi.generate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["docs", id] });
    },
  });

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ["docs", id, "report"],
    queryFn: () => docsApi.report(id),
    enabled: graph?.status === "ready",
    retry: false,
  });

  const {
    data: wiki,
    isLoading: wikiLoading,
    isError: wikiIsError,
    error: wikiErr,
  } = useQuery({
    queryKey: ["docs", id, "wiki"],
    queryFn: () => docsApi.wiki(id),
    enabled: graph?.status === "ready" && !generate.isPending,
    retry: false,
  });

  const wikiMissing =
    wikiIsError &&
    wikiErr instanceof ApiError &&
    (wikiErr.status === 404 || wikiErr.message.includes("not generated"));

  const hasWiki = Boolean(wiki && Object.keys(wiki).length > 0);
  const needsDocs = graph?.status === "ready" && !wikiLoading && !generate.isPending && !hasWiki;

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

  if (reportLoading || wikiLoading || generate.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64" />
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          {generate.isPending
            ? "Generating wiki, call flow diagram, and dependency tree…"
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
            Indexing built the knowledge graph
            {report ? " and architecture report" : ""}. Generate wiki pages, an
            interactive call-flow diagram, and a dependency tree from that graph.
            {wikiMissing ? " (Not generated yet for this graph.)" : ""}
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
        {report && (
          <CardContent className="pt-0 border-t">
            <p className="text-xs text-muted-foreground mb-3">Architecture report (from ingest)</p>
            <div className="prose prose-invert prose-sm max-w-none max-h-96 overflow-y-auto">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          </CardContent>
        )}
      </Card>
    );
  }

  const wikiPages = wiki ? Object.entries(wiki) : [];

  return (
    <Tabs defaultValue="report">
      <div className="flex items-center justify-between gap-4 mb-2 flex-wrap">
        <TabsList>
          <TabsTrigger value="report">Architecture Report</TabsTrigger>
          <TabsTrigger value="wiki">Wiki</TabsTrigger>
          <TabsTrigger value="callflow">Call Flow</TabsTrigger>
          <TabsTrigger value="tree">Dependency Tree</TabsTrigger>
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
      <TabsContent value="report" className="prose prose-invert prose-sm max-w-none mt-4">
        <ReactMarkdown>{typeof report === "string" ? report : "No report available."}</ReactMarkdown>
      </TabsContent>
      <TabsContent value="wiki" className="mt-4 space-y-6">
        {wikiPages.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No wiki pages. Use Regenerate all to rebuild documentation.
          </p>
        ) : (
          wikiPages.map(([title, md]) => (
            <section key={title}>
              <h2 className="text-lg font-semibold mb-2">{title}</h2>
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{md}</ReactMarkdown>
              </div>
            </section>
          ))
        )}
      </TabsContent>
      <TabsContent value="callflow" className="mt-4">
        <iframe
          src={docsApi.callflowUrl(id)}
          className="w-full h-[600px] rounded-lg border bg-white"
          title="Call flow"
        />
      </TabsContent>
      <TabsContent value="tree" className="mt-4">
        <iframe
          src={docsApi.treeUrl(id)}
          className="w-full h-[600px] rounded-lg border bg-white"
          title="Dependency tree"
        />
      </TabsContent>
    </Tabs>
  );
}
