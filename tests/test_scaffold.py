import pytest
from fastapi.testclient import TestClient

from citehop import health
from citehop.api.main import app
from citehop.apply_sql import statements


def test_health_redacts_failure_and_keeps_api_alive(monkeypatch):
    def fail():
        raise RuntimeError("secret-password")

    monkeypatch.setattr(health, "maria_ready", lambda: True)
    monkeypatch.setattr(health, "neo_ready", fail)
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "services": {"mariadb": "ready", "neo4j": "unavailable"}
    }
    assert "secret" not in response.text


def test_sql_handles_quoted_semicolons():
    assert statements("SELECT 'a;b'; SELECT 1;") == ["SELECT 'a;b'", "SELECT 1"]
    assert statements("-- head\nSELECT 1;\n-- note\n/* end */\n") == ["-- head\nSELECT 1"]
    with pytest.raises(ValueError, match="DELIMITER"):
        statements("DELIMITER $$\nSELECT 1$$")
