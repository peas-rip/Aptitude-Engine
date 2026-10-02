"""Practice sets: ordering modes, knowledge attach, shortages."""

import random

import pytest

from qme.testgen import SelectionError, generate_practice, load_bank
from qme.testgen.schemas import DIFFICULTY_RANK, PracticeRequest
from tests.testgen_fixtures import write_bank


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


def test_shortage_when_pool_smaller_than_count(bank):
    practice = generate_practice(
        bank, PracticeRequest(count=10, difficulty="hard", seed=1)
    )
    assert practice.coverage.total == 1
    assert practice.shortages[0].shortfall == 9


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
