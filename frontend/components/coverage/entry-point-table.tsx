"use client";

import { Badge } from "@/components/ui/badge";
import type { EntryPoint } from "@/lib/types";
import { riskBadgeClass, cn } from "@/lib/utils";

export function EntryPointTable({ rows }: { rows: EntryPoint[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground py-8 text-center">No entry points found.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3 font-medium">Entry point</th>
            <th className="text-left p-3 font-medium">File</th>
            <th className="text-left p-3 font-medium">Type</th>
            <th className="text-left p-3 font-medium">Risk</th>
            <th className="text-left p-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((ep) => (
            <tr key={ep.id} className="border-t border-border hover:bg-muted/30">
              <td className="p-3 font-mono text-xs">{ep.label}</td>
              <td className="p-3 text-muted-foreground text-xs">{ep.source_file}</td>
              <td className="p-3 text-xs">{ep.entry_type}</td>
              <td className="p-3">
                {ep.risk && (
                  <span className={cn("text-xs px-2 py-0.5 rounded border", riskBadgeClass(ep.risk))}>
                    {ep.risk}
                  </span>
                )}
              </td>
              <td className="p-3">
                <Badge variant={ep.covered ? "success" : "destructive"}>
                  {ep.covered ? "Covered" : "Gap"}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
