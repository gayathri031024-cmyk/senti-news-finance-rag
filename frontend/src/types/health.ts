export interface DatabaseStatus {
  connected: boolean;
  pgvector_installed: boolean;
  error: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app_name: string;
  environment: string;
  database: DatabaseStatus;
}
