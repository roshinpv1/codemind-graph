"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useGraphs } from "@/lib/hooks/use-graphs";
import { Search } from "lucide-react";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { data: graphs } = useGraphs();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50" onClick={() => setOpen(false)}>
      <div
        className="fixed left-1/2 top-[20%] w-full max-w-lg -translate-x-1/2 rounded-lg border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="p-2">
          <div className="flex items-center border-b px-3 pb-2">
            <Search className="mr-2 h-4 w-4 text-muted-foreground" />
            <Command.Input
              placeholder="Search graphs, jump to coverage…"
              className="flex-1 bg-transparent outline-none text-sm"
            />
          </div>
          <Command.List className="max-h-72 overflow-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results.
            </Command.Empty>
            <Command.Group heading="Graphs">
              {(graphs ?? []).map((g) => (
                <Command.Item
                  key={g.id}
                  value={g.name}
                  onSelect={() => {
                    router.push(`/graphs/${g.id}`);
                    setOpen(false);
                  }}
                  className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-accent"
                >
                  {g.name}
                  <span className="ml-2 text-xs text-muted-foreground">{g.graph_role}</span>
                </Command.Item>
              ))}
            </Command.Group>
            <Command.Group heading="Actions">
              <Command.Item
                onSelect={() => {
                  router.push("/graphs");
                  setOpen(false);
                }}
                className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-accent"
              >
                View all graphs
              </Command.Item>
              <Command.Item
                onSelect={() => {
                  router.push("/projects");
                  setOpen(false);
                }}
                className="cursor-pointer rounded px-2 py-1.5 text-sm aria-selected:bg-accent"
              >
                View projects
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
