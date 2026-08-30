import type { QuerySource } from "../types/query";

interface SourceListProps {
  sources: QuerySource[];
}

export function SourceList({ sources }: SourceListProps) {
  if (sources.length === 0) return null;

  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Sources
      </h3>
      <ul className="mt-2 space-y-2">
        {sources.map((source) => (
          <li
            key={source.chunk_id}
            className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-700">
                {source.document_name}
              </p>
              <p className="text-xs text-slate-400">Page {source.page_number}</p>
            </div>
            <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500 shadow-sm">
              {(source.relevance_score * 100).toFixed(0)}% match
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
