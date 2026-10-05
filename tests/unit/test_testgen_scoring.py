"""Submission scoring: pure answers -> TestResult."""

import pytest

from qme.testgen.errors import SubmissionError
from qme.testgen.schemas import BankQuestion
from qme.testgen.scoring import score_test
from tests.testgen_fixtures import make_question


def questions() -> list[BankQuestion]:
    return [
        BankQuestion.model_validate(make_question("q1", difficulty="easy")),
        BankQuestion.model_validate(
            make_question("q2", difficulty="medium", chapter="Time & Work", topic="Work Rate")
        ),
        BankQuestion.model_validate(
            make_question("q3", difficulty="hard", chapter="Time & Work", topic="Work Rate")
        ),
    ]


def test_perfect_score():
    result = score_test(questions(), {"q1": "A", "q2": "A", "q3": "A"}, "T-1")
    assert result.test_id == "T-1"
    assert result.score.correct == 3
    assert result.score.total == 3
    assert result.score.percent == 100.0
    assert all(line.is_correct for line in result.results)


def test_partial_score_and_percent():
    result = score_test(questions(), {"q1": "A", "q2": "B", "q3": "A"}, "T-2", elapsed_seconds=540)
    assert result.score.correct == 2
    assert result.score.percent == 66.7
    assert result.elapsed_seconds == 540
    assert result.results[1].your_answer == "B"
    assert result.results[1].is_correct is False


def test_unanswered_counts_incorrect():
    result = score_test(questions(), {"q1": "A"}, "T-3")
    assert result.score.correct == 1
    assert result.results[1].your_answer is None
    assert result.results[1].is_correct is False


def test_unknown_question_id_rejected():
    with pytest.raises(SubmissionError) as excinfo:
        score_test(questions(), {"ghost": "A"}, "T-4")
    assert excinfo.value.details["unknown_question_ids"] == ["ghost"]
    assert excinfo.value.details["invalid_option_keys"] == {}


def test_invalid_option_key_rejected():
    with pytest.raises(SubmissionError) as excinfo:
        score_test(questions(), {"q1": "Z"}, "T-5")
    assert excinfo.value.details["unknown_question_ids"] == []
    assert excinfo.value.details["invalid_option_keys"] == {"q1": "Z"}


def test_breakups_by_difficulty_chapter_source():
    result = score_test(questions(), {"q1": "A", "q2": "B", "q3": "B"}, "T-6")
    assert result.by_difficulty["easy"].correct == 1
    assert result.by_difficulty["easy"].total == 1
    assert result.by_difficulty["medium"].correct == 0
    assert result.by_difficulty["hard"].correct == 0
    assert result.by_chapter["book.pdf › Percentage"] == result.by_difficulty["easy"]
    assert result.by_source["book.pdf"].total == 3
    time_work = result.by_chapter["book.pdf › Time & Work"]
    assert time_work.total == 2 and time_work.correct == 0


def test_result_lines_carry_review_fields():
    result = score_test(questions(), {"q1": "B"}, "T-7")
    line = result.results[0]
    assert line.correct_answer == "A"
    assert line.answer_text == "1"
    assert line.solution_steps == ["step one", "step two"]
    assert line.chapter == "book.pdf › Percentage"
    assert line.source == "book.pdf"
    assert line.difficulty == "easy"


def test_scoring_is_deterministic():
    answers = {"q1": "A", "q2": "A", "q3": "B"}
    first = score_test(questions(), answers, "T-8", elapsed_seconds=10).model_dump()
    second = score_test(questions(), answers, "T-8", elapsed_seconds=10).model_dump()
    assert first == second
