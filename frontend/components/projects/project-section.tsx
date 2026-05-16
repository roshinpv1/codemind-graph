import { cn } from "@/lib/utils";

interface ProjectSectionProps {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function ProjectSection({ id, title, description, children, className }: ProjectSectionProps) {
  return (
    <section id={id} className={cn("scroll-mt-20 space-y-4", className)}>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description && <p className="text-sm text-muted-foreground max-w-2xl">{description}</p>}
      </div>
      {children}
    </section>
  );
}
