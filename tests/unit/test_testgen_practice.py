"""Practice sets: ordering modes, knowledge attach, pagination, sources."""

import random

import pytest

from qme.testgen import SelectionError, generate_practice, load_bank
from qme.testgen.schemas import DIFFICULTY_RANK, PracticeRequest
from tests.testgen_fixtures import big_questions, write_bank


@pytest.fixture()
def bank(tmp_path):
    return load_bank(write_bank(tmp_path))


def test_progressive_orders_easy_to_hard(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=6, mode="progressive", seed=3)
    )
    ranks = [DIFFICULTY_RANK[q.classification.difficulty] for q in practice.questions]
    assert ranks == sorted(ranks)
    assert len(practice.questions) == 6


def test_mixed_seeded_order_is_reproducible(bank):
    kwargs = dict(count=6, mode="mixed", seed=11)
    first = generate_practice(bank, PracticeRequest(**kwargs))
    second = generate_practice(bank, PracticeRequest(**kwargs))
    assert [q.question_id for q in first.questions] == [
        q.question_id for q in second.questions
    ]


def test_filters_scope_the_pool(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=10, chapter="Time & Work", seed=1)
    )
    assert {q.classification.chapter for q in practice.questions} == {"Time & Work"}
    assert len(practice.questions) == 2


def test_partial_page_when_pool_smaller_than_count(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=10, difficulty="hard", seed=1)
    )
    assert practice.coverage.total == 1
    assert practice.shortages == []
    assert practice.pagination is not None
    assert practice.pagination.total == 1
    assert practice.pagination.total_pages == 1
    assert practice.pagination.has_more is False


def test_unknown_topic_raises(bank):
    with pytest.raises(SelectionError, match="matches no questions"):
        generate_practice(bank, PracticeRequest(topic="Missing Topic"))


def test_knowledge_attached_per_topic(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=4, chapter="Percentage", seed=5)
    )
    assert practice.topic_knowledge
    for entry in practice.topic_knowledge.values():
        assert entry["formulas"]
        assert entry["short_tricks"]
    assert practice.chapter_formula_summary


def test_include_knowledge_false_omits_bank_entries(bank):
    practice = generate_practice(
        bank,
        PracticeRequest(count=4, chapter="Percentage", seed=5, include_knowledge=False),
    )
    assert practice.topic_knowledge == {}
    assert practice.chapter_formula_summary == []


def test_chapter_formula_summary_only_single_chapter(bank):
    practice = generate_practice(bank, PracticeRequest(count=6, seed=1))
    assert practice.chapter_formula_summary == []

    single = generate_practice(
        bank, PracticeRequest(count=4, chapter="Percentage", seed=1)
    )
    assert single.chapter_formula_summary == ["Percentage summary"]


def test_default_mode_is_progressive(bank):
    practice = generate_practice(bank, PracticeRequest(count=3, seed=2))
    assert practice.mode == "progressive"
    ranks = [DIFFICULTY_RANK[q.classification.difficulty] for q in practice.questions]
    assert ranks == sorted(ranks)


def test_different_seeds_can_sample_differently(bank):
    runs = {
        tuple(
            q.question_id
            for q in generate_practice(
                bank, PracticeRequest(count=4, seed=s, mode="mixed")
            ).questions
        )
        for s in range(20)
    }
    assert len(runs) > 1


def test_rng_independence_from_global_state(bank):
    random.seed(999)
    first = generate_practice(bank, PracticeRequest(count=4, seed=8, mode="mixed"))
    random.seed(1)
    second = generate_practice(bank, PracticeRequest(count=4, seed=8, mode="mixed"))
    assert [q.question_id for q in first.questions] == [
        q.question_id for q in second.questions
    ]


# --- pagination -------------------------------------------------------------------


def test_pages_are_disjoint_and_cover_the_pool(bank):
    seen: list[str] = []
    for page in range(1, 4):
        practice = generate_practice(
            bank, PracticeRequest(count=2, page=page, seed=4, mode="mixed")
        )
        assert practice.pagination.total == 6
        assert practice.pagination.total_pages == 3
        assert practice.pagination.page == page
        seen.extend(q.question_id for q in practice.questions)
    assert len(seen) == len(set(seen)) == 6
    last = generate_practice(bank, PracticeRequest(count=2, page=3, seed=4, mode="mixed"))
    assert last.pagination.has_more is False


def test_page_beyond_pool_raises_with_total_pages(bank):
    with pytest.raises(SelectionError) as excinfo:
        generate_practice(bank, PracticeRequest(count=2, page=4, seed=4))
    assert excinfo.value.details["total_pages"] == 3
    assert excinfo.value.details["page"] == 4


def test_seed_generated_and_echoed_when_absent(bank):
    first = generate_practice(bank, PracticeRequest(count=2, seed=None))
    second = generate_practice(bank, PracticeRequest(count=2, seed=first.seed))
    assert isinstance(first.seed, int)
    assert [q.question_id for q in first.questions] == [
        q.question_id for q in second.questions
    ]


def test_changing_seed_reshuffles_order(bank):
    a = generate_practice(bank, PracticeRequest(count=6, mode="mixed", seed=1))
    b = generate_practice(bank, PracticeRequest(count=6, mode="mixed", seed=2))
    assert [q.question_id for q in a.questions] != [q.question_id for q in b.questions]


def test_count_larger_than_pool_returns_partial_page_without_shortage(bank):
    practice = generate_practice(bank, PracticeRequest(count=50, seed=1))
    assert practice.coverage.total == 6
    assert practice.shortages == []
    assert practice.pagination.total == 6
    assert practice.pagination.has_more is False


# --- sources ----------------------------------------------------------------------


def test_source_filters_pool(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=10, source="book.pdf", seed=1)
    )
    assert {q.source.name for q in practice.questions} == {"book.pdf"}
    assert practice.filters_applied["source"] == "book.pdf"


def test_unknown_source_raises_with_available(bank):
    with pytest.raises(SelectionError) as excinfo:
        generate_practice(bank, PracticeRequest(source="nope"))
    assert excinfo.value.details["available"]["sources"] == ["book.pdf"]


def test_qualified_chapter_sets_source_scope(bank):
    practice = generate_practice(
        bank,
        PracticeRequest(count=10, chapter="book.pdf › Time & Work", seed=1),
    )
    assert {q.classification.chapter for q in practice.questions} == {"Time & Work"}
    assert practice.filters_applied["source"] == "book.pdf"
    assert practice.filters_applied["chapter"] == "Time & Work"


def test_conflicting_chapter_source_and_source_filter(bank):
    questions = big_questions()
    for q in questions:
        if q["classification"]["chapter"] == "Time & Work":
            q["source"]["name"] = "book2.pdf"
    two_source = load_bank(write_bank(bank.blueprint_path.parent, questions))
    with pytest.raises(SelectionError, match="conflicts with source filter"):
        generate_practice(
            two_source,
            PracticeRequest(chapter="book2.pdf › Time & Work", source="book.pdf"),
        )
