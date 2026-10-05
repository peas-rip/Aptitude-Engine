"""Contract validation for the three upstream bank files."""


import pytest

from qme.testgen import ContractError, SelectionError, load_bank
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


def test_missing_knowledge_topic_reports_gap(tmp_path):
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
    bank = load_bank(path)
    assert bank.knowledge_missing == ["Percentage"]
    coverage = bank.knowledge_coverage()
    assert coverage.missing_chapters == ["Percentage"]
    assert coverage.covered_chapters == ["Time & Work"]


def test_missing_knowledge_chapter_reports_gap(tmp_path):
    knowledge = {
        "schema_version": "1.0",
        "provenance": {},
        "chapters": {},
        "web_sources": [],
    }
    path = write_bank(tmp_path, knowledge_override=knowledge)
    bank = load_bank(path)
    assert bank.knowledge_missing == ["Percentage", "Time & Work"]
    assert bank.knowledge_coverage().covered_chapters == []


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


# --- multi-source adoption ------------------------------------------------------


def _two_source_bank(tmp_path):
    """Percentage split across book.pdf (q1, q3..) and book2.pdf (q2)."""
    questions = default_questions()
    questions[1]["source"]["name"] = "book2.pdf"  # q2: Percentage from book2
    questions[4]["source"]["name"] = "book2.pdf"  # q5: Time & Work from book2
    return load_bank(write_bank(tmp_path, questions))


def test_source_names_and_qualified_chapters(tmp_path):
    bank = _two_source_bank(tmp_path)
    assert bank.source_names == ["book.pdf", "book2.pdf"]
    assert bank.qualified_chapters == [
        "book.pdf › Percentage",
        "book.pdf › Time & Work",
        "book2.pdf › Percentage",
        "book2.pdf › Time & Work",
    ]


def test_resolve_qualified_chapter(tmp_path):
    bank = _two_source_bank(tmp_path)
    assert bank.resolve_chapter("book2.pdf › Percentage") == "Percentage"
    assert bank.resolve_chapter("book.pdf › Percentage") == "Percentage"


def test_resolve_unqualified_ambiguous_raises(tmp_path):
    bank = _two_source_bank(tmp_path)
    with pytest.raises(SelectionError) as excinfo:
        bank.resolve_chapter("Percentage")
    assert excinfo.value.details["ambiguous"] == [
        "book.pdf › Percentage",
        "book2.pdf › Percentage",
    ]


def test_resolve_unknown_source_in_key_raises(tmp_path):
    bank = _two_source_bank(tmp_path)
    with pytest.raises(SelectionError, match="unknown source"):
        bank.resolve_chapter("ghost.pdf › Percentage")


def test_resolve_unknown_chapter_raises(tmp_path):
    bank = _two_source_bank(tmp_path)
    with pytest.raises(SelectionError, match="not found in source"):
        bank.resolve_chapter("book.pdf › Ghost")


def test_chapter_label_strips_source_part(tmp_path):
    bank = _two_source_bank(tmp_path)
    assert bank.chapter_label("book2.pdf › Percentage") == "Percentage"
    assert bank.chapter_label("Percentage") == "Percentage"


def test_source_infos_group_by_source(tmp_path):
    bank = _two_source_bank(tmp_path)
    infos = bank.source_infos()
    assert [i.name for i in infos] == ["book.pdf", "book2.pdf"]
    by_name = {i.name: i for i in infos}
    assert by_name["book2.pdf"].question_count == 2
    keys = {c.key for c in by_name["book.pdf"].chapters}
    assert keys == {"book.pdf › Percentage", "book.pdf › Time & Work"}
    percentage = next(c for c in by_name["book.pdf"].chapters if c.label == "Percentage")
    assert percentage.difficulty_counts == {"easy": 1, "medium": 2}


def test_duplicate_ids_name_sources_and_uniqueness_rule(tmp_path):
    questions = default_questions()
    questions[1]["question_id"] = questions[0]["question_id"]  # same id, 2 sources
    questions[1]["source"]["name"] = "book2.pdf"
    path = write_bank(tmp_path, questions, duplicate_ids=False)
    with pytest.raises(ContractError) as excinfo:
        load_bank(path)
    joined = str(excinfo.value)
    assert "book.pdf" in joined and "book2.pdf" in joined
    assert "globally unique" in joined
    assert "tcs-12" in joined
