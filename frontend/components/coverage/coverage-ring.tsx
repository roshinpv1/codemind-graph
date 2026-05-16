import { gradeColor, cn } from "@/lib/utils";

interface CoverageRingProps {
  pct: number;
  grade: string;
  label?: string;
  size?: number;
}

export function CoverageRing({ pct, grade, label, size = 120 }: CoverageRingProps) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(var(--muted))" strokeWidth={8} />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth={8}
            strokeDasharray={circ}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-2xl font-bold", gradeColor(grade))}>{grade}</span>
          <span className="text-xs text-muted-foreground">{pct.toFixed(1)}%</span>
        </div>
      </div>
      {label && <span className="text-xs text-muted-foreground text-center">{label}</span>}
    </div>
  );
}
