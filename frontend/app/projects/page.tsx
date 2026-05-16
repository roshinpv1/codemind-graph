"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects, useCreateProject, useDeleteProject } from "@/lib/hooks/use-projects";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Trash2 } from "lucide-react";

export default function ProjectsPage() {
  const router = useRouter();
  const { data: projects, isLoading } = useProjects();
  const create = useCreateProject();
  const deleteProject = useDeleteProject();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const p = await create.mutateAsync({ name, description });
    setOpen(false);
    setName("");
    setDescription("");
    router.push(`/projects/${p.id}`);
  };

  const handleDelete = async (e: React.MouseEvent, projectId: string, projectName: string, graphCount: number) => {
    e.preventDefault();
    e.stopPropagation();
    if (
      !confirm(
        `Delete project "${projectName}" and ${graphCount} graph(s)? This cannot be undone.`,
      )
    ) {
      return;
    }
    await deleteProject.mutateAsync(projectId);
  };

  return (
    <>
      <PageHeader
        title="Projects"
        description="Each project owns its graphs (source, test, CI, CD). Graphs cannot be shared across projects."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                New Project
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Project</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={create.isPending}>
                  Create
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : !projects?.length ? (
        <Card className="p-12 text-center text-muted-foreground">
          <p>Create a project, then ingest repositories into role slots (source, test, ci, cd).</p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Card key={p.id} className="hover:border-primary/50 transition-colors h-full relative group">
              <Link href={`/projects/${p.id}`} className="block">
                <CardHeader>
                  <CardTitle className="text-base pr-10">{p.name}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {p.description || "No description"}
                  <p className="mt-2">{p.graphs.length} graph{p.graphs.length !== 1 ? "s" : ""}</p>
                </CardContent>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                className="absolute top-3 right-3 h-8 w-8 text-destructive hover:text-destructive opacity-0 group-hover:opacity-100"
                onClick={(e) => handleDelete(e, p.id, p.name, p.graphs.length)}
                disabled={deleteProject.isPending}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
