"""Selection: filters, shortage reporting, seed determinism."""

import random

import pytest

from qme.testgen import SelectionError, load_bank
from qme.testgen.selector import select
from tests.testgen_fixtures import sample_selection, write_bank


@pytest.fixture()
def bank(tmp_path):
    return load_bank(write_bank(tmp_path))


def test_filters_by_difficulty(bank):
    result = select(bank, sample_selection(count=1, difficulty="hard"), random.Random(1))
    assert [q.question_id for q in result.picked] == ["q5"]
    assert result.shortage is None


def test_filters_by_chapter_and_topic(bank):
    result = select(
        bank,
        sample_selection(count=5, chapter="Time & Work", topic="Work Rate"),
        random.Random(1),
    )
    assert {q.question_id for q in result.picked} == {"q5", "q6"}


def test_filters_by_question_type_and_page_range(bank):
    result = select(
        bank,
        sample_selection(count=5, question_type="numeric", page_min=15, page_max=25),
        random.Random(1),
    )
    assert [q.question_id for q in result.picked] == ["q4"]


def test_filters_by_skills_any_match(bank):
    result = select(
        bank, sample_selection(count=5, skills=["algebra"]), random.Random(1)
    )
    assert [q.question_id for q in result.picked] == ["q4"]


def test_unknown_chapter_lists_available(bank):
    with pytest.raises(SelectionError, match="not in bank"):
        select(bank, sample_selection(count=2, chapter="Nonexistent"), random.Random(1))


def test_unknown_topic_lists_available(bank):
    with pytest.raises(SelectionError, match="available"):
        select(
            bank,
            sample_selection(count=2, topic="Missing Topic"),
            random.Random(1),
        )


def test_no_match_reports_filters(bank):
    with pytest.raises(SelectionError, match="no question matches"):
        select(
            bank,
            sample_selection(count=2, chapter="Time & Work", difficulty="medium"),
            random.Random(1),
        )


def test_shortage_record(bank):
    result = select(
        bank, sample_selection(count=10, difficulty="hard"), random.Random(1)
    )
    assert result.shortage is not None
    assert result.shortage.requested == 10
    assert result.shortage.provided == 1
    assert result.shortage.shortfall == 9
    assert result.shortage.filters == {"difficulty": "hard"}


def test_seed_determinism(bank):
    sel = sample_selection(count=3)
    first = [q.question_id for q in select(bank, sel, random.Random(7)).picked]
    second = [q.question_id for q in select(bank, sel, random.Random(7)).picked]
    assert first == second
    assert len(first) == 3


def test_different_seed_can_differ(bank):
    sel = sample_selection(count=4)
    runs = {
        tuple(q.question_id for q in select(bank, sel, random.Random(s)).picked)
        for s in range(20)
    }
    assert len(runs) > 1


def test_exclude_counts_overlap_and_skips(bank):
    result = select(
        bank,
        sample_selection(count=10),
        random.Random(1),
        exclude={"q1", "q2", "q3", "q4"},
    )
    assert {q.question_id for q in result.picked} == {"q5", "q6"}
    assert result.overlap_excluded == 4


def test_all_matching_excluded_reports_shortage_not_error(bank):
    result = select(
        bank,
        sample_selection(count=4, chapter="Percentage"),
        random.Random(1),
        exclude={"q1", "q2", "q3", "q4"},
    )
    assert result.picked == []
    assert result.overlap_excluded == 4
    assert result.shortage is not None
    assert result.shortage.provided == 0
