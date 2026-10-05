"""Test assembly: selections -> blueprint-conformant ``GeneratedTest``."""

import random
from collections import Counter
from datetime import UTC, datetime

from qme.testgen.bank import Bank
from qme.testgen.errors import SelectionError
from qme.testgen.schemas import (
    AnswerKeyEntry,
    BankQuestion,
    Coverage,
    GeneratedTest,
    TestRequest,
    Timing,
    qualify_chapter,
)
from qme.testgen.selector import select


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


def _answer_key(questions: list[BankQuestion], include_solutions: bool) -> list[AnswerKeyEntry]:
    return [
        AnswerKeyEntry(
            question_id=q.question_id,
            correct_answer=q.correct_answer,
            answer_text=q.answer_text,
            solution_steps=q.solution.steps if include_solutions else [],
        )
        for q in questions
    ]


def generate_test(bank: Bank, request: TestRequest) -> GeneratedTest:
    """Assemble a test from the request's selections (deterministic per seed)."""
    rng = random.Random(request.seed)
    chosen: list[BankQuestion] = []
    seen: set[str] = set()
    shortages = []
    overlaps_dropped = 0

    for index, selection in enumerate(request.selections):
        result = select(bank, selection, rng, selection_index=index, exclude=seen)
        if result.shortage is not None:
            shortages.append(result.shortage)
        overlaps_dropped += result.overlap_excluded
        for q in result.picked:
            seen.add(q.question_id)
            chosen.append(q)

    if not chosen:
        raise SelectionError("no questions matched any selection")

    test_id = request.test_id or f"T-{datetime.now(UTC):%Y%m%d-%H%M%S}-{len(chosen)}"
    contract = bank.blueprint.test_generation_contract
    return GeneratedTest(
        test_id=test_id,
        title=request.title,
        seed=request.seed,
        generated_at=datetime.now(UTC).isoformat(),
        contract_source={
            "blueprint": bank.blueprint_path.name,
            "schema_version": bank.blueprint.schema_version,
            "question_bank": bank.blueprint.question_bank,
            "knowledge_bank": bank.blueprint.knowledge_bank,
        },
        selections_applied=request.selections,
        selection_rules_applied=list(contract.selection_rules),
        questions=chosen,
        answer_key=_answer_key(chosen, request.include_solutions),
        coverage=_coverage(chosen),
        timing=_timing(chosen),
        shortages=shortages,
        notes={"overlaps_dropped": overlaps_dropped} if overlaps_dropped else {},
    )
