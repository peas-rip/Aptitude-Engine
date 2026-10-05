"""Markdown rendering for tests and practice sets."""

from qme.testgen import generate_practice, generate_test, load_bank
from qme.testgen import render as renderers
from qme.testgen.schemas import PracticeRequest, Selection, TestRequest
from tests.testgen_fixtures import write_bank


def test_test_markdown_contains_contract_sections(tmp_path):
    bank = load_bank(write_bank(tmp_path))
    test = generate_test(
        bank,
        TestRequest(title="Unit Test Paper", seed=1, selections=[Selection(count=3)]),
    )
    md = renderers.test_to_markdown(test)
    assert "# Unit Test Paper" in md
    assert f"**test_id:** {test.test_id}" in md
    assert "## Questions" in md
    assert "## Answer key" in md
    assert "**A** 1" in md
    assert "step one" in md


def test_test_markdown_reports_shortages(tmp_path):
    bank = load_bank(write_bank(tmp_path))
    test = generate_test(
        bank,
        TestRequest(
            seed=1, selections=[Selection(count=50, difficulty="hard")]
        ),
    )
    md = renderers.test_to_markdown(test)
    assert "## Shortages" in md
    assert "short 49" in md


def test_practice_markdown_contains_knowledge_and_answers(tmp_path):
    bank = load_bank(write_bank(tmp_path))
    practice = generate_practice(bank, PracticeRequest(count=3, seed=4))
    md = renderers.practice_to_markdown(practice)
    assert "# " in md
    assert "## Formulas & tricks" in md
    assert "formula" in md
    assert "trick" in md
    assert "<details><summary>Answer: A" in md
    assert "</details>" in md


def test_practice_markdown_shows_pagination(tmp_path):
    bank = load_bank(write_bank(tmp_path))
    practice = generate_practice(
        bank, PracticeRequest(count=20, difficulty="hard", seed=1)
    )
    md = renderers.practice_to_markdown(practice)
    assert "**page:** 1/1 (pool 1, page size 20, has_more=False)" in md
    assert "**seed:** 1" in md
    assert "requested" not in md
