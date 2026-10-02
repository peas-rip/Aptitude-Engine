"""Practice-set assembly: one filtered pool, ordered progressive or mixed."""

import random
from collections import Counter
from datetime import UTC, datetime

from qme.testgen.bank import Bank
from qme.testgen.errors import SelectionError
from qme.testgen.schemas import (
    DIFFICULTY_RANK,
    BankQuestion,
    Coverage,
    PracticeRequest,
    PracticeSet,
    Selection,
    Shortage,
    Timing,
)


def _coverage(questions: list[BankQuestion]) -> Coverage:
    return Coverage(
        total=len(questions),
        by_chapter=dict(Counter(q.classification.chapter for q in questions)),
        by_topic=dict(Counter(q.classification.topic for q in questions)),
        by_difficulty=dict(Counter(q.classification.difficulty for q in questions)),
    )


def _timing(questions: list[BankQuestion]) -> Timing:
    times = [q.agent_metadata.estimated_time_seconds for q in questions] or [0]
    return Timing(
        estimated_total_sec=sum(times),
        avg_per_question_sec=round(sum(times) / len(times), 1),
        min_sec=min(times),
        max_sec=max(times),
    )


def generate_practice(bank: Bank, request: PracticeRequest) -> PracticeSet:
    """Build a practice set from a single topic/chapter/difficulty scope."""
    selection = Selection(
        count=request.count,
        chapter=request.chapter,
        topic=request.topic,
        difficulty=request.difficulty,
    )
    rng = random.Random(request.seed)

    candidates = [
        q
        for q in bank.questions
        if (request.chapter is None or q.classification.chapter == request.chapter)
        and (request.topic is None or q.classification.topic == request.topic)
        and (request.difficulty is None or q.classification.difficulty == request.difficulty)
    ]
    if not candidates:
        raise SelectionError(
            f"practice request matches no questions: {selection.filter_summary()!r}",
            {"filters": selection.filter_summary()},
        )

    if len(candidates) > request.count:
        picked_ids = set(rng.sample([q.question_id for q in candidates], request.count))
        picked = [q for q in candidates if q.question_id in picked_ids]
    else:
        picked = candidates

    shortage = None
    if len(picked) < request.count:
        shortage = Shortage(
            selection_index=0,
            requested=request.count,
            provided=len(picked),
            shortfall=request.count - len(picked),
            filters=selection.filter_summary(),
        )

    if request.mode == "progressive":
        picked.sort(key=lambda q: (DIFFICULTY_RANK[q.classification.difficulty], rng.random()))
    else:
        rng.shuffle(picked)

    topic_knowledge: dict[str, dict] = {}
    chapter_summaries: set[str] = set()
    chapters: set[str] = set()
    for q in picked:
        chapter = q.classification.chapter
        topic = q.classification.topic
        chapters.add(chapter)
        if not request.include_knowledge:
            continue
        entry = bank.knowledge_for(chapter, topic)
        if entry is not None:
            topic_knowledge[topic] = {
                "formulas": entry.formulas,
                "short_tricks": entry.short_tricks,
            }
            chapter_entry = bank.knowledge.chapters.get(chapter)
            if chapter_entry is not None:
                chapter_summaries.update(chapter_entry.chapter_formula_summary)

    practice_id = request.practice_id or f"P-{datetime.now(UTC):%Y%m%d-%H%M%S}-{len(picked)}"
    return PracticeSet(
        practice_id=practice_id,
        title=request.title,
        generated_at=datetime.now(UTC).isoformat(),
        mode=request.mode,
        filters_applied=selection.filter_summary(),
        questions=picked,
        coverage=_coverage(picked),
        timing=_timing(picked),
        shortages=[s for s in [shortage] if s is not None],
        topic_knowledge=topic_knowledge,
        chapter_formula_summary=sorted(chapter_summaries) if len(chapters) == 1 else [],
    )
