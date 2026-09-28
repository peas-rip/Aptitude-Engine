"""Unit tests: QuestionClassifier stage — taxonomy enforcement + corrective retries."""

import json

import pytest

from qme.config.settings import Settings
from qme.config.taxonomy_loader import load_taxonomy
from qme.core.exceptions import LLMResponseFormatError
from qme.core.models import ClassificationInput, ClassificationResult
from qme.core.protocols import QuestionClassifier
from qme.llm.gateway import GatewayResult
from qme.pipeline.stages.classifier import Classifier

INPUT = ClassificationInput(
    question_text="What is 15% of 240?",
    options={"A": "30", "B": "36", "C": "40", "D": "45"},
    correct_answer="B",
)

VALID = ClassificationResult(
    category_id="quantitative_aptitude",
    topic_id="percentages",
    subtopic_id="basic_percentages",
    concepts=["percentage"],
    question_type="mcq",
    tags=["percent"],
    confidence=0.9,
)

BAD_TOPIC = VALID.model_copy(update={"topic_id": "alchemy_is_not_a_topic"})


def _result(value: ClassificationResult) -> GatewayResult[ClassificationResult]:
    return GatewayResult(
        value=value,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        duration_ms=1,
        attempts=1,
    )


class FakeGateway:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> GatewayResult[ClassificationResult]:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _classifier(outcomes: list, *, max_retries: int = 3) -> tuple[Classifier, FakeGateway]:
    gateway = FakeGateway(outcomes)
    settings = Settings(llm_provider="groq", groq_api_key="k", max_retries=max_retries)
    return Classifier(gateway=gateway, settings=settings), gateway


class TestProtocolConformance:
    def test_implements_question_classifier_protocol(self) -> None:
        classifier, _ = _classifier([_result(VALID)])
        assert isinstance(classifier, QuestionClassifier)

    def test_reports_taxonomy_version(self) -> None:
        classifier, _ = _classifier([_result(VALID)])
        assert classifier.get_taxonomy_version() == load_taxonomy().version == 1


class TestClassify:
    pytestmark = pytest.mark.asyncio

    async def test_valid_result_returned_untouched(self) -> None:
        classifier, gateway = _classifier([_result(VALID)])
        result = await classifier.classify(INPUT)
        assert result == VALID
        assert len(gateway.calls) == 1

    async def test_prompt_carries_taxonomy_and_question_separately(self) -> None:
        classifier, gateway = _classifier([_result(VALID)])
        await classifier.classify(INPUT)
        call = gateway.calls[0]
        assert call["stage"] == "classifier"
        assert call["model"] == classifier._model
        system, user = call["messages"]
        assert system["role"] == "system"
        assert "quantitative_aptitude" in system["content"]
        assert "basic_percentages" in system["content"]
        assert user["role"] == "user"
        # Question travels as JSON data in its own message, never interpolated
        # into the template.
        payload = json.loads(user["content"])
        assert payload["question_text"] == INPUT.question_text

    async def test_unknown_ids_trigger_corrective_retry_then_succeed(self) -> None:
        classifier, gateway = _classifier([_result(BAD_TOPIC), _result(VALID)])
        result = await classifier.classify(INPUT)
        assert result == VALID
        assert len(gateway.calls) == 2
        retry_messages = gateway.calls[1]["messages"]
        assert len(retry_messages) == 4  # system, user, assistant echo, correction
        assert "invalid" in retry_messages[3]["content"].lower()
        assert "alchemy_is_not_a_topic" in retry_messages[3]["content"]

    async def test_unknown_category_also_retried(self) -> None:
        bad = VALID.model_copy(update={"category_id": "astrology"})
        classifier, gateway = _classifier([_result(bad), _result(VALID)])
        result = await classifier.classify(INPUT)
        assert result == VALID
        assert len(gateway.calls) == 2

    async def test_unknown_subtopic_also_retried(self) -> None:
        bad = VALID.model_copy(update={"subtopic_id": "not_a_subtopic"})
        classifier, gateway = _classifier([_result(bad), _result(VALID)])
        result = await classifier.classify(INPUT)
        assert result == VALID
        assert len(gateway.calls) == 2

    async def test_persistent_unknown_ids_raise_after_max_retries(self) -> None:
        classifier, gateway = _classifier([_result(BAD_TOPIC)] * 3, max_retries=3)
        with pytest.raises(LLMResponseFormatError) as excinfo:
            await classifier.classify(INPUT)
        assert excinfo.value.context["attempts"] == 3
        assert excinfo.value.context["errors"]
        assert "alchemy_is_not_a_topic" in " ".join(excinfo.value.context["errors"])
        assert len(gateway.calls) == 3

    async def test_null_subtopic_is_accepted(self) -> None:
        value = VALID.model_copy(update={"subtopic_id": None})
        classifier, gateway = _classifier([_result(value)])
        result = await classifier.classify(INPUT)
        assert result.subtopic_id is None
        assert len(gateway.calls) == 1

    async def test_gateway_errors_propagate_with_context(self) -> None:
        classifier, _ = _classifier([LLMResponseFormatError("schema miss", context={"a": 1})])
        with pytest.raises(LLMResponseFormatError):
            await classifier.classify(INPUT)
