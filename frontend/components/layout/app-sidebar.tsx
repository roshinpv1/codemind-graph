"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderKanban,
  Network,
  Brain,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/graphs", label: "Graphs", icon: Network },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r border-border bg-card/50 flex flex-col shrink-0">
      <div className="p-4 border-b border-border">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
          <Brain className="h-6 w-6 text-primary" />
          CodeMind
        </Link>
        <p className="text-xs text-muted-foreground mt-1">Architecture Intelligence</p>
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
      </nav>
    </aside>
  );
}
