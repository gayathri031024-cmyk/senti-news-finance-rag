from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_db_connection
from app.schemas.health import DatabaseStatus, HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Reports backend liveness plus a live check of the database
    connection and whether the pgvector extension is installed.
    """
    db_status = check_db_connection()
    overall = "ok" if db_status["connected"] and db_status["pgvector_installed"] else "degraded"

    return HealthResponse(
        status=overall,
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        database=DatabaseStatus(**db_status),
    )
