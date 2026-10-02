"""Interim corpus metadata batch job (authorized interim; superseded by Step 8).

Runs the two pipeline stages that exist today (Classifier -> DifficultyEngine)
over a normalized corpus and writes one metadata record per question:

    {"question": NormalizedQuestion, "classification": ..., "difficulty": ...,
     "status": "ok" | "failed", "error": str | None, "low_confidence": bool,
     "provenance": {classifier_model, classifier_prompt, difficulty_model,
                    difficulty_prompt, difficulty_methodology, processed_at}}

Not a test of correctness — an opt-in job that reuses pytest's runner so the
code lives inside ``tests/`` per the no-code-outside-src rule:

    # smoke (3 questions, separate output)
    QME_BATCH_LIMIT=3 QME_BATCH_OUTPUT=data/output/metadata_batch_smoke \
      python -X utf8 -m pytest -m ai_eval tests/batch -s

    # full run (resumable: status=ok records are skipped on restart)
    python -X utf8 -m pytest -m ai_eval tests/batch -s

Resume semantics: records are appended; failures are retried on restart and
the LAST record per question wins when reading the output.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qme.core.models import (
    ClassificationInput,
    DifficultyInput,
    NormalizedQuestion,
)
from qme.llm.gateway import LLMGateway
from qme.pipeline.stages.classifier import Classifier
from qme.pipeline.stages.difficulty import DifficultyEngine

logger = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.ai_eval,
    pytest.mark.slow,
    pytest.mark.asyncio,
]

INPUT_PATH = Path(
    os.environ.get("QME_BATCH_INPUT", "data/output/book_ingest/normalized.jsonl")
)
OUTPUT_PATH = Path(
    os.environ.get("QME_BATCH_OUTPUT", "data/output/metadata_batch/metadata.jsonl")
)
LIMIT = int(os.environ.get("QME_BATCH_LIMIT", "0"))

LOW_CONFIDENCE = 0.7  # stage test convention: confidence below this = review signal


def _question_key(q: NormalizedQuestion) -> str:
    if q.source.question_id:
        return q.source.question_id
    return "h" + hashlib.sha1(q.question_text.encode("utf-8")).hexdigest()[:12]


def _load_done(path: Path) -> set[str]:
    """Question keys already processed with status=ok (broken lines tolerated)."""
    done: set[str] = set()
    if not path.exists():
        return done
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if record.get("status") == "ok":
                done.add(record["key"])
        except json.JSONDecodeError:
            logger.warning("batch output broken line skipped | line=%d", number)
    return done


def _load_questions(path: Path) -> list[NormalizedQuestion]:
    questions: list[NormalizedQuestion] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            questions.append(NormalizedQuestion.model_validate_json(line))
        except Exception as exc:
            logger.warning("invalid normalized record skipped | line=%d | %s", number, exc)
    return questions


async def test_run_corpus_metadata_batch() -> None:
    from qme.config.settings import get_settings

    settings = get_settings()
    assert INPUT_PATH.exists(), f"input corpus missing: {INPUT_PATH}"
    questions = _load_questions(INPUT_PATH)
    assert questions, f"no valid questions in {INPUT_PATH}"

    done = _load_done(OUTPUT_PATH)
    pending = [q for q in questions if _question_key(q) not in done]
    if LIMIT > 0:
        pending = pending[:LIMIT]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gateway = LLMGateway(settings=settings)
    classifier = Classifier(gateway=gateway, settings=settings)
    difficulty = DifficultyEngine(gateway=gateway, settings=settings)

    started = time.perf_counter()
    counts = {"ok": 0, "failed": 0, "skipped": len(questions) - len(pending)}
    rating_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    with OUTPUT_PATH.open("a", encoding="utf-8") as out:
        for index, question in enumerate(pending, start=1):
            key = _question_key(question)
            record: dict = {
                "key": key,
                "question": question.model_dump(),
                "status": "failed",
                "error": None,
                "low_confidence": False,
                "provenance": {
                    "classifier_model": settings.model_classifier,
                    "classifier_prompt": "classifier_v1",
                    "difficulty_model": settings.model_difficulty,
                    "difficulty_prompt": "difficulty_v1",
                    "difficulty_methodology": None,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            try:
                classification = await classifier.classify(
                    ClassificationInput(
                        question_text=question.question_text,
                        options=question.options,
                        correct_answer=question.correct_answer,
                    )
                )
                record["classification"] = classification.model_dump()

                result = await difficulty.score(
                    DifficultyInput(
                        question_text=question.question_text,
                        options=question.options,
                        correct_answer=question.correct_answer,
                        classification=classification,
                    )
                )
                record["difficulty"] = result.model_dump()
                record["provenance"]["difficulty_methodology"] = (
                    result.methodology_version
                )
                record["low_confidence"] = result.confidence < LOW_CONFIDENCE
                record["status"] = "ok"
                rating_counts[result.rating] = rating_counts.get(result.rating, 0) + 1
                category_counts[classification.category_id] = (
                    category_counts.get(classification.category_id, 0) + 1
                )
                if record["low_confidence"]:
                    logger.warning(
                        "low difficulty confidence (possible fallback) | key=%s | "
                        "confidence=%.2f",
                        key,
                        result.confidence,
                    )
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                logger.warning("question failed | key=%s | %s", key, record["error"])

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            counts[record["status"]] += 1
            elapsed = time.perf_counter() - started
            print(
                f"[{index}/{len(pending)}] {record['status']:6s} {key} "
                f"({elapsed:6.0f}s)",
                flush=True,
            )

    summary = {
        "input": str(INPUT_PATH),
        "output": str(OUTPUT_PATH),
        "total_questions": len(questions),
        "processed_now": len(pending),
        **counts,
        "ratings": rating_counts,
        "categories": category_counts,
        "elapsed_sec": round(time.perf_counter() - started),
    }
    print("BATCH SUMMARY: " + json.dumps(summary, ensure_ascii=False), flush=True)
    assert counts["failed"] == 0 or counts["ok"] > 0, (
        f"batch made no progress: {summary}"
    )
