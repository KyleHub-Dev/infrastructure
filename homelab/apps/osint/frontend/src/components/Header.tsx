export function Header() {
  return (
    <header className="flex items-center justify-between px-5 h-12 border-b border-border bg-card/95 shrink-0">
      <h1 className="font-display font-bold text-sm tracking-wide text-foreground">
        OSINT Platform
      </h1>
      <div className="flex items-center gap-4">
        {(["Neo4j", "Redis", "Tor"] as const).map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            <span className="text-xs text-muted-foreground">{s}</span>
          </div>
        ))}
      </div>
    </header>
  );
}
