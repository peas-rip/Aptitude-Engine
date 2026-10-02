"""Contract validation for the three upstream bank files."""


import pytest

from qme.testgen import ContractError, load_bank
from tests.testgen_fixtures import default_questions, write_bank


def test_load_bank_ok(tmp_path):
    bank = load_bank(write_bank(tmp_path))
    assert len(bank.questions) == 6
    assert bank.chapters == ["Percentage", "Time & Work"]
    assert set(bank.difficulties) == {"easy", "medium", "hard"}
    assert bank.bucket_counts[("Percentage", "Successive Percentages", "easy")] == 2
    assert bank.knowledge_for("Percentage", "Successive Percentages") is not None


def test_missing_blueprint_file(tmp_path):
    with pytest.raises(ContractError, match="blueprint not found"):
        load_bank(tmp_path / "nope.json")


def test_question_missing_required_field_reports_line(tmp_path):
    questions = default_questions()
    del questions[2]["correct_answer"]
    path = write_bank(tmp_path, questions)
    with pytest.raises(ContractError, match="line 3"):
        load_bank(path)


def test_wrong_required_filters_violates_contract(tmp_path):
    path = write_bank(
        tmp_path, contract_overrides={"required_filters": ["chapter"]}
    )
    with pytest.raises(ContractError, match="required_filters"):
        load_bank(path)


def test_missing_output_fields_violates_contract(tmp_path):
    path = write_bank(
        tmp_path, contract_overrides={"output_fields": ["test_id", "questions"]}
    )
    with pytest.raises(ContractError, match="output_fields missing"):
        load_bank(path)


def test_empty_selection_rules_violates_contract(tmp_path):
    path = write_bank(tmp_path, contract_overrides={"selection_rules": []})
    with pytest.raises(ContractError, match="selection_rules"):
        load_bank(path)


def test_bucket_count_mismatch_stops(tmp_path):
    buckets = {
        "Percentage": {"Successive Percentages": {"easy": 99}},
        "Time & Work": {"Work Rate": {"easy": 1, "hard": 1}},
    }
    path = write_bank(tmp_path, buckets_override=buckets)
    with pytest.raises(ContractError, match="blueprint says 99"):
        load_bank(path)


def test_bank_question_missing_from_buckets_stops(tmp_path):
    buckets = {"Percentage": {"Successive Percentages": {"easy": 2, "medium": 2}}}
    path = write_bank(tmp_path, buckets_override=buckets)
    with pytest.raises(ContractError, match="blueprint buckets omit"):
        load_bank(path)


def test_missing_knowledge_topic_stops(tmp_path):
    questions = default_questions()
    knowledge = {
        "schema_version": "1.0",
        "provenance": {},
        "chapters": {
            "Percentage": {
                "question_count": 4,
                "topics": {"Other Topic": {"question_count": 4}},
                "chapter_formula_summary": [],
            },
            "Time & Work": {
                "question_count": 2,
                "topics": {"Work Rate": {"question_count": 2}},
                "chapter_formula_summary": [],
            },
        },
        "web_sources": [],
    }
    path = write_bank(tmp_path, questions, knowledge_override=knowledge)
    with pytest.raises(ContractError, match="missing topic 'Successive Percentages'"):
        load_bank(path)


def test_missing_knowledge_chapter_stops(tmp_path):
    knowledge = {
        "schema_version": "1.0",
        "provenance": {},
        "chapters": {},
        "web_sources": [],
    }
    path = write_bank(tmp_path, knowledge_override=knowledge)
    with pytest.raises(ContractError, match="missing chapter"):
        load_bank(path)


def test_duplicate_question_ids_stop(tmp_path):
    path = write_bank(tmp_path, duplicate_ids=True)
    with pytest.raises(ContractError, match="duplicate"):
        load_bank(path)


def test_invalid_difficulty_stops(tmp_path):
    questions = default_questions()
    questions[0]["classification"]["difficulty"] = "brutal"
    path = write_bank(tmp_path, questions)
    with pytest.raises(ContractError, match="line 1"):
        load_bank(path)
