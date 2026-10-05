"""Friendly-shape rule table: discrimination, rules, feasibility, compile."""

import pytest
from pydantic import ValidationError

from qme.testgen import SelectionError, load_bank
from qme.testgen.schemas import TestRequest, TestSpec
from qme.testgen.spec import compile_spec, parse_test_request
from tests.testgen_fixtures import big_questions, default_questions, write_bank


@pytest.fixture()
def bank(tmp_path):
    return load_bank(write_bank(tmp_path, big_questions()))


def compile_dict(bank, body: dict):
    parsed = parse_test_request(body)
    assert isinstance(parsed, TestSpec)
    return compile_spec(bank, parsed)


def expect_rule(bank, body: dict, rule: str) -> SelectionError:
    with pytest.raises(SelectionError) as excinfo:
        compile_dict(bank, body)
    rules = [v["rule"] for v in excinfo.value.details["violations"]]
    assert rule in rules, f"expected {rule!r} in {rules!r}"
    return excinfo.value


# --- shape discrimination -----------------------------------------------------------


def test_legacy_shape_parses_to_test_request():
    parsed = parse_test_request({"selections": [{"count": 2}]})
    assert isinstance(parsed, TestRequest)


def test_friendly_shape_parses_to_test_spec():
    parsed = parse_test_request(
        {"count": 10, "difficulty": {"mode": "single", "value": "easy"}}
    )
    assert isinstance(parsed, TestSpec)


def test_both_shapes_rejected():
    with pytest.raises(SelectionError) as excinfo:
        parse_test_request(
            {"selections": [{"count": 2}], "count": 10, "difficulty": {"mode": "single", "value": "easy"}}
        )
    assert excinfo.value.details["violations"][0]["rule"] == "single_shape"


def test_friendly_missing_difficulty_is_schema_error():
    with pytest.raises(ValidationError):
        parse_test_request({"count": 10})


# --- count rules -----------------------------------------------------------------


def test_count_multiple_of_five_rule(bank):
    expect_rule(
        bank,
        {"chapters": ["book.pdf › Percentage"], "difficulty": {"mode": "single", "value": "easy"}, "count": 12},
        "count_multiple_of_5",
    )


def test_count_minimum_ten_explicit_chapters(bank):
    error = expect_rule(
        bank,
        {"chapters": ["book.pdf › Percentage"], "difficulty": {"mode": "single", "value": "easy"}, "count": 5},
        "count_minimum",
    )
    assert ">= 10" in error.details["violations"][0]["expected"]


def test_count_minimum_thirty_all_chapters(bank):
    error = expect_rule(
        bank,
        {"difficulty": {"mode": "single", "value": "easy"}, "count": 10},
        "count_minimum",
    )
    assert ">= 30" in error.details["violations"][0]["expected"]


def test_all_chapters_count_30_single_easy_fails_feasibility(bank):
    # 30 >= 30 and 30 % 5 == 0 — the remaining failure is feasibility of
    # "single easy" (only 15 easy exist), proving rules run in order.
    error = expect_rule(
        bank,
        {"difficulty": {"mode": "single", "value": "easy"}, "count": 30},
        "feasibility",
    )
    assert error.details["available_by_difficulty"]["easy"] == 15


# --- difficulty composition -------------------------------------------------------


def test_single_mode_requires_value(bank):
    expect_rule(bank, {"count": 10, "difficulty": {"mode": "single"}}, "single_requires_value")


def test_mixed_mode_requires_counts(bank):
    expect_rule(bank, {"count": 10, "difficulty": {"mode": "mixed"}}, "mixed_requires_counts")


def test_mixed_counts_must_sum_to_count(bank):
    expect_rule(
        bank,
        {
            "count": 10,
            "difficulty": {"mode": "mixed", "counts": {"easy": 5, "medium": 4}},
        },
        "mixed_counts_sum",
    )


def test_mixed_unknown_difficulty_key(bank):
    expect_rule(
        bank,
        {"count": 10, "difficulty": {"mode": "mixed", "counts": {"ez": 10}}},
        "mixed_unknown_difficulty",
    )


def test_mixed_negative_count(bank):
    expect_rule(
        bank,
        {
            "count": 10,
            "difficulty": {"mode": "mixed", "counts": {"easy": -5, "medium": 15}},
        },
        "mixed_negative_count",
    )


# --- scope rules -----------------------------------------------------------------


