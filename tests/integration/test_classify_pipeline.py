"""Integration: ingest -> classify through the real taxonomy + prompt chain.

Uses the real :class:`Classifier` (real taxonomy loader, real prompt template)
with a scripted gateway, so the full offline chain is exercised end-to-end.
"""

import json
from pathlib import Path

import pytest

from qme.config.settings import Settings
from qme.config.taxonomy_loader import load_taxonomy
from qme.core.models import ClassificationInput, ClassificationResult, NormalizedQuestion
from qme.ingestion import ingest_file
from qme.llm.gateway import GatewayResult
from qme.pipeline.stages.classifier import Classifier

pytestmark = pytest.mark.asyncio

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


class FakeGateway:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> GatewayResult[ClassificationResult]:
        self.calls.append(kwargs)
        return self._outcomes.pop(0)


def _result(value: ClassificationResult) -> GatewayResult[ClassificationResult]:
    return GatewayResult(
        value=value,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        duration_ms=1,
        attempts=1,
    )


def _classifier(outcomes: list) -> Classifier:
    settings = Settings(llm_provider="groq", groq_api_key="k")
    return Classifier(gateway=FakeGateway(outcomes), settings=settings)


def _input_from(question: NormalizedQuestion) -> ClassificationInput:
    return ClassificationInput(
        question_text=question.question_text,
        options=question.options,
        correct_answer=question.correct_answer,
    )


async def test_sample_question_classifies_end_to_end() -> None:
    ingest = ingest_file(SAMPLES / "sample_questions.jsonl")
    assert len(ingest.questions) == 12

    predicted = ClassificationResult(
        category_id="quantitative_aptitude",
        topic_id="percentages",
        subtopic_id="basic_percentages",
        concepts=["percentage"],
        question_type="mcq",
        tags=["pct"],
        confidence=0.95,
    )
    classifier = _classifier([_result(predicted)] * len(ingest.questions))
    taxonomy = load_taxonomy()

    for question in ingest.questions:
        result = await classifier.classify(_input_from(question))
        assert result == predicted
        assert taxonomy.validate_ids(
            result.category_id, result.topic_id, result.subtopic_id
        ) == []


async def test_taxonomy_rejection_recovers_within_same_call() -> None:
    ingest = ingest_file(SAMPLES / "sample_questions.jsonl")
    first = ClassificationResult(
        category_id="made_up_category",
        topic_id="percentages",
        subtopic_id=None,
        concepts=["percentage"],
        question_type="mcq",
        confidence=0.5,
    )
    recovered = ClassificationResult(
        category_id="quantitative_aptitude",
        topic_id="percentages",
        subtopic_id="basic_percentages",
        concepts=["percentage"],
        question_type="mcq",
        confidence=0.9,
    )
    classifier = _classifier([_result(first), _result(recovered)])

    result = await classifier.classify(_input_from(ingest.questions[0]))
    assert result.category_id == "quantitative_aptitude"
    assert len(classifier._gateway.calls) == 2  # recovery happened in one classify() call


async def test_classifier_prompt_never_contains_question_text() -> None:
    """FE-001 injection containment: question text lives only in the user JSON."""
    ingest = ingest_file(SAMPLES / "sample_questions.jsonl")
    question = ingest.questions[0]
    predicted = ClassificationResult(
        category_id="quantitative_aptitude",
        topic_id="percentages",
        subtopic_id=None,
        concepts=["percentage"],
        question_type="mcq",
        confidence=0.9,
    )
    classifier = _classifier([_result(predicted)])

    await classifier.classify(_input_from(question))
    system_prompt = classifier._gateway.calls[0]["messages"][0]["content"]
    assert question.question_text not in system_prompt
    payload = json.loads(classifier._gateway.calls[0]["messages"][1]["content"])
    assert payload["question_text"] == question.question_text
