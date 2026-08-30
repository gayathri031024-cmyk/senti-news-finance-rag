import { useCallback, useEffect, useState } from "react";

import { DocumentList } from "./components/DocumentList";
import { DocumentUpload } from "./components/DocumentUpload";
import { QueryPanel } from "./components/QueryPanel";
import { StatusBadge } from "./components/StatusBadge";
import { fetchDocuments } from "./lib/documentsApi";
import { useHealth } from "./lib/useHealth";
import type { DocumentListItem } from "./types/document";

function App() {
  const { state, error: healthError, refresh } = useHealth();

  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [selected, setSelected] = useState<DocumentListItem | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const result = await fetchDocuments();
      setDocuments(result);
    } catch {
      // Backend/document list errors are non-fatal for this simple UI —
      // the connection status badge already surfaces backend issues.
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Poll while anything is still processing, so status flips to
  // processed/failed without a manual refresh.
  useEffect(() => {
    const hasInFlight = documents.some(
      (doc) => doc.status === "uploaded" || doc.status === "processing"
    );
    if (!hasInFlight) return;

    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
  }, [documents, loadDocuments]);

  // If the selected document disappears from the list, or a re-fetch
  // returns a fresher copy of it (e.g. status just flipped to
  // processed), keep `selected` in sync.
  useEffect(() => {
    if (!selected) return;
    const fresh = documents.find((doc) => doc.id === selected.id);
    if (!fresh) {
      setSelected(null);
    } else if (fresh !== selected) {
      setSelected(fresh);
    }
  }, [documents, selected]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">SentiNews Research</h1>
            <p className="text-sm text-slate-500">
              Finance Document Research Assistant — upload financial documents and ask
              grounded questions about them.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge state={state} />
            <button
              onClick={refresh}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              Recheck
            </button>
          </div>
        </div>
        {healthError && (
          <p className="mx-auto mt-2 max-w-6xl text-sm text-rose-500">
            Couldn't reach the backend at the configured API URL: {healthError}
          </p>
        )}
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 py-8 lg:grid-cols-[minmax(0,320px)_1fr]">
        <section className="space-y-6">
          <DocumentUpload onUploaded={loadDocuments} />
          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Documents
            </h2>
            <DocumentList
              documents={documents}
              loading={documentsLoading}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </div>
        </section>

        <section className="min-h-[28rem]">
          <QueryPanel selectedDocument={selected} />
        </section>
      </main>
    </div>
  );
}

export default App;
