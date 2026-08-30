export interface QuerySource {
  document_id: string;
  document_name: string;
  page_number: number;
  chunk_id: string;
  relevance_score: number;
}

export interface QueryResponse {
  answer: string;
  sources: QuerySource[];
}
