"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useIngestGraph } from "@/lib/hooks/use-graphs";
import { useProjects } from "@/lib/hooks/use-projects";
import type { GraphRole } from "@/lib/types";
import { Plus } from "lucide-react";

interface IngestDialogProps {
  trigger?: React.ReactNode;
  /** When set, graph is ingested into this project only (required for project-scoped ingest). */
  projectId?: string;
  defaultRole?: GraphRole;
  /** Hide role picker when ingesting into a fixed slot */
  lockRole?: boolean;
}

export function IngestDialog({
  trigger,
  projectId: fixedProjectId,
  defaultRole = "ci",
  lockRole = false,
}: IngestDialogProps) {
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<GraphRole>(defaultRole);
  const [projectId, setProjectId] = useState(fixedProjectId ?? "");
  const [backend, setBackend] = useState("openai");
  const [useSemantic, setUseSemantic] = useState(true);

  const ingest = useIngestGraph();
  const { data: projects } = useProjects();

  useEffect(() => {
    if (fixedProjectId) setProjectId(fixedProjectId);
  }, [fixedProjectId]);

  useEffect(() => {
    setRole(defaultRole);
  }, [defaultRole, open]);

  const effectiveProjectId = fixedProjectId ?? projectId;
  const canSubmit = Boolean(effectiveProjectId && path && name);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectiveProjectId) return;
    await ingest.mutateAsync({
      path,
      name,
      graph_role: role,
      project_id: effectiveProjectId,
      backend,
      use_semantic: useSemantic,
    });
    setOpen(false);
    setPath("");
    setName("");
  };

  const noProjects = !fixedProjectId && (!projects || projects.length === 0);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button disabled={noProjects}>
            <Plus className="h-4 w-4 mr-2" />
            Ingest Repository
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ingest into project</DialogTitle>
          <DialogDescription>
<<<<<<< Updated upstream
            Each repository belongs to one project. Slots: Application (CI role), Test, and CD.
=======
            Every graph must belong to a project. One graph per role (source, test, cd).
>>>>>>> Stashed changes
          </DialogDescription>
        </DialogHeader>
        {noProjects ? (
          <p className="text-sm text-muted-foreground">
            Create a project first, then ingest repositories from the project page.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {!fixedProjectId && (
              <div className="space-y-2">
                <Label>Project *</Label>
                <Select value={projectId} onValueChange={setProjectId} required>
                  <SelectTrigger>
                    <SelectValue placeholder="Select project" />
                  </SelectTrigger>
                  <SelectContent>
                    {(projects ?? []).map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="path">Filesystem path *</Label>
              <Input
                id="path"
                placeholder="/path/to/repo"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                placeholder="my-service"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              {!lockRole && (
                <div className="space-y-2">
                  <Label>Role *</Label>
                  <Select value={role} onValueChange={(v) => setRole(v as GraphRole)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
<<<<<<< Updated upstream
                      <SelectItem value="ci">Application</SelectItem>
=======
                      <SelectItem value="source">Source (application)</SelectItem>
>>>>>>> Stashed changes
                      <SelectItem value="test">Test</SelectItem>
                      <SelectItem value="cd">CD</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              {lockRole && (
                <div className="space-y-2">
                  <Label>Role</Label>
                  <p className="text-sm capitalize pt-2">{role}</p>
                </div>
              )}
              <div className="space-y-2">
                <Label className={!useSemantic ? "text-muted-foreground" : ""}>Backend</Label>
                <Select value={backend} onValueChange={setBackend} disabled={!useSemantic}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="ollama">Ollama</SelectItem>
                    <SelectItem value="claude">Claude</SelectItem>
                    <SelectItem value="gemini">Gemini</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={useSemantic}
                onChange={(e) => setUseSemantic(e.target.checked)}
                className="mt-0.5 rounded border-input"
              />
              <span>
                LLM semantic extraction
                <span className="text-muted-foreground block text-xs">
                  Uncheck for code-only (no API key).
                </span>
              </span>
            </label>
            <Button type="submit" className="w-full" disabled={ingest.isPending || !canSubmit}>
              {ingest.isPending ? "Starting…" : "Start Ingestion"}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

