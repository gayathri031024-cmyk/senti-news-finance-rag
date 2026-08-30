import type { DocumentListItem, DocumentStatus } from "../types/document";

interface DocumentListProps {
  documents: DocumentListItem[];
  loading: boolean;
  selectedId?: string | null;
  onSelect?: (doc: DocumentListItem) => void;
}

const STATUS_LABEL: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing…",
  processed: "Processed",
  failed: "Failed",
};

const STATUS_STYLES: Record<DocumentStatus, string> = {
  uploaded: "bg-slate-100 text-slate-600",
  processing: "bg-amber-50 text-amber-700",
  processed: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-50 text-rose-700",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentList({ documents, loading, selectedId, onSelect }: DocumentListProps) {
  if (loading && documents.length === 0) {
    return <p className="text-sm text-slate-400">Loading documents…</p>;
  }

  if (documents.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No documents uploaded yet — upload a financial PDF to get started.
      </p>
    );
  }

  return (
    <ul className="w-full max-w-xl divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white shadow-sm">
      {documents.map((doc) => {
        const selectable = Boolean(onSelect) && doc.status === "processed";
        const isSelected = selectedId === doc.id;
        return (
          <li key={doc.id}>
            <button
              type="button"
              disabled={!selectable}
              onClick={() => selectable && onSelect?.(doc)}
              className={`flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition ${
                selectable ? "cursor-pointer hover:bg-slate-50" : "cursor-default"
              } ${isSelected ? "bg-sky-50" : ""}`}
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-800">{doc.filename}</p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {formatFileSize(doc.file_size)}
                  {doc.status === "processed" && (
                    <> · {doc.page_count} page{doc.page_count === 1 ? "" : "s"} · {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}</>
                  )}
                </p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[doc.status]}`}
              >
                {STATUS_LABEL[doc.status]}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
