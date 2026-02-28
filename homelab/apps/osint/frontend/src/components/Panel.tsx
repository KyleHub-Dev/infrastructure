import type React from "react";

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-card rounded-lg border border-border p-4 ${className ?? ""}`}>
      {children}
    </div>
  );
}

export function Heading({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground font-display whitespace-nowrap">
        {children}
      </h3>
      <span className="flex-1 h-px bg-gradient-to-r from-border to-transparent" />
    </div>
  );
}
