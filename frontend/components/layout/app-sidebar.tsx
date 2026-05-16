"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FolderKanban, Brain, Search } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
];

function contextFromPath(pathname: string): string | null {
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/);
  if (!projectMatch) return null;
  const rest = pathname.slice(projectMatch[0].length);
  if (rest.startsWith("/graphs/")) return "Repository view";
  if (rest.startsWith("/investigate")) return "Project Q&A";
  if (rest === "" || rest === "/") return "Project home";
  return "Project";
}

export function AppSidebar() {
  const pathname = usePathname();
  const context = contextFromPath(pathname);

  return (
    <aside className="w-56 border-r border-border bg-card/50 flex flex-col shrink-0">
      <div className="p-4 border-b border-border">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
          <Brain className="h-6 w-6 text-primary" />
          CodeMind
        </Link>
        <p className="text-xs text-muted-foreground mt-1">Architecture intelligence</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              pathname === href || (href !== "/" && pathname.startsWith(href))
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
        {context && (
          <p className="px-3 pt-3 text-[11px] uppercase tracking-wide text-muted-foreground/80">
            {context}
          </p>
        )}
      </nav>
      <div className="p-3 border-t border-border space-y-2">
        <p className="flex items-center gap-2 px-2 text-xs text-muted-foreground">
          <Search className="h-3.5 w-3.5" />
          <kbd className="rounded border border-border bg-muted/50 px-1.5 py-0.5 font-mono text-[10px]">
            ⌘K
          </kbd>
          <span>quick jump</span>
        </p>
      </div>
    </aside>
  );
}
