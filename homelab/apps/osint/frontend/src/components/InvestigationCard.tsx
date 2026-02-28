import { useState } from "react";
import { statusDotClass, statusTextClass } from "../lib/constants";
import type { Investigation } from "../lib/api";

interface InvestigationCardProps {
  investigation: Investigation;
  selected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function InvestigationCard({ investigation: inv, selected, onSelect, onDelete }: InvestigationCardProps) {
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  return (
    <div
      className={`bg-card/90 border border-border/50 p-3.5 mb-2 cursor-pointer rounded-lg transition-colors hover:border-primary/30
        ${selected ? "border-l-2 border-l-primary bg-primary/5" : ""}
      `}
      onClick={() => onSelect(inv.id)}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2 h-2 rounded-full shrink-0 ${statusDotClass(inv.status)}`} />
        <span className="font-display font-bold text-sm text-foreground truncate">{inv.id}</span>
        <span className={`ml-auto text-[10px] font-semibold uppercase px-1.5 py-0.5 border rounded-sm ${statusTextClass(inv.status)} border-current`}>
          {inv.status}
        </span>
      </div>

      <div className="font-semibold text-sm text-primary mb-1 break-all">{inv.query}</div>

      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] px-1.5 py-px bg-primary/10 text-primary/80 border border-primary/25 rounded-sm">
          {inv.observable_type}
        </span>
        <span className="text-[10px] px-1.5 py-px bg-warning/10 text-warning/80 border border-warning/25 rounded-sm capitalize">
          {inv.legal_basis.replace(/_/g, " ")}
        </span>
      </div>

      <p className="text-[11px] text-muted-foreground mb-2">{inv.purpose}</p>

      <div className="flex gap-4 text-xs items-end">
        {[
          { label: "Nodes", value: inv.node_count.toLocaleString() },
          { label: "Edges", value: inv.edge_count.toLocaleString() },
          { label: "TTL", value: `${inv.ttl_days}d` },
        ].map((s) => (
          <div key={s.label}>
            <div className="text-[9px] uppercase text-muted-foreground mb-0.5">{s.label}</div>
            <div className="font-mono font-bold text-foreground">{s.value}</div>
          </div>
        ))}

        <div className="ml-auto">
          {deleteConfirm ? (
            <div className="flex gap-1">
              <button
                className="text-[10px] px-2 py-1 bg-error/15 text-error border border-error/30 rounded hover:bg-error/25 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(inv.id);
                }}
              >
                Confirm
              </button>
              <button
                className="text-[10px] px-2 py-1 bg-secondary text-muted-foreground border border-border rounded hover:bg-secondary/80 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteConfirm(false);
                }}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              className="text-[10px] px-2 py-1 text-muted-foreground hover:text-error transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirm(true);
              }}
              title="Delete investigation"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
