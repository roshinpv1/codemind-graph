import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function gradeFromPct(pct: number): string {
  if (pct >= 80) return "A";
  if (pct >= 60) return "B";
  if (pct >= 40) return "C";
  if (pct >= 20) return "D";
  return "F";
}

export function gradeColor(grade: string): string {
  switch (grade) {
    case "A":
      return "text-emerald-400";
    case "B":
      return "text-green-400";
    case "C":
      return "text-yellow-400";
    case "D":
      return "text-orange-400";
    default:
      return "text-red-400";
  }
}

export function formatPct(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) return "—";
  return `${n.toFixed(1)}%`;
}

export function riskBadgeClass(risk: string): string {
  switch (risk) {
    case "critical":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    case "high":
      return "bg-orange-500/20 text-orange-400 border-orange-500/30";
    case "medium":
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    default:
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  }
}

export function truncate(s: string, max = 48): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
