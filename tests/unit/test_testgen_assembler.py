"""Test assembly: coverage, timing, answer key, dedupe, contract conformance."""

import pytest

from qme.testgen import SelectionError, generate_test, load_bank
from qme.testgen.schemas import GeneratedTest, Selection, TestRequest
from tests.testgen_fixtures import sample_request, sample_selection, write_bank

OUTPUT_FIELDS = ["test_id", "questions", "answer_key", "coverage", "timing"]


@pytest.fixture()
def bank(tmp_path):
    return load_bank(write_bank(tmp_path))


def test_output_fields_all_present(bank):
    test = generate_test(bank, sample_request())
    payload = test.model_dump()
    for field in OUTPUT_FIELDS:
        assert field in payload


def test_coverage_totals(bank):
    test = generate_test(
        bank,
        sample_request(selections=[sample_selection(count=10)]),
    )
    assert test.coverage.total == 6
    assert sum(test.coverage.by_chapter.values()) == 6
    assert sum(test.coverage.by_difficulty.values()) == 6
    assert test.coverage.by_difficulty == {"easy": 3, "medium": 2, "hard": 1}


def test_timing_math(bank):
    test = generate_test(bank, sample_request())
    assert test.timing.estimated_total_sec == 60
    assert test.timing.avg_per_question_sec == 30.0
    assert test.timing.min_sec == 30
    assert test.timing.max_sec == 30


def test_answer_key_alignment_and_solutions_toggle(bank):
    test = generate_test(bank, sample_request())
    assert [k.question_id for k in test.answer_key] == [
        q.question_id for q in test.questions
    ]
    assert all(k.solution_steps for k in test.answer_key)

    bare = generate_test(
        bank, sample_request(include_solutions=False)
    )
    assert all(not k.solution_steps for k in bare.answer_key)


def test_questions_never_altered(bank):
    test = generate_test(bank, sample_request())
    for q in test.questions:
        assert q.question_text == f"Question {q.question_id}?"
        assert q.options == {"A": "1", "B": "2", "C": "3", "D": "4"}


def test_overlapping_selections_dedupe(bank):
    request = sample_request(
        selections=[
            sample_selection(count=4, chapter="Percentage"),
            sample_selection(count=10, chapter="Percentage"),
        ]
    )
    test = generate_test(bank, request)
    ids = [q.question_id for q in test.questions]
    assert len(ids) == len(set(ids))
    assert test.notes["overlaps_dropped"] == 4
    assert test.shortages[0].provided == 0


def test_shortages_propagate(bank):
    request = sample_request(
        selections=[sample_selection(count=50, difficulty="hard")]
    )
    test = generate_test(bank, request)
    assert len(test.shortages) == 1
    assert test.shortages[0].shortfall == 49


def test_selection_rules_echoed(bank):
    test = generate_test(bank, sample_request())
    assert test.selection_rules_applied == bank.blueprint.test_generation_contract.selection_rules
    assert test.contract_source["question_bank"] == "bank.jsonl"


def test_explicit_and_generated_test_ids(bank):
    explicit = generate_test(bank, sample_request(test_id="T-CUSTOM"))
    assert explicit.test_id == "T-CUSTOM"
    generated = generate_test(bank, sample_request())
    assert generated.test_id.startswith("T-")


def test_unsatisfiable_selection_raises(bank):
    with pytest.raises(SelectionError):
        generate_test(
            bank,
            TestRequest(selections=[Selection(count=3, chapter="Nope")]),
        )


def test_roundtrip_validation(bank):
    test = generate_test(bank, sample_request())
    again = GeneratedTest.model_validate_json(test.model_dump_json())
    assert again.test_id == test.test_id
