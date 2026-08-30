"""
SQLAlchemy engine + session setup.

One engine per process, one session per request (via the `get_db`
FastAPI dependency below).
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """
    Lightweight connectivity + pgvector availability check, used by
    /api/health. Never raises — callers get a status dict either way.
    """
    result = {"connected": False, "pgvector_installed": False, "error": None}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["connected"] = True

            row = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).first()
            result["pgvector_installed"] = row is not None
    except Exception as exc:  # noqa: BLE001 - surfaced in health response, not raised
        result["error"] = str(exc)
    return result
