import type { DocumentDetail, DocumentListItem, DocumentUploadResponse } from "../types/document";

const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? `Upload failed with status ${response.status}`;
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchDocuments(): Promise<DocumentListItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents`);
  if (!response.ok) {
    throw new Error(`Failed to load documents (status ${response.status})`);
  }
  return response.json();
}

export async function fetchDocument(id: string): Promise<DocumentDetail> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to load document (status ${response.status})`);
  }
  return response.json();
}
