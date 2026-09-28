"""Integration tests: FastAPI app (Session C gate)."""

from fastapi.testclient import TestClient

from qme import __version__
from qme.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_200() -> None:
    client = make_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_body_shape() -> None:
    client = make_client()
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["environment"]
    assert isinstance(body["openai_configured"], bool)


def test_openapi_available() -> None:
    client = make_client()
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Question Metadata Engine"
