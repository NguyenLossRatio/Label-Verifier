from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_index_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Label Verifier" in response.text
