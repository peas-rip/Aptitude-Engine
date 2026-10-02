"""End-to-end against the real external-agent files in data/input (gitignored).

Skipped automatically on machines without the bank files (fresh clones, CI).
"""

import json
from pathlib import Path

import pytest

from qme.testgen import generate_practice, generate_test, load_bank
from qme.testgen.schemas import GeneratedTest, PracticeRequest, PracticeSet, Selection, TestRequest

BLUEPRINT = Path("data/input/aptitude_test_blueprint.json")
AGENT_READY = Path("data/input/book_questions_agent_ready.jsonl")

pytestmark = pytest.mark.skipif(
    not (BLUEPRINT.exists() and AGENT_READY.exists()),
    reason="external agent bank not present in data/input (gitignored)",
)


@pytest.fixture(scope="module")
def bank():
    return load_bank(BLUEPRINT)


def test_bank_loads_with_contract_intact(bank):
    assert len(bank.questions) == 1310
    assert len(bank.chapters) == 17
    assert bank.difficulties == ["easy", "hard", "medium"]
    assert bank.blueprint.test_generation_contract.required_filters == [
        "chapter",
        "topic",
        "difficulty",
    ]


def test_generate_test_roundtrip(bank):
    test = generate_test(
        bank,
        TestRequest(
            title="E2E smoke",
            seed=42,
            selections=[Selection(count=5, difficulty="hard")],
        ),
    )
    again = GeneratedTest.model_validate_json(test.model_dump_json())
    assert again.test_id == test.test_id
    assert test.coverage.total == 5
    assert test.coverage.by_difficulty == {"hard": 5}
    ids = [q.question_id for q in test.questions]
    assert len(ids) == len(set(ids))
    for q in test.questions:
        assert q.correct_answer in q.options
        assert q.question_text
        assert q.solution.steps


def test_questions_match_source_file_verbatim(bank):
    source = {}
    for line in AGENT_READY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            source[record["question_id"]] = record

    test = generate_test(
        bank,
        TestRequest(seed=7, selections=[Selection(count=8, chapter="Percentage, Profit & Loss")]),
    )
    for q in test.questions:
        original = source[q.question_id]
        assert q.question_text == original["question_text"]
        assert q.options == original["options"]
        assert q.correct_answer == original["correct_answer"]


def test_practice_progressive_with_knowledge(bank):
    practice = generate_practice(
        bank, PracticeRequest(topic="Percentage", count=6, mode="progressive", seed=9)
    )
    again = PracticeSet.model_validate_json(practice.model_dump_json())
    assert again.practice_id == practice.practice_id
    assert practice.coverage.total == 6
    ranks = ["easy", "medium", "hard"]
    order = [ranks.index(q.classification.difficulty) for q in practice.questions]
    assert order == sorted(order)
    assert practice.topic_knowledge.get("Percentage", {}).get("formulas")


def test_contract_mismatch_is_loud_not_repaired(tmp_path, bank):
    from qme.testgen import ContractError

    bad = tmp_path / "bad_blueprint.json"
    payload = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    payload["test_generation_contract"]["output_fields"] = ["test_id"]
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ContractError, match="output_fields missing"):
        load_bank(bad)
