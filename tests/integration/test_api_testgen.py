"""Integration tests: Testgen HTTP API (API_CONTRACTS 1.7)."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from qme.config.settings import get_settings
from qme.main import create_app
from tests.testgen_fixtures import big_questions, write_bank

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


@pytest.fixture()
def big_api(monkeypatch, tmp_path):
    monkeypatch.setenv("QME_BLUEPRINT_PATH", str(write_bank(tmp_path, big_questions())))
    monkeypatch.setattr("qme.api.routes.testgen._cache", {"key": None, "bank": None})
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
    assert body["chapters"] == ["book.pdf › Percentage", "book.pdf › Time & Work"]
    assert set(body["difficulties"]) == {"easy", "medium", "hard"}
    assert body["question_count"] == 6
    assert body["buckets"]["Percentage"]["Successive Percentages"]["easy"] == 2
    assert body["contract"]["required_filters"] == ["chapter", "topic", "difficulty"]
    assert [s["name"] for s in body["sources"]] == ["book.pdf"]
    chapters = body["sources"][0]["chapters"]
    assert chapters[0]["key"] == "book.pdf › Percentage"
    assert chapters[0]["question_count"] == 4
    assert chapters[0]["difficulty_counts"] == {"easy": 2, "medium": 2}
    assert body["knowledge_coverage"] == {
        "covered_chapters": ["Percentage", "Time & Work"],
        "missing_chapters": [],
    }


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


# --- friendly shape (API_CONTRACTS 1.7) ------------------------------------------

ALL_CHAPTERS = ["book.pdf › Percentage", "book.pdf › Time & Work"]


def test_friendly_single_difficulty_200(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={
            "title": "Unit 1",
            "chapters": ALL_CHAPTERS,
            "difficulty": {"mode": "single", "value": "easy"},
            "count": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["seed"] is not None  # generated + echoed for submit round-trip
    assert len(body["questions"]) == 10
    assert body["coverage"]["by_difficulty"] == {"easy": 10}
    assert body["coverage"]["by_source"] == {"book.pdf": 10}
    assert set(body["coverage"]["by_chapter"]) <= set(ALL_CHAPTERS)


def test_friendly_mixed_counts_200(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={
            "seed": 5,
            "chapters": ALL_CHAPTERS,
            "difficulty": {"mode": "mixed", "counts": {"easy": 5, "medium": 5, "hard": 5}},
            "count": 15,
        },
    )
    assert response.status_code == 200
    assert response.json()["coverage"]["by_difficulty"] == {
        "easy": 5,
        "medium": 5,
        "hard": 5,
    }


def test_friendly_all_chapters_min_30(big_api):
    too_small = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"difficulty": {"mode": "mixed", "counts": {"easy": 5, "medium": 5}}, "count": 10},
    )
    assert too_small.status_code == 422
    assert_envelope(too_small.json(), "INVALID_INPUT")
    violations = too_small.json()["error"]["details"]["violations"]
    assert any(v["rule"] == "count_minimum" for v in violations)

    ok = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={
            "seed": 1,
            "difficulty": {"mode": "mixed", "counts": {"easy": 15, "medium": 10, "hard": 5}},
            "count": 30,
        },
    )
    assert ok.status_code == 200
    assert ok.json()["coverage"]["total"] == 30


def test_friendly_count_multiple_of_5(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"chapters": ["book.pdf › Percentage"], "difficulty": {"mode": "single", "value": "easy"}, "count": 12},
    )
    assert response.status_code == 422
    violations = response.json()["error"]["details"]["violations"]
    assert violations[0]["rule"] == "count_multiple_of_5"


def test_friendly_mixed_sum_mismatch(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"count": 10, "difficulty": {"mode": "mixed", "counts": {"easy": 5, "medium": 4}}},
    )
    assert response.status_code == 422
    rules = [v["rule"] for v in response.json()["error"]["details"]["violations"]]
    assert "mixed_counts_sum" in rules


def test_friendly_infeasible_difficulty_reports_availability(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"chapters": ALL_CHAPTERS, "difficulty": {"mode": "single", "value": "hard"}, "count": 10},
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(v["rule"] == "feasibility" for v in details["violations"])
    assert details["available_by_difficulty"] == {"easy": 15, "medium": 10, "hard": 5}


def test_both_shapes_rejected(big_api):
    response = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"selections": [{"count": 5}], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
    )
    assert response.status_code == 422
    rules = [v["rule"] for v in response.json()["error"]["details"]["violations"]]
    assert rules == ["single_shape"]


def test_unknown_source_and_chapter_422(big_api):
    source = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"sources": ["ghost"], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
    )
    assert source.status_code == 422
    assert source.json()["error"]["details"]["available"]["sources"] == ["book.pdf"]

    chapter = big_api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"chapters": ["book.pdf › Ghost"], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
    )
    assert chapter.status_code == 422
    rules = [v["rule"] for v in chapter.json()["error"]["details"]["violations"]]
    assert rules == ["unknown_chapter"]


def test_legacy_shape_with_source_still_200(api):
    response = api.post(
        "/api/v1/tests",
        headers=auth(),
        json={"seed": 3, "selections": [{"count": 3, "difficulty": "easy", "source": "book.pdf"}]},
    )
    assert response.status_code == 200
    assert response.json()["coverage"]["by_source"] == {"book.pdf": 3}


# --- submit round-trip ------------------------------------------------------------

SUBMIT_BODY = {
    "seed": 42,
    "chapters": ALL_CHAPTERS,
    "difficulty": {"mode": "mixed", "counts": {"easy": 5, "medium": 5}},
    "count": 10,
}


def _create_friendly_test(big_api) -> dict:
    response = big_api.post("/api/v1/tests", headers=auth(), json=SUBMIT_BODY)
    assert response.status_code == 200
    return response.json()


def test_submit_all_correct_scores_100(big_api):
    test = _create_friendly_test(big_api)
    answers = {entry["question_id"]: entry["correct_answer"] for entry in test["answer_key"]}
    response = big_api.post(
        "/api/v1/tests/submit",
        headers=auth(),
        json={"test_id": test["test_id"], "request": SUBMIT_BODY, "answers": answers, "elapsed_seconds": 120},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["test_id"] == test["test_id"]
    assert body["score"] == {"correct": 10, "total": 10, "percent": 100.0}
    assert body["elapsed_seconds"] == 120
    assert all(line["is_correct"] for line in body["results"])
    assert body["by_difficulty"]["easy"]["total"] == 5


def test_submit_is_idempotent(big_api):
    test = _create_friendly_test(big_api)
    answers = {entry["question_id"]: entry["correct_answer"] for entry in test["answer_key"]}
    request = {"test_id": test["test_id"], "request": SUBMIT_BODY, "answers": answers}
    first = big_api.post("/api/v1/tests/submit", headers=auth(), json=request)
    second = big_api.post("/api/v1/tests/submit", headers=auth(), json=request)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_submit_wrong_answers_score_low(big_api):
    test = _create_friendly_test(big_api)
    answers = {
        entry["question_id"]: ("B" if entry["correct_answer"] != "B" else "C")
        for entry in test["answer_key"]
    }
    response = big_api.post(
        "/api/v1/tests/submit",
        headers=auth(),
        json={"request": SUBMIT_BODY, "answers": answers},
    )
    assert response.status_code == 200
    assert response.json()["score"]["correct"] == 0


def test_submit_missing_seed_422(big_api):
    response = big_api.post(
        "/api/v1/tests/submit",
        headers=auth(),
        json={"request": {"difficulty": {"mode": "single", "value": "easy"}, "count": 10}, "answers": {}},
    )
    assert response.status_code == 422
    rules = [v["rule"] for v in response.json()["error"]["details"]["violations"]]
    assert rules == ["seed_required"]


def test_submit_invalid_option_key_422_answer_mismatch(big_api):
    test = _create_friendly_test(big_api)
    qid = test["questions"][0]["question_id"]
    response = big_api.post(
        "/api/v1/tests/submit",
        headers=auth(),
        json={"request": SUBMIT_BODY, "answers": {qid: "Z"}},
    )
    assert response.status_code == 422
    body = response.json()
    assert_envelope(body, "ANSWER_MISMATCH")
    assert body["error"]["details"]["invalid_option_keys"] == {qid: "Z"}


def test_submit_unknown_question_id_422_answer_mismatch(big_api):
    response = big_api.post(
        "/api/v1/tests/submit",
        headers=auth(),
        json={
            "request": {
                "seed": 42,
                "chapters": ALL_CHAPTERS,
                "difficulty": {"mode": "single", "value": "easy"},
                "count": 10,
            },
            "answers": {"ghost": "A"},
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert_envelope(body, "ANSWER_MISMATCH")
    assert body["error"]["details"]["unknown_question_ids"] == ["ghost"]


# --- practice pagination + sources ------------------------------------------------


def test_practice_pages_disjoint_with_seed_echo(api):
    first = api.post(
        "/api/v1/practice", headers=auth(), json={"count": 2, "page": 1, "seed": 9, "mode": "mixed"}
    )
    assert first.status_code == 200
    body = first.json()
    assert body["seed"] == 9
    assert body["pagination"] == {
        "page": 1,
        "count": 2,
        "total": 6,
        "total_pages": 3,
        "has_more": True,
    }
    ids_page1 = {q["question_id"] for q in body["questions"]}

    second = api.post(
        "/api/v1/practice", headers=auth(), json={"count": 2, "page": 2, "seed": 9, "mode": "mixed"}
    )
    ids_page2 = {q["question_id"] for q in second.json()["questions"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_practice_seed_generated_when_absent(api):
    response = api.post("/api/v1/practice", headers=auth(), json={"count": 2})
    assert response.status_code == 200
    assert isinstance(response.json()["seed"], int)


def test_practice_page_out_of_range_422(api):
    response = api.post(
        "/api/v1/practice", headers=auth(), json={"count": 2, "page": 4, "seed": 9}
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details["total_pages"] == 3
    assert details["page"] == 4


def test_practice_unknown_source_422(api):
    response = api.post("/api/v1/practice", headers=auth(), json={"source": "ghost"})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["available"]["sources"] == ["book.pdf"]


def test_practice_qualified_chapter_200(api):
    response = api.post(
        "/api/v1/practice",
        headers=auth(),
        json={"count": 5, "chapter": "book.pdf › Time & Work", "seed": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert {q["classification"]["chapter"] for q in body["questions"]} == {"Time & Work"}
    assert body["filters_applied"]["source"] == "book.pdf"


# --- knowledge endpoint (source-less) ----------------------------------------------


def test_knowledge_endpoint_unqualified(api):
    response = api.get(f"/api/v1/chapters/{quote('Percentage')}/knowledge", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["chapter"] == "Percentage"
    assert body["formula_summary"] == ["Percentage summary"]
    entry = body["topics"]["Successive Percentages"]
    assert entry["formulas"] == ["Successive Percentages formula"]
    assert entry["short_tricks"] == ["Successive Percentages trick"]


def test_knowledge_endpoint_qualified_key_strips_source(api):
    key = quote("book.pdf › Percentage", safe="")
    response = api.get(f"/api/v1/chapters/{key}/knowledge", headers=auth())
    assert response.status_code == 200
    assert response.json()["chapter"] == "Percentage"


def test_knowledge_endpoint_topic_filter(api):
    response = api.get(
        f"/api/v1/chapters/{quote('Percentage')}/knowledge",
        headers=auth(),
        params={"topic": "Successive Percentages"},
    )
    assert response.status_code == 200
    assert list(response.json()["topics"]) == ["Successive Percentages"]


def test_knowledge_endpoint_unknown_chapter_404(api):
    response = api.get(f"/api/v1/chapters/{quote('Ghost')}/knowledge", headers=auth())
    assert response.status_code == 404
    assert_envelope(response.json(), "NOT_FOUND")


def test_knowledge_endpoint_empty_when_knowledge_missing(monkeypatch, tmp_path):
    knowledge = {"schema_version": "1.0", "provenance": {}, "chapters": {}, "web_sources": []}
    path = write_bank(tmp_path, knowledge_override=knowledge)
    monkeypatch.setenv("QME_BLUEPRINT_PATH", str(path))
    monkeypatch.setenv("QME_API_KEY", API_KEY)
    monkeypatch.setattr("qme.api.routes.testgen._cache", {"key": None, "bank": None})
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.get(f"/api/v1/chapters/{quote('Percentage')}/knowledge", headers=auth())
        assert response.status_code == 200
        body = response.json()
        assert body["formula_summary"] == []
        assert body["topics"] == {}
        meta = client.get("/api/v1/bank/meta", headers=auth()).json()
        assert meta["knowledge_coverage"]["missing_chapters"] == ["Percentage", "Time & Work"]
    finally:
        get_settings.cache_clear()
