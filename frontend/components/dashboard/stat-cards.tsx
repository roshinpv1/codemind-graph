"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Network, FolderKanban, Shield, Target } from "lucide-react";

interface StatCardsProps {
  graphCount: number;
  projectCount: number;
  avgCoverage: number | null;
  violationCount: number | null;
}

export function StatCards({ graphCount, projectCount, avgCoverage, violationCount }: StatCardsProps) {
  const stats = [
    { label: "Repositories", value: graphCount, icon: Network },
    { label: "Projects", value: projectCount, icon: FolderKanban },
    {
      label: "Avg Functional Coverage",
      value: avgCoverage !== null ? `${avgCoverage.toFixed(1)}%` : "—",
      icon: Target,
    },
    {
      label: "Open Violations",
      value: violationCount !== null ? violationCount : "—",
      icon: Shield,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map(({ label, value, icon: Icon }) => (
        <Card key={label}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
            <Icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
