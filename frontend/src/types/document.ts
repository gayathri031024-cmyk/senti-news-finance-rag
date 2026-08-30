export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed";

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
}

export interface DocumentListItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  page_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentListItem {
  error_message: string | null;
}
