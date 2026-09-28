"""Opt-in live difficulty evaluation: Pearson correlation vs expert ratings.

Not part of the default suite (rate-limited real API calls):

    pytest -m ai_eval tests/ai_evaluation

Requires the active provider's API key in ``.env`` (gemini by default).
M4 exit gate: correlation with expert scores >= 0.8 (FE-003 acceptance).
"""

import json
import time
from pathlib import Path
from statistics import correlation

import pytest

from qme.config.settings import get_settings
from qme.core.models import DifficultyInput, DifficultyResult
from qme.utils.difficulty_calc import rating_for

pytestmark = [
    pytest.mark.ai_eval,
    pytest.mark.asyncio,
    pytest.mark.slow,
]

GOLD_PATH = Path(__file__).resolve().parent / "gold_standard" / "difficulty.jsonl"

MIN_CORRELATION = 0.80


def _missing_key_reason() -> str:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    key = {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "custom": settings.custom_api_key,
    }.get(provider, "")
    return "" if key else f"no API key configured for provider {provider!r}"


def _gold() -> list[dict]:
    return [
        json.loads(line)
        for line in GOLD_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.skipif(bool(_missing_key_reason()), reason=_missing_key_reason() or "skipped")
async def test_difficulty_correlation_against_expert_ratings() -> None:
    from qme.pipeline.stages.difficulty import DifficultyEngine  # needs key only here

    engine = DifficultyEngine()
    gold = _gold()
    assert len(gold) >= 20

    expert_scores: list[float] = []
    model_scores: list[float] = []
    rating_hits = 0
    deltas: list[tuple[float, str, float]] = []
    started = time.perf_counter()

    for index, row in enumerate(gold, start=1):
        expected = row["expected"]
        result: DifficultyResult = await engine.score(
            DifficultyInput(
                question_text=row["question_text"],
                options=row["options"],
                correct_answer=row["correct_answer"],
                classification=row["classification"],
            )
        )
        expert_scores.append(expected["score"])
        model_scores.append(result.score)
        if result.rating == expected["rating"]:
            rating_hits += 1
        deltas.append((abs(result.score - expected["score"]), row["question_text"], result.score))
        print(
            f"[{index}/{len(gold)}] model={result.score:4.1f} expert={expected['score']:4.1f} "
            f"rating={result.rating:6s} ({time.perf_counter() - started:5.1f}s)",
            flush=True,
        )

    assert len(expert_scores) == len(model_scores) >= 2
    assert max(expert_scores) > min(expert_scores), "expert labels need variance"

    pearson = correlation(expert_scores, model_scores)
    rating_agreement = rating_hits / len(gold)
    mean_abs_error = sum(d for d, _, _ in deltas) / len(deltas)
    model_dist = {
        name: sum(
            1
            for score in model_scores
            if rating_for(score, easy_max=3.5, medium_max=6.5).value == name
        )
        for name in ("easy", "medium", "hard")
    }

    print(
        f"\ndifficulty eval: correlation={pearson:.3f} "
        f"(min {MIN_CORRELATION}) | rating agreement={rating_agreement:.0%} "
        f"| MAE={mean_abs_error:.2f} | model distribution={model_dist}"
    )
    for delta, question, model_score in sorted(deltas, reverse=True)[:5]:
        print(f"  biggest delta {delta:.1f}: model={model_score:.1f} {question[:50]!r}")

    assert pearson >= MIN_CORRELATION, (
        f"correlation {pearson:.3f} below {MIN_CORRELATION} "
        f"(expert={expert_scores}, model={model_scores})"
    )
