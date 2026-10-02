"""Integration tests: Testgen HTTP API (API_CONTRACTS 1.7)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from qme.config.settings import get_settings
from qme.main import create_app
from tests.testgen_fixtures import write_bank

API_KEY = "unit-test-key-123"


@pytest.fixture()
def blueprint(tmp_path):
    return write_bank(tmp_path)


@pytest.fixture()
def api(monkeypatch, blueprint):
    monkeypatch.setenv("QME_BLUEPRINT_PATH", str(blueprint))
    monkeypatch.setenv("QME_API_KEY", API_KEY)
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def auth(key: str | None = API_KEY) -> dict:
    return {"X-API-Key": key} if key is not None else {}


def assert_envelope(body: dict, code: str) -> None:
    error = body["error"]
    assert error["code"] == code
    assert error["message"]
    assert isinstance(error["details"], dict)
    uuid.UUID(error["request_id"])  # must be a parseable uuid


def test_health_open_without_key(monkeypatch):
    monkeypatch.delenv("QME_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        get_settings.cache_clear()


def test_401_missing_key(api):
    response = api.get("/api/v1/bank/meta")
    assert response.status_code == 401
    assert_envelope(response.json(), "UNAUTHORIZED")


def test_401_wrong_key(api):
    response = api.get("/api/v1/bank/meta", headers=auth("wrong-key"))
    assert response.status_code == 401
    assert_envelope(response.json(), "UNAUTHORIZED")


def test_bank_meta_shape(api):
    response = api.get("/api/v1/bank/meta", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["chapters"] == ["Percentage", "Time & Work"]
    assert set(body["difficulties"]) == {"easy", "medium", "hard"}
    assert body["question_count"] == 6
    assert body["buckets"]["Percentage"]["Successive Percentages"]["easy"] == 2
    assert body["contract"]["required_filters"] == ["chapter", "topic", "difficulty"]


def test_tests_happy_path(api):
    response = api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"seed": 42, "selections": [{"count": 3, "difficulty": "easy"}]},
    )
    assert response.status_code == 200
    body = response.json()
    for field in ["test_id", "questions", "answer_key", "coverage", "timing"]:
        assert field in body
    assert body["coverage"]["total"] == 3
    assert body["coverage"]["by_difficulty"] == {"easy": 3}
    assert len(body["questions"]) == len(body["answer_key"]) == 3


def test_practice_happy_path(api):
    response = api.post(
        "/api/v1/practice",
        headers=auth(),
        json={"seed": 7, "count": 4, "mode": "progressive"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "progressive"
    assert body["coverage"]["total"] == 4
    assert body["practice_id"].startswith("P-")


def test_422_malformed_body(api):
    response = api.post(
        "/api/v1/tests", headers=auth(), json={"selections": []}
    )
    assert response.status_code == 422
    body = response.json()
    assert_envelope(body, "VALIDATION_ERROR")
    assert body["error"]["details"]["fields"]


def test_422_unknown_chapter_lists_available(api):
    response = api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"selections": [{"count": 2, "chapter": "Nonexistent"}]},
    )
    assert response.status_code == 422
    body = response.json()
    assert_envelope(body, "INVALID_INPUT")
    available = body["error"]["details"]["available"]["chapters"]
    assert "Percentage" in available


def test_503_broken_bank_reports_issues(monkeypatch, tmp_path):
    broken = write_bank(tmp_path, contract_overrides={"output_fields": ["test_id"]})
    monkeypatch.setenv("QME_BLUEPRINT_PATH", str(broken))
    monkeypatch.setenv("QME_API_KEY", API_KEY)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/v1/tests",
            headers=auth(),
            json={"selections": [{"count": 1}]},
        )
        assert response.status_code == 503
        body = response.json()
        assert_envelope(body, "SERVICE_UNAVAILABLE")
        issues = body["error"]["details"]["issues"]
        assert any("output_fields missing" in issue for issue in issues)
    finally:
        get_settings.cache_clear()


def test_production_refuses_to_boot_without_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("QME_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="QME_API_KEY must be set"):
            create_app()
    finally:
        get_settings.cache_clear()
