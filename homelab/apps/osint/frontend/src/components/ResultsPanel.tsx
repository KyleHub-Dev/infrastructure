import { useState, useMemo } from "react";
import type { Observable } from "../lib/api";
import { entityColors, inputClass, selectClass } from "../lib/constants";
import { Panel, Heading } from "./Panel";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type SortField = "value" | "confidence" | "tool_source" | "platform";
type SortDir = "asc" | "desc";

interface ResultsPanelProps {
  observables: Observable[];
  resultsLoading: boolean;
  selectedInv: string | null;
  selectedStatus: string | undefined;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const DEFAULT_COLOR = "#7a7a8e";

function platform(obs: Observable): string {
  return (obs.metadata?.platform as string) ?? "";
}

function confidenceColor(c: number): string {
  if (c >= 0.8) return "hsl(152 69% 45%)";
  if (c >= 0.5) return "hsl(38 92% 50%)";
  return "hsl(0 84% 60%)";
}

/* ------------------------------------------------------------------ */
/*  Group header                                                       */
/* ------------------------------------------------------------------ */

function GroupHeader({
  type,
  count,
  collapsed,
  onToggle,
}: {
  type: string;
  count: number;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      className="w-full flex items-center gap-2 px-3 py-2 bg-secondary/40 border border-border/30 rounded-md text-xs hover:bg-secondary/60 transition-colors"
      onClick={onToggle}
    >
      <span
        className="w-2.5 h-2.5 rounded-full shrink-0"
        style={{ backgroundColor: entityColors[type] ?? DEFAULT_COLOR }}
      />
      <span className="font-medium text-foreground">{type}</span>
      <span className="text-muted-foreground">({count})</span>
      <span className="ml-auto text-muted-foreground">{collapsed ? "+" : "\u2212"}</span>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Result row                                                         */
/* ------------------------------------------------------------------ */

function ResultRow({ obs }: { obs: Observable }) {
  const plat = platform(obs);

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border/20 hover:bg-secondary/30 transition-colors text-xs">
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ backgroundColor: entityColors[obs.entity_type] ?? DEFAULT_COLOR }}
      />
      <span className="font-mono text-sm text-foreground truncate min-w-0 flex-1">
        {obs.value}
      </span>
      {plat && (
        <span className="px-1.5 py-0.5 bg-secondary border border-border/50 rounded-sm text-muted-foreground shrink-0">
          {plat}
        </span>
      )}
      <span className="px-1.5 py-0.5 bg-primary/10 border border-primary/25 rounded-sm text-primary/80 shrink-0">
        {obs.tool_source}
      </span>
      <div className="w-16 shrink-0 flex items-center gap-1">
        <div className="flex-1 h-1.5 bg-secondary/60 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${obs.confidence * 100}%`,
              backgroundColor: confidenceColor(obs.confidence),
            }}
          />
        </div>
        <span className="text-[10px] font-mono text-muted-foreground w-7 text-right">
          {(obs.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ResultsPanel                                                       */
/* ------------------------------------------------------------------ */

export function ResultsPanel({
  observables,
  resultsLoading,
  selectedInv,
  selectedStatus,
}: ResultsPanelProps) {
  const [searchText, setSearchText] = useState("");
  const [sortField, setSortField] = useState<SortField>("confidence");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (type: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  /* Filter */
  const filtered = useMemo(() => {
    if (!searchText) return observables;
    const q = searchText.toLowerCase();
    return observables.filter(
      (o) =>
        o.value.toLowerCase().includes(q) ||
        platform(o).toLowerCase().includes(q) ||
        o.tool_source.toLowerCase().includes(q),
    );
  }, [observables, searchText]);

  /* Sort */
  const sorted = useMemo(() => {
    const arr = [...filtered];
    const dir = sortDir === "asc" ? 1 : -1;

    arr.sort((a, b) => {
      switch (sortField) {
        case "confidence":
          return (a.confidence - b.confidence) * dir;
        case "value":
          return a.value.localeCompare(b.value) * dir;
        case "tool_source":
          return a.tool_source.localeCompare(b.tool_source) * dir;
        case "platform":
          return platform(a).localeCompare(platform(b)) * dir;
        default:
          return 0;
      }
    });

    return arr;
  }, [filtered, sortField, sortDir]);

  /* Group by entity_type, ordered by count desc */
  const groups = useMemo(() => {
    const map = new Map<string, Observable[]>();
    for (const obs of sorted) {
      const list = map.get(obs.entity_type);
      if (list) list.push(obs);
      else map.set(obs.entity_type, [obs]);
    }

    return [...map.entries()].sort(([, a], [, b]) => b.length - a.length);
  }, [sorted]);

  return (
    <div className="p-3 flex flex-col overflow-hidden">
      <Panel className="flex-1 flex flex-col overflow-hidden">
        <Heading>Results</Heading>

        <div className="flex-1 relative min-h-0 flex flex-col">
          {resultsLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="text-xs text-muted-foreground animate-pulse">Loading results...</span>
            </div>
          ) : !selectedInv ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="text-xs text-muted-foreground">Select an investigation</span>
            </div>
          ) : observables.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="text-xs text-muted-foreground">
                {selectedStatus === "pending" ? "Waiting for workers..." : "No results"}
              </span>
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-2 mb-3">
                <input
                  className={inputClass}
                  type="text"
                  placeholder="Filter results..."
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  style={{ maxWidth: 240 }}
                />
                <select
                  className={selectClass}
                  value={`${sortField}:${sortDir}`}
                  onChange={(e) => {
                    const [f, d] = e.target.value.split(":") as [SortField, SortDir];
                    setSortField(f);
                    setSortDir(d);
                  }}
                  style={{ maxWidth: 200 }}
                >
                  <option value="confidence:desc">Confidence (high first)</option>
                  <option value="confidence:asc">Confidence (low first)</option>
                  <option value="value:asc">Value (A-Z)</option>
                  <option value="value:desc">Value (Z-A)</option>
                  <option value="tool_source:asc">Tool (A-Z)</option>
                  <option value="platform:asc">Platform (A-Z)</option>
                </select>
                <span className="ml-auto text-xs text-muted-foreground shrink-0">
                  {filtered.length} of {observables.length} results
                </span>
              </div>

              {/* Grouped results */}
              <div className="flex-1 overflow-y-auto min-h-0 flex flex-col gap-2">
                {groups.map(([type, items]) => (
                  <div key={type}>
                    <GroupHeader
                      type={type}
                      count={items.length}
                      collapsed={collapsedGroups.has(type)}
                      onToggle={() => toggleGroup(type)}
                    />
                    {!collapsedGroups.has(type) && (
                      <div className="mt-1 border border-border/20 rounded-md overflow-hidden">
                        {items.map((obs) => (
                          <ResultRow key={obs.id} obs={obs} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {groups.length === 0 && searchText && (
                  <div className="flex-1 flex items-center justify-center">
                    <span className="text-xs text-muted-foreground">No results match "{searchText}"</span>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Entity legend */}
        <div className="flex flex-wrap gap-3 pt-3 border-t border-border/50 mt-3">
          {Object.entries(entityColors).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-muted-foreground">{type}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
