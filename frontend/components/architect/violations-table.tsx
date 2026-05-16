import type { Violation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

export function ViolationsTable({
  violations,
  emptyMessage = "No violations detected.",
}: {
  violations: Violation[];
  emptyMessage?: string;
}) {
  if (!violations.length) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3">Severity</th>
            <th className="text-left p-3">Rule</th>
            <th className="text-left p-3">Source → Target</th>
            <th className="text-left p-3">Message</th>
          </tr>
        </thead>
        <tbody>
          {violations.map((v, i) => (
            <tr key={i} className="border-t border-border">
              <td className="p-3">
                <Badge variant={v.severity === "error" ? "destructive" : "warning"}>
                  {v.severity}
                </Badge>
              </td>
              <td className="p-3 font-mono text-xs">{v.rule}</td>
              <td className="p-3 text-xs">
                {v.source_label} → {v.target_label}
              </td>
              <td className="p-3 text-muted-foreground text-xs">{v.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
