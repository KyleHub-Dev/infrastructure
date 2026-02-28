import { useState } from "react";
import { OBSERVABLE_TYPE_MAP } from "../lib/api";
import { inputClass, selectClass } from "../lib/constants";
import { Panel, Heading } from "./Panel";

interface InvestigationPayload {
  query: string;
  observable_type: string;
  legal_basis: string;
  purpose: string;
  justification: string;
  ttl_days: number;
}

interface InvestigationModalProps {
  initialTarget: string;
  initialType: string;
  onClose: () => void;
  onSubmit: (payload: InvestigationPayload) => Promise<void>;
}

export function InvestigationModal({ initialTarget, initialType, onClose, onSubmit }: InvestigationModalProps) {
  const [formTarget, setFormTarget] = useState(initialTarget);
  const [formType, setFormType] = useState(initialType);
  const [formBasis, setFormBasis] = useState("legitimate_interest");
  const [formPurpose, setFormPurpose] = useState("");
  const [formJustification, setFormJustification] = useState("");
  const [formTTL, setFormTTL] = useState("90");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!formTarget.trim() || !formPurpose.trim() || formJustification.length < 20) return;
    setSubmitting(true);
    try {
      await onSubmit({
        query: formTarget,
        observable_type: OBSERVABLE_TYPE_MAP[formType] ?? formType,
        legal_basis: formBasis,
        purpose: formPurpose,
        justification: formJustification,
        ttl_days: Number(formTTL),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="w-[480px] max-w-[90vw] max-h-[85vh] overflow-y-auto animate-[modalIn_0.2s_ease-out]"
        onClick={(e) => e.stopPropagation()}
      >
        <Panel>
          <Heading>New Investigation</Heading>

          <label className="block text-xs text-muted-foreground mb-1">Target</label>
          <input
            className={`${inputClass} mb-4`}
            value={formTarget}
            onChange={(e) => setFormTarget(e.target.value)}
            placeholder="Enter target..."
          />

          <label className="block text-xs text-muted-foreground mb-1">Type</label>
          <select className={`${selectClass} mb-4`} value={formType} onChange={(e) => setFormType(e.target.value)}>
            <option value="username">Username</option>
            <option value="email">Email</option>
            <option value="domain">Domain</option>
            <option value="ip">IP Address</option>
          </select>

          <label className="block text-xs text-muted-foreground mb-1">Legal Basis (GDPR Art. 6)</label>
          <select className={`${selectClass} mb-4`} value={formBasis} onChange={(e) => setFormBasis(e.target.value)}>
            <option value="legitimate_interest">Legitimate Interest</option>
            <option value="legal_obligation">Legal Obligation</option>
            <option value="vital_interest">Vital Interest</option>
          </select>

          <label className="block text-xs text-muted-foreground mb-1">Purpose</label>
          <input
            className={`${inputClass} mb-4`}
            value={formPurpose}
            onChange={(e) => setFormPurpose(e.target.value)}
            placeholder="Describe purpose..."
          />

          <label className="block text-xs text-muted-foreground mb-1">
            Justification
            <span className="text-muted-foreground/60 ml-1">(min 20 characters)</span>
          </label>
          <textarea
            className={`${inputClass} mb-1 min-h-[80px] resize-y`}
            value={formJustification}
            onChange={(e) => setFormJustification(e.target.value)}
            placeholder="Detailed justification including Article 14 exemption rationale if applicable..."
          />
          <p className={`text-[10px] mb-4 ${formJustification.length >= 20 ? "text-success" : "text-muted-foreground"}`}>
            {formJustification.length}/20 characters
          </p>

          <label className="block text-xs text-muted-foreground mb-1">Retention Period</label>
          <select className={`${selectClass} mb-4`} value={formTTL} onChange={(e) => setFormTTL(e.target.value)}>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
            <option value="180">180 days</option>
            <option value="365">365 days</option>
          </select>

          <div className="px-3 py-2 bg-secondary/50 border border-border rounded-md mb-4 text-[11px] text-muted-foreground leading-relaxed">
            <span className="block text-primary font-semibold text-[10px] mb-0.5">Privacy Notice</span>
            Data processed per GDPR. Auto-purged after retention period. Audit trail maintained. Only public data collected.
          </div>

          <div className="flex gap-3 justify-end">
            <button
              className="bg-secondary text-foreground text-xs px-4 py-2 rounded-md border border-border hover:bg-secondary/80 transition-colors"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="bg-primary text-primary-foreground text-xs font-semibold px-5 py-2 rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={submitting || !formTarget.trim() || !formPurpose.trim() || formJustification.length < 20}
              onClick={handleSubmit}
            >
              {submitting ? "Creating..." : "Start Investigation"}
            </button>
          </div>
        </Panel>
      </div>

      <style>{`
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.96); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
