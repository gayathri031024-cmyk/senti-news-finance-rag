from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_200():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_response_shape():
    """
    The endpoint must always return this shape, whether or not a
    database is actually reachable — health checks should never 500.
    """
    body = client.get("/api/health").json()

    assert body["status"] in {"ok", "degraded"}
    assert "app_name" in body
    assert "environment" in body
    assert "database" in body
    assert "connected" in body["database"]
    assert "pgvector_installed" in body["database"]


def test_health_reports_degraded_when_db_unreachable(monkeypatch):
    """
    With no reachable Postgres, the endpoint should report a degraded
    status rather than raising an error.
    """
    import app.api.health as health_module

    def fake_check_db_connection():
        return {"connected": False, "pgvector_installed": False, "error": "could not connect"}

    monkeypatch.setattr(health_module, "check_db_connection", fake_check_db_connection)

    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is False
