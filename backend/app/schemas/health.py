from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    connected: bool
    pgvector_installed: bool
    error: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    app_name: str
    environment: str
    database: DatabaseStatus
