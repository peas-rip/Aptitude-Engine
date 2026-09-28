"""Integration: ingest -> classify -> score difficulty through the real stages.

Both stages are real (real taxonomy, real prompt templates, real pure math);
only the LLM calls are scripted, so the offline chain is exercised end-to-end.
"""

from pathlib import Path

import pytest

from qme.config.settings import Settings
from qme.config.taxonomy_loader import load_taxonomy
from qme.core.constants import DifficultyRating
from qme.core.exceptions import LLMError
from qme.core.models import (
    ClassificationInput,
    ClassificationResult,
    DifficultyInput,
    DifficultyResult,
    NormalizedQuestion,
)
from qme.ingestion import ingest_file
from qme.llm.gateway import GatewayResult
from qme.pipeline.stages.classifier import Classifier
from qme.pipeline.stages.difficulty import (
    DifficultyAssessment,
    DifficultyEngine,
    FactorScore,
)

pytestmark = pytest.mark.asyncio

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"

CLASSIFICATION = ClassificationResult(
    category_id="quantitative_aptitude",
    topic_id="percentages",
    subtopic_id="basic_percentages",
    concepts=["percentage"],
    question_type="mcq",
    confidence=0.95,
)

ASSESSMENT = DifficultyAssessment(
    concept_count=FactorScore(score=3.0, reasoning="single concept"),
    reasoning_complexity=FactorScore(score=4.0, reasoning="direct formula"),
    calculation_complexity=FactorScore(score=5.0, reasoning="one multiplication"),
    steps=FactorScore(score=4.0, reasoning="two steps"),
    ambiguity=FactorScore(score=2.0, reasoning="clear options"),
    formula_complexity=FactorScore(score=1.0, reasoning="basic percent"),
    confidence=0.9,
)


class FakeGateway:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> GatewayResult:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _settings() -> Settings:
    return Settings(llm_provider="gemini", gemini_api_key="k")


def _first_question() -> NormalizedQuestion:
    return ingest_file(SAMPLES / "sample_questions.jsonl").questions[0]


async def test_classify_then_score_end_to_end() -> None:
    question = _first_question()

    classifier = Classifier(
        gateway=FakeGateway(
            [
                GatewayResult(
                    value=CLASSIFICATION,
                    model="m",
                    prompt_tokens=1,
                    completion_tokens=1,
                    duration_ms=1,
                    attempts=1,
                )
            ]
        ),
        settings=_settings(),
    )
    classification = await classifier.classify(
        ClassificationInput(
            question_text=question.question_text,
            options=question.options,
            correct_answer=question.correct_answer,
        )
    )
    assert classification.topic_id == "percentages"

    engine = DifficultyEngine(
        gateway=FakeGateway(
            [
                GatewayResult(
                    value=ASSESSMENT,
                    model="m",
                    prompt_tokens=1,
                    completion_tokens=1,
                    duration_ms=1,
                    attempts=1,
                )
            ]
        ),
        settings=_settings(),
    )
    result = await engine.score(
        DifficultyInput(
            question_text=question.question_text,
            options=question.options,
            correct_answer=question.correct_answer,
            classification=classification,
        )
    )

    # Full contract validation + consistency checks
    DifficultyResult.model_validate(result.model_dump())
    assert 0.0 <= result.score <= 10.0
    assert result.rating in {r.value for r in DifficultyRating}
    assert len(result.factors) == 6
    assert sum(f.weight for f in result.factors) == pytest.approx(1.0)
    assert result.estimated_time_sec > 0
    assert result.methodology_version == "difficulty_v1"


async def test_difficulty_fallback_keeps_pipeline_alive() -> None:
    question = _first_question()
    engine = DifficultyEngine(gateway=FakeGateway([LLMError("down")]), settings=_settings())
    result = await engine.score(
        DifficultyInput(
            question_text=question.question_text,
            options=question.options,
            correct_answer=question.correct_answer,
            classification=CLASSIFICATION,
        )
    )
    assert result.score == 5.0
    assert result.confidence < 0.7
    assert load_taxonomy().validate_ids(
        CLASSIFICATION.category_id,
        CLASSIFICATION.topic_id,
        CLASSIFICATION.subtopic_id,
    ) == []