def test_unknown_source_lists_available(bank):
    error = expect_rule(
        bank,
        {"sources": ["nope"], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
        "unknown_source",
    )
    assert error.details["available"]["sources"] == ["book.pdf"]


def test_empty_sources_rejected(bank):
    expect_rule(
        bank,
        {"sources": [], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
        "sources_not_empty",
    )


def test_empty_chapters_rejected(bank):
    expect_rule(
        bank,
        {"chapters": [], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
        "chapters_not_empty",
    )


def test_unknown_chapter_lists_available(bank):
    error = expect_rule(
        bank,
        {
            "chapters": ["book.pdf › Nonexistent"],
            "difficulty": {"mode": "single", "value": "easy"},
            "count": 10,
        },
        "unknown_chapter",
    )
    assert "available" in error.details


def test_chapter_outside_selected_sources(bank):
    # second source holding only Time & Work
    questions = big_questions()
    for q in questions:
        if q["classification"]["chapter"] == "Time & Work":
            q["source"]["name"] = "book2.pdf"
    two_source = load_bank(write_bank(bank.blueprint_path.parent, questions))
    expect_rule(
        two_source,
        {
            "sources": ["book.pdf"],
            "chapters": ["book2.pdf › Time & Work"],
            "difficulty": {"mode": "single", "value": "hard"},
            "count": 10,
        },
        "chapter_outside_sources",
    )


# --- feasibility ------------------------------------------------------------------


def test_infeasible_single_difficulty_reports_availability(bank):
    error = expect_rule(
        bank,
        {
            "chapters": ["book.pdf › Percentage", "book.pdf › Time & Work"],
            "difficulty": {"mode": "single", "value": "hard"},
            "count": 10,
        },
        "feasibility",
    )
    available = error.details["available_by_difficulty"]
    assert available == {"easy": 15, "medium": 10, "hard": 5}


def test_infeasible_mixed_reports_short_bucket(bank):
    error = expect_rule(
        bank,
        {
            "chapters": ["book.pdf › Percentage", "book.pdf › Time & Work"],
            "count": 20,
            "difficulty": {"mode": "mixed", "counts": {"easy": 14, "hard": 6, "medium": 0}},
        },
        "feasibility",
    )
    short = [v for v in error.details["violations"] if v["actual"] == "hard"]
    assert short and short[0]["available"] == 5


# --- compile ----------------------------------------------------------------------


def test_compile_single_difficulty(bank):
    request = compile_dict(
        bank,
        {
            "seed": 7,
            "title": "T",
            "chapters": ["book.pdf › Percentage", "book.pdf › Time & Work"],
            "difficulty": {"mode": "single", "value": "easy"},
            "count": 10,
        },
    )
    assert request.seed == 7 and request.title == "T"
    assert len(request.selections) == 1
    selection = request.selections[0]
    assert selection.count == 10 and selection.difficulty == "easy"
    assert sorted(selection.chapters) == ["book.pdf › Percentage", "book.pdf › Time & Work"]


def test_compile_mixed_difficulty_counts(bank):
    request = compile_dict(
        bank,
        {
            "chapters": ["book.pdf › Percentage", "book.pdf › Time & Work"],
            "count": 20,
            "difficulty": {"mode": "mixed", "counts": {"hard": 5, "easy": 10, "medium": 5}},
        },
    )
    assert [(s.difficulty, s.count) for s in request.selections] == [
        ("easy", 10),
        ("medium", 5),
        ("hard", 5),
    ]


def test_compile_chapter_scope_limits_pool(bank):
    request = compile_dict(
        bank,
        {
            "chapters": ["book.pdf › Percentage"],
            "difficulty": {"mode": "single", "value": "easy"},
            "count": 10,
        },
    )
    assert request.selections[0].chapters == ["book.pdf › Percentage"]


def test_compile_all_chapters_minimum(bank):
    request = compile_dict(
        bank,
        {
            "count": 30,
            "difficulty": {"mode": "mixed", "counts": {"easy": 15, "medium": 10, "hard": 5}},
        },
    )
    assert sum(s.count for s in request.selections) == 30


def test_compile_legacy_fields_pass_through(bank):
    request = compile_dict(
        bank,
        {
            "test_id": "custom",
            "seed": 99,
            "chapters": ["book.pdf › Percentage", "book.pdf › Time & Work"],
            "difficulty": {"mode": "single", "value": "easy"},
            "count": 10,
        },
    )
    assert request.test_id == "custom" and request.seed == 99
    assert request.include_solutions is True


def test_compile_ambiguous_unqualified_chapter(tmp_path):
    questions = default_questions()
    questions[1]["source"]["name"] = "book2.pdf"  # q2: Percentage from book2
    bank = load_bank(write_bank(tmp_path, questions))
    error = expect_rule(
        bank,
        {"chapters": ["Percentage"], "difficulty": {"mode": "single", "value": "easy"}, "count": 10},
        "unknown_chapter",
    )
    assert "ambiguous" in str(error.details["violations"][0].get("detail", "")).lower()
