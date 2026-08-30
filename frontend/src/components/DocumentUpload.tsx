import { useRef, useState } from "react";

import { uploadDocument } from "../lib/documentsApi";

interface DocumentUploadProps {
  onUploaded: () => void;
}

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!selectedFile) return;
    setStatus("uploading");
    setError(null);
    try {
      await uploadDocument(selectedFile);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setStatus("idle");
      onUploaded();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  return (
    <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-800">Upload Financial Document</h2>
      <p className="mt-1 text-sm text-slate-500">
        PDF only. The document will be extracted, cleaned, and chunked page-by-page.
      </p>

      <div className="mt-4 flex items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
        />
        <button
          onClick={handleUpload}
          disabled={!selectedFile || status === "uploading"}
          className="shrink-0 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {status === "uploading" ? "Uploading…" : "Upload"}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
    </div>
  );
}
