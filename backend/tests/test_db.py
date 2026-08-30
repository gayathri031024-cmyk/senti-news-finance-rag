import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import check_db_connection


def test_check_db_connection_handles_unreachable_db(monkeypatch):
    """
    check_db_connection() must never raise — it should degrade
    gracefully to a status dict when the database can't be reached.
    """
    import app.db.session as session_module

    bad_engine = create_engine("postgresql+psycopg://nouser:nopass@localhost:1/doesnotexist")
    monkeypatch.setattr(session_module, "engine", bad_engine)

    result = check_db_connection()
    assert result["connected"] is False
    assert result["pgvector_installed"] is False
    assert result["error"] is not None


@pytest.mark.skipif(
    not os.getenv("RUN_DB_INTEGRATION_TESTS"),
    reason="Requires a live Postgres with pgvector (docker compose up db). "
    "Set RUN_DB_INTEGRATION_TESTS=1 to enable.",
)
def test_live_db_connection_and_pgvector():
    """
    Integration test against a real database. Run after `docker compose
    up -d db` and `alembic upgrade head`:

        RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_db.py -k live
    """
    from app.core.config import get_settings
    from app.models.document import Document

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)

    result = check_db_connection()
    assert result["connected"] is True
    assert result["pgvector_installed"] is True

    with Session() as db:
        count = db.query(Document).count()
        assert count >= 0
