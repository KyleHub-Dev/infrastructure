import type { Investigation } from "../lib/api";
import { inputClass, selectClass } from "../lib/constants";
import { Panel, Heading } from "./Panel";
import { InvestigationCard } from "./InvestigationCard";

interface InvestigationListProps {
  investigations: Investigation[];
  selectedId: string | null;
  loading: boolean;
  activeCount: number;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  filterText: string;
  onFilterTextChange: (text: string) => void;
  filterStatus: string;
  onFilterStatusChange: (status: string) => void;
}

export function InvestigationList({
  investigations,
  selectedId,
  loading,
  activeCount,
  onSelect,
  onDelete,
  filterText,
  onFilterTextChange,
  filterStatus,
  onFilterStatusChange,
}: InvestigationListProps) {
  return (
    <div className="p-3 border-r border-border/50 overflow-y-auto flex flex-col">
      <Panel className="mb-3">
        <Heading>Investigations</Heading>
        <p className="text-xs text-muted-foreground mb-3">
          {activeCount} active / {investigations.length} shown
        </p>
        <input
          className={inputClass}
          type="text"
          placeholder="Filter by name, ID, or type..."
          value={filterText}
          onChange={(e) => onFilterTextChange(e.target.value)}
        />
        <select
          className={`${selectClass} mt-2`}
          value={filterStatus}
          onChange={(e) => onFilterStatusChange(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="archived">Archived</option>
        </select>
      </Panel>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-xs text-muted-foreground animate-pulse">Loading...</span>
        </div>
      ) : investigations.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-xs text-muted-foreground">
            {filterText || filterStatus !== "all"
              ? "No matching investigations"
              : "No investigations yet"}
          </span>
        </div>
      ) : (
        investigations.map((inv) => (
          <InvestigationCard
            key={inv.id}
            investigation={inv}
            selected={selectedId === inv.id}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ))
      )}

      <Panel className="mt-3">
        <Heading>Compliance</Heading>
        <div className="flex flex-col gap-2">
          {[
            { label: "GDPR", status: "Active" },
            { label: "Auto-purge", status: "Enabled" },
            { label: "Encryption", status: "AES-256" },
            { label: "Audit log", status: "Recording" },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{item.label}</span>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-success" />
                <span className="text-success font-medium">{item.status}</span>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
