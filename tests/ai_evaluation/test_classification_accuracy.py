"""Opt-in live accuracy evaluation of the classifier against the gold standard.

Not part of the default suite (rate-limited real API calls):

    pytest -m ai_eval tests/ai_evaluation

Requires the active provider's API key in ``.env`` (gemini by default);
skips cleanly otherwise.
Metrics: exact-match accuracy per hierarchy level (category / topic / subtopic).
"""

import json
from pathlib import Path

import pytest

from qme.config.settings import get_settings
from qme.core.models import ClassificationInput

pytestmark = [
    pytest.mark.ai_eval,
    pytest.mark.asyncio,
    pytest.mark.slow,
]

GOLD_PATH = Path(__file__).resolve().parent / "gold_standard" / "classification.jsonl"

# Sanity floors, not targets: a model below these is broken, not imprecise.
MIN_CATEGORY_ACCURACY = 0.70
MIN_TOPIC_ACCURACY = 0.50


def _missing_key_reason() -> str:
    """Skip unless the active provider (from .env) actually has a key."""
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
    rows = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


@pytest.mark.skipif(bool(_missing_key_reason()), reason=_missing_key_reason() or "skipped")
async def test_classification_accuracy_against_gold_standard() -> None:
    from qme.pipeline.stages.classifier import Classifier  # deferred: needs key only here

    classifier = Classifier()
    gold = _gold()
    assert len(gold) >= 20

    category_hits = topic_hits = subtopic_hits = subtopic_total = 0
    misses: list[str] = []
    for row in gold:
        result = await classifier.classify(
            ClassificationInput(
                question_text=row["question_text"],
                options=row["options"],
                correct_answer=row["correct_answer"],
            )
        )
        expected = row["expected"]
        if result.category_id == expected["category_id"]:
            category_hits += 1
        else:
            misses.append(f"[category] {row['question_text'][:40]!r}: {result.category_id}")
        if result.topic_id == expected["topic_id"]:
            topic_hits += 1
        else:
            misses.append(
                f"[topic] {row['question_text'][:40]!r}: "
                f"got {result.topic_id}, want {expected['topic_id']}"
            )
        if expected["subtopic_id"] is not None:
            subtopic_total += 1
            if result.subtopic_id == expected["subtopic_id"]:
                subtopic_hits += 1

    total = len(gold)
    report = {
        "category": f"{category_hits}/{total}",
        "topic": f"{topic_hits}/{total}",
        "subtopic": f"{subtopic_hits}/{subtopic_total}",
    }
    print(f"\nclassification accuracy: {report}")
    for miss in misses:
        print(f"  miss: {miss}")

    assert category_hits / total >= MIN_CATEGORY_ACCURACY, report
    assert topic_hits / total >= MIN_TOPIC_ACCURACY, report
