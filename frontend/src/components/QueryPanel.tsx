import { useState } from "react";

import { askQuestion } from "../lib/queryApi";
import type { DocumentListItem } from "../types/document";
import type { QueryResponse } from "../types/query";
import { SourceList } from "./SourceList";

interface QueryPanelProps {
  selectedDocument: DocumentListItem | null;
}

type Status = "idle" | "loading" | "error";

export function QueryPanel({ selectedDocument }: QueryPanelProps) {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedDocument) return;

    const trimmed = question.trim();
    if (!trimmed) {
      setStatus("error");
      setError("Enter a question before submitting.");
      return;
    }

    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const response = await askQuestion(selectedDocument.id, trimmed);
      setResult(response);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong reaching the backend."
      );
    }
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-800">Research Assistant</h2>

      {!selectedDocument && (
        <p className="mt-2 text-sm text-slate-400">
          Select a processed document on the left to ask questions about it.
        </p>
      )}

      {selectedDocument && (
        <>
          <p className="mt-1 text-sm text-slate-500">
            Asking questions about{" "}
            <span className="font-medium text-slate-700">
              {selectedDocument.filename}
            </span>
          </p>

          <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question…"
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={status === "loading"}
              className="shrink-0 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {status === "loading" ? "Thinking…" : "Ask"}
            </button>
          </form>

          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

          {status === "loading" && (
            <p className="mt-4 text-sm text-slate-400">Retrieving evidence and generating an answer…</p>
          )}

          {result && (
            <div className="mt-4 flex-1 overflow-y-auto">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Answer
              </h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                {result.answer}
              </p>

              <SourceList sources={result.sources} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
