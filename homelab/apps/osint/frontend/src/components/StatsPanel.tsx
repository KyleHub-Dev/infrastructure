import type { InvestigationStats } from "../lib/api";
import { entityColors } from "../lib/constants";
import { Panel, Heading } from "./Panel";

interface StatsPanelProps {
  stats: InvestigationStats | null;
  activeCount: number;
  totalInvestigations: number;
  selectedInv: string | null;
}

export function StatsPanel({ stats, activeCount, totalInvestigations, selectedInv }: StatsPanelProps) {
  const totalEntities = stats
    ? Object.values(stats.by_type).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="p-3 border-l border-border/50 overflow-y-auto flex flex-col gap-3">
      <Panel>
        <Heading>Overview</Heading>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Nodes", value: stats ? stats.node_count.toLocaleString() : "—", cls: "text-primary" },
            { label: "Edges", value: stats ? stats.edge_count.toLocaleString() : "—", cls: "text-primary" },
            { label: "Active", value: String(activeCount), cls: "text-success" },
            { label: "Total", value: String(totalInvestigations), cls: "text-primary" },
          ].map((m) => (
            <div key={m.label}>
              <div className="text-[10px] uppercase text-muted-foreground mb-1">{m.label}</div>
              <div className={`font-mono font-bold text-2xl ${m.cls}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel>
        <Heading>Entities</Heading>
        {stats && totalEntities > 0 ? (
          <div className="flex flex-col gap-2">
            {Object.entries(stats.by_type)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type}>
                  <div className="flex justify-between mb-0.5">
                    <span
                      className="text-[10px] uppercase font-medium"
                      style={{ color: entityColors[type] ?? "hsl(220 15% 55%)" }}
                    >
                      {type}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {count.toLocaleString()} ({((count / totalEntities) * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-1 bg-secondary/60 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(count / totalEntities) * 100}%`,
                        background: entityColors[type] ?? "hsl(220 15% 55%)",
                        opacity: 0.7,
                      }}
                    />
                  </div>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {selectedInv ? "No entity data yet" : "Select an investigation"}
          </p>
        )}
      </Panel>

      {stats && Object.keys(stats.by_tool).length > 0 && (
        <Panel>
          <Heading>Tools</Heading>
          <div className="flex flex-col gap-2">
            {Object.entries(stats.by_tool)
              .sort(([, a], [, b]) => b - a)
              .map(([tool, count]) => (
                <div key={tool} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{tool}</span>
                  <span className="font-mono font-bold text-foreground">{count.toLocaleString()}</span>
                </div>
              ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
