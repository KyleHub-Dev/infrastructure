import { useState, useEffect, useCallback } from "react";
import { api } from "./lib/api";
import type { Investigation, Observable, InvestigationStats } from "./lib/api";
import { Header } from "./components/Header";
import { SearchBar } from "./components/SearchBar";
import { InvestigationList } from "./components/InvestigationList";
import { ResultsPanel } from "./components/ResultsPanel";
import { StatsPanel } from "./components/StatsPanel";
import { InvestigationModal } from "./components/InvestigationModal";
import { ErrorBar } from "./components/ErrorBar";

export default function App() {
  const [selectedInv, setSelectedInv] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTarget, setModalTarget] = useState("");
  const [modalType, setModalType] = useState("username");

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [observables, setObservables] = useState<Observable[]>([]);
  const [stats, setStats] = useState<InvestigationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");

  /* ---- Fetch investigations ---- */

  const fetchInvestigations = useCallback(async () => {
    try {
      const list = await api<Investigation[]>("/api/v1/investigations/");
      setInvestigations(list);
      return list;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load investigations");
      return null;
    }
  }, []);

  /* Initial load */
  useEffect(() => {
    (async () => {
      setLoading(true);
      const list = await fetchInvestigations();
      if (list && list.length > 0) {
        setSelectedInv(list[0].id);
      }
      setLoading(false);
    })();
  }, [fetchInvestigations]);

  /* ---- Fetch results + stats for selected investigation ---- */

  const fetchResultsAndStats = useCallback(async (invId: string) => {
    setResultsLoading(true);
    try {
      const [obs, s] = await Promise.all([
        api<Observable[]>(`/api/v1/observables/?investigation_id=${invId}`),
        api<InvestigationStats>(`/api/v1/graph/stats/${invId}`),
      ]);
      setObservables(obs);
      setStats(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    } finally {
      setResultsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedInv) {
      setObservables([]);
      setStats(null);
      return;
    }
    fetchResultsAndStats(selectedInv);
  }, [selectedInv, fetchResultsAndStats]);

  /* Poll while any investigation is pending/running */
  useEffect(() => {
    const hasActive = investigations.some(
      (inv) => inv.status === "pending" || inv.status === "running",
    );
    if (!hasActive) return;

    const interval = setInterval(async () => {
      const list = await fetchInvestigations();
      if (list && selectedInv) {
        const prev = investigations.find((i) => i.id === selectedInv);
        const next = list.find((i) => i.id === selectedInv);
        if (
          prev && next &&
          (prev.node_count !== next.node_count || prev.edge_count !== next.edge_count)
        ) {
          setSelectedInv((s) => s);
          fetchResultsAndStats(selectedInv);
        }
      }
    }, 5000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [investigations, selectedInv, fetchInvestigations]);

  /* ---- Action handlers ---- */

  const handleCreate = async (payload: {
    query: string;
    observable_type: string;
    legal_basis: string;
    purpose: string;
    justification: string;
    ttl_days: number;
  }) => {
    setError(null);
    try {
      const inv = await api<Investigation>("/api/v1/investigations/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setModalOpen(false);
      await fetchInvestigations();
      setSelectedInv(inv.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create investigation");
    }
  };

  const handleDelete = async (invId: string) => {
    setError(null);
    try {
      await api(`/api/v1/investigations/${invId}`, { method: "DELETE" });
      const list = await fetchInvestigations();
      if (selectedInv === invId) {
        setSelectedInv(list && list.length > 0 ? list[0].id : null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete investigation");
    }
  };

  /* ---- Derived values ---- */

  const activeCount = investigations.filter(
    (i) => i.status === "pending" || i.status === "running",
  ).length;

  const filteredInvestigations = investigations.filter((inv) => {
    const matchesText =
      !filterText ||
      inv.query.toLowerCase().includes(filterText.toLowerCase()) ||
      inv.id.toLowerCase().includes(filterText.toLowerCase()) ||
      inv.observable_type.toLowerCase().includes(filterText.toLowerCase());
    const matchesStatus = filterStatus === "all" || inv.status === filterStatus;
    return matchesText && matchesStatus;
  });

  const selectedStatus = investigations.find((i) => i.id === selectedInv)?.status;

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <Header />

      <SearchBar
        onInvestigate={(query, type) => {
          setModalTarget(query);
          setModalType(type);
          setModalOpen(true);
        }}
      />

      <div className="grid grid-cols-[28%_44%_28%] flex-1 min-h-0 overflow-hidden">
        <InvestigationList
          investigations={filteredInvestigations}
          selectedId={selectedInv}
          loading={loading}
          activeCount={activeCount}
          onSelect={setSelectedInv}
          onDelete={handleDelete}
          filterText={filterText}
          onFilterTextChange={setFilterText}
          filterStatus={filterStatus}
          onFilterStatusChange={setFilterStatus}
        />

        <ResultsPanel
          observables={observables}
          resultsLoading={resultsLoading}
          selectedInv={selectedInv}
          selectedStatus={selectedStatus}
        />

        <StatsPanel
          stats={stats}
          activeCount={activeCount}
          totalInvestigations={investigations.length}
          selectedInv={selectedInv}
        />
      </div>

      <ErrorBar error={error} onDismiss={() => setError(null)} />

      {modalOpen && (
        <InvestigationModal
          initialTarget={modalTarget}
          initialType={modalType}
          onClose={() => setModalOpen(false)}
          onSubmit={handleCreate}
        />
      )}
    </div>
  );
}
