"""Practice-set assembly: one filtered pool, ordered progressive or mixed.

Paginated (API_CONTRACTS 1.7): the whole filtered pool is ordered once from
the request ``seed`` and sliced into disjoint pages — same seed + same
filters + ``page``/``count`` always reproduce the same page, and the next
page never repeats a question. Pool size is reported via ``pagination``;
practice never reports shortages.
"""

import math
import random
from collections import Counter
from datetime import UTC, datetime

from qme.testgen.bank import Bank
from qme.testgen.errors import SelectionError
from qme.testgen.schemas import (
    CHAPTER_SEP,
    DIFFICULTY_RANK,
    BankQuestion,
    Coverage,
    Pagination,
    PracticeRequest,
    PracticeSet,
    Selection,
    Timing,
    qualify_chapter,
)


def _coverage(questions: list[BankQuestion]) -> Coverage:
    return Coverage(
        total=len(questions),
        by_chapter=dict(
            Counter(
                qualify_chapter(q.source.name, q.classification.chapter)
                for q in questions
            )
        ),
        by_topic=dict(Counter(q.classification.topic for q in questions)),
        by_difficulty=dict(Counter(q.classification.difficulty for q in questions)),
        by_source=dict(Counter(q.source.name for q in questions)),
    )


def _timing(questions: list[BankQuestion]) -> Timing:
    times = [q.agent_metadata.estimated_time_seconds for q in questions] or [0]
    return Timing(
        estimated_total_sec=sum(times),
        avg_per_question_sec=round(sum(times) / len(times), 1),
        min_sec=min(times),
        max_sec=max(times),
    )


def _resolve_scope(
    bank: Bank, source: str | None, chapter_key: str | None
) -> tuple[str | None, str | None]:
    """Resolve ``source`` + optional (qualified) chapter key to filters."""
    chapter: str | None = None
    if chapter_key is not None:
        chapter = bank.resolve_chapter(chapter_key)
        if CHAPTER_SEP in chapter_key:
            chapter_source = chapter_key.partition(CHAPTER_SEP)[0]
            if source is not None and source != chapter_source:
                raise SelectionError(
                    f"chapter {chapter_key!r} belongs to source {chapter_source!r}, "
                    f"which conflicts with source filter {source!r}",
                    {"sources": [source, chapter_source]},
                )
            source = chapter_source
    if source is not None and source not in bank.source_names:
        raise SelectionError(
            f"unknown source {source!r}",
            {"available": {"sources": bank.source_names}},
        )
    return source, chapter


def generate_practice(bank: Bank, request: PracticeRequest) -> PracticeSet:
    """Build one deterministic page of a single source/chapter/pool scope."""
    source, chapter = _resolve_scope(bank, request.source, request.chapter)

    seed = request.seed if request.seed is not None else random.randrange(10**9)
    rng = random.Random(seed)

    pool = [
        q
        for q in bank.questions
        if (source is None or q.source.name == source)
        and (chapter is None or q.classification.chapter == chapter)
        and (request.topic is None or q.classification.topic == request.topic)
        and (
            request.difficulty is None
            or q.classification.difficulty == request.difficulty
        )
    ]
    selection = Selection(
        count=request.count,
        source=source,
        chapter=chapter,
        topic=request.topic,
        difficulty=request.difficulty,
    )
    if not pool:
        raise SelectionError(
            f"practice request matches no questions: {selection.filter_summary()!r}",
            {"filters": selection.filter_summary()},
        )

    if request.mode == "progressive":
        pool.sort(
            key=lambda q: (DIFFICULTY_RANK[q.classification.difficulty], rng.random())
        )
    else:
        rng.shuffle(pool)

    total = len(pool)
    total_pages = math.ceil(total / request.count)
    if request.page > total_pages:
        raise SelectionError(
            f"page {request.page} exceeds the pool (1..{total_pages})",
            {"page": request.page, "total_pages": total_pages, "total": total},
        )
    offset = (request.page - 1) * request.count
    picked = pool[offset : offset + request.count]

    topic_knowledge: dict[str, dict] = {}
    chapter_summaries: set[str] = set()
    chapters: set[str] = set()
    for q in picked:
        page_chapter = q.classification.chapter
        topic = q.classification.topic
        chapters.add(page_chapter)
        if not request.include_knowledge:
            continue
        entry = bank.knowledge_for(page_chapter, topic)
        if entry is not None:
            topic_knowledge[topic] = {
                "formulas": entry.formulas,
                "short_tricks": entry.short_tricks,
            }
            chapter_entry = bank.knowledge.chapters.get(page_chapter)
            if chapter_entry is not None:
                chapter_summaries.update(chapter_entry.chapter_formula_summary)

    practice_id = request.practice_id or f"P-{datetime.now(UTC):%Y%m%d-%H%M%S}-{len(picked)}"
    return PracticeSet(
        practice_id=practice_id,
        title=request.title,
        seed=seed,
        generated_at=datetime.now(UTC).isoformat(),
        mode=request.mode,
        filters_applied=selection.filter_summary(),
        questions=picked,
        coverage=_coverage(picked),
        timing=_timing(picked),
        pagination=Pagination(
            page=request.page,
            count=request.count,
            total=total,
            total_pages=total_pages,
            has_more=request.page < total_pages,
        ),
        shortages=[],
        topic_knowledge=topic_knowledge,
        chapter_formula_summary=sorted(chapter_summaries) if len(chapters) == 1 else [],
    )
