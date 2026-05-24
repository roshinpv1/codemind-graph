import { Badge } from "@/components/ui/badge";
import type { GraphStatus } from "@/lib/types";
import { roleLabel } from "@/lib/role-labels";
import { cn } from "@/lib/utils";

const styles: Record<GraphStatus, string> = {
  pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  running: "bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse",
  ready: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
};

export function StatusBadge({ status }: { status: GraphStatus }) {
  return (
    <Badge variant="outline" className={cn("capitalize", styles[status])}>
      {status}
    </Badge>
  );
}

export function RoleBadge({ role }: { role: string }) {
  const normalized = role === "ci" ? "source" : role;
  const colors: Record<string, string> = {
    source: "bg-violet-500/20 text-violet-300",
    test: "bg-cyan-500/20 text-cyan-300",
    cd: "bg-pink-500/20 text-pink-300",
  };
  return (
    <Badge variant="outline" className={cn("text-xs", colors[normalized] ?? "")}>
      {roleLabel(role)}
    </Badge>
  );
}
