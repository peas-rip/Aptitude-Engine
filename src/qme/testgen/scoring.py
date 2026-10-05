"""Submission scoring: answers -> ``TestResult`` (pure, deterministic).

API_CONTRACTS 1.7 — ``POST /api/v1/tests/submit``. The test is regenerated
by the caller (deterministic per seed) and passed in as ``questions``;
scoring itself is a pure function so it stays unit-testable without a bank
or HTTP layer. Unknown question ids or option keys raise
:class:`~qme.testgen.errors.SubmissionError` (``422 ANSWER_MISMATCH``) —
answers are never silently coerced or dropped.
"""

from qme.testgen.errors import SubmissionError
from qme.testgen.schemas import (
    DIFFICULTY_RANK,
    BankQuestion,
    ResultLine,
    ScoreBreakup,
    TestResult,
    qualify_chapter,
)


def _breakup(pairs: list[tuple[str, bool]]) -> dict[str, ScoreBreakup]:
    totals: dict[str, list[int]] = {}
    for key, correct in pairs:
        entry = totals.setdefault(key, [0, 0])
        entry[1] += 1
        if correct:
            entry[0] += 1
    return {
        key: ScoreBreakup(
            correct=correct,
            total=total,
            percent=round(correct / total * 100, 1) if total else 0.0,
        )
        for key, (correct, total) in totals.items()
    }


def score_test(
    questions: list[BankQuestion],
    answers: dict[str, str],
    test_id: str,
    elapsed_seconds: int | None = None,
) -> TestResult:
    """Score ``answers`` (question_id -> option key) against ``questions``."""
    known = {q.question_id: q for q in questions}
    unknown_ids = sorted(set(answers) - set(known))
    invalid_keys = {
        qid: key
        for qid, key in answers.items()
        if qid in known and key not in known[qid].options
    }
    if unknown_ids or invalid_keys:
        raise SubmissionError(
            "answers do not match the regenerated test",
            {
                "unknown_question_ids": unknown_ids,
                "invalid_option_keys": invalid_keys,
            },
        )

    lines: list[ResultLine] = []
    for q in questions:
        given = answers.get(q.question_id)
        correct = given == q.correct_answer
        lines.append(
            ResultLine(
                question_id=q.question_id,
                your_answer=given,
                correct_answer=q.correct_answer,
                answer_text=q.answer_text,
                is_correct=correct,
                solution_steps=q.solution.steps,
                difficulty=q.classification.difficulty,
                chapter=qualify_chapter(q.source.name, q.classification.chapter),
                source=q.source.name,
            )
        )

    total = len(lines)
    correct_total = sum(1 for line in lines if line.is_correct)
    return TestResult(
        test_id=test_id,
        score=ScoreBreakup(
            correct=correct_total,
            total=total,
            percent=round(correct_total / total * 100, 1) if total else 0.0,
        ),
        by_difficulty=_breakup(
            [
                (line.difficulty, line.is_correct)
                for line in sorted(
                    lines, key=lambda ln: DIFFICULTY_RANK[ln.difficulty]
                )
            ]
        ),
        by_chapter=_breakup(
            sorted((line.chapter, line.is_correct) for line in lines)
        ),
        by_source=_breakup(sorted((line.source, line.is_correct) for line in lines)),
        elapsed_seconds=elapsed_seconds,
        results=lines,
    )
