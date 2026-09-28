"""Unit tests: DifficultyEngine stage — assembly, fallback, Protocol conformance."""

import json

import pytest

from qme.config.settings import Settings
from qme.core.constants import DifficultyRating
from qme.core.exceptions import LLMError, LLMRateLimitError, QMEError
from qme.core.models import ClassificationResult, DifficultyInput, DifficultyResult
from qme.core.protocols import DifficultyEngine as DifficultyEngineProtocol
from qme.llm.gateway import GatewayResult
from qme.pipeline.stages.difficulty import (
    _FALLBACK_CONFIDENCE,
    _FALLBACK_SCORE,
    METHODOLOGY_VERSION,
    DifficultyAssessment,
    DifficultyEngine,
    FactorScore,
)
from qme.utils.difficulty_calc import rating_for

CLASSIFICATION = ClassificationResult(
    category_id="quantitative_aptitude",
    topic_id="percentages",
    subtopic_id="basic_percentages",
    concepts=["percentage"],
    question_type="mcq",
    confidence=0.95,
)

INPUT = DifficultyInput(
    question_text="What is 25% of 320?",
    options={"A": "60", "B": "80", "C": "90", "D": "110"},
    correct_answer="B",
    classification=CLASSIFICATION,
)

# Weighted: .15*4 + .30*6 + .10*5 + .20*7 + .15*3 + .10*2 = 4.95 (medium)
FACTOR_SCORES = {
    "concept_count": 4.0,
    "reasoning_complexity": 6.0,
    "calculation_complexity": 5.0,
    "steps": 7.0,
    "ambiguity": 3.0,
    "formula_complexity": 2.0,
}


def _assessment(confidence: float = 0.9, **overrides: float) -> DifficultyAssessment:
    merged = {**FACTOR_SCORES, **overrides}
    return DifficultyAssessment(
        **{
            name: FactorScore(score=score, reasoning=f"{name} is assessed")
            for name, score in merged.items()
        },
        confidence=confidence,
    )


def _result(value: DifficultyAssessment) -> GatewayResult[DifficultyAssessment]:
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

    async def complete(self, **kwargs) -> GatewayResult[DifficultyAssessment]:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _engine(outcomes: list, *, settings: Settings | None = None) -> tuple:
    gateway = FakeGateway(outcomes)
    cfg = settings or Settings(
        llm_provider="gemini", gemini_api_key="k", model_difficulty="m-test"
    )
    return DifficultyEngine(gateway=gateway, settings=cfg), gateway


class TestProtocolConformance:
    def test_implements_difficulty_engine_protocol(self) -> None:
        engine, _ = _engine([_result(_assessment())])
        assert isinstance(engine, DifficultyEngineProtocol)

    def test_rejects_weights_not_matching_schema(self) -> None:
        cfg = Settings(llm_provider="gemini", gemini_api_key="k")
        cfg.difficulty_factor_weights = {"concept_count": 1.0}
        with pytest.raises(QMEError, match="do not match the assessment schema"):
            DifficultyEngine(gateway=FakeGateway([]), settings=cfg)


class TestScore:
    pytestmark = pytest.mark.asyncio

    async def test_weighted_score_and_medium_bucket(self) -> None:
        engine, gateway = _engine([_result(_assessment())])
        result = await engine.score(INPUT)
        assert isinstance(result, DifficultyResult)
        assert result.score == pytest.approx(4.95)
        assert result.rating == DifficultyRating.MEDIUM.value
        assert result.confidence == 0.9
        assert result.methodology_version == METHODOLOGY_VERSION
        assert len(gateway.calls) == 1

    async def test_factors_carry_config_weights_and_reasoning(self) -> None:
        engine, _ = _engine([_result(_assessment())])
        result = await engine.score(INPUT)
        settings = engine._settings
        assert [f.name for f in result.factors] == list(settings.difficulty_factor_weights)
        for factor in result.factors:
            assert factor.weight == settings.difficulty_factor_weights[factor.name]
            assert factor.score == FACTOR_SCORES[factor.name]
            assert factor.reasoning
        assert sum(f.weight for f in result.factors) == pytest.approx(1.0)

    async def test_estimated_time_derives_from_score(self) -> None:
        engine, _ = _engine([_result(_assessment())])
        result = await engine.score(INPUT)
        expected = round(30 + 12 * 4.95)
        assert result.estimated_time_sec == expected
        assert result.estimated_time_sec > 0

    async def test_rating_consistent_with_score_at_boundaries(self) -> None:
        engine, gateway = _engine(
            [
                _result(_assessment(**{name: 0.0 for name in FACTOR_SCORES})),
                _result(_assessment(**{name: 10.0 for name in FACTOR_SCORES})),
            ]
        )
        easy = await engine.score(INPUT)
        hard = await engine.score(INPUT)
        assert easy.score == 0.0
        assert easy.rating == DifficultyRating.EASY.value
        assert hard.score == pytest.approx(10.0)
        assert hard.rating == DifficultyRating.HARD.value
        assert len(gateway.calls) == 2

    async def test_prompt_is_static_and_question_travels_as_user_json(self) -> None:
        engine, gateway = _engine([_result(_assessment())])
        await engine.score(INPUT)
        call = gateway.calls[0]
        assert call["stage"] == "difficulty"
        assert call["model"] == "m-test"
        system, user = call["messages"]
        assert system["role"] == "system"
        assert "Factor definitions" in system["content"]
        assert INPUT.question_text not in system["content"]
        payload = json.loads(user["content"])
        assert payload["question_text"] == INPUT.question_text
        assert payload["classification"]["topic_id"] == "percentages"

    async def test_all_ten_factors_yield_hard_rating(self) -> None:
        engine, _ = _engine([_result(_assessment(**{n: 10.0 for n in FACTOR_SCORES}))])
        result = await engine.score(INPUT)
        assert result.rating == "hard"
        assert rating_for(
            result.score, easy_max=3.5, medium_max=6.5
        ) is DifficultyRating.HARD


class TestFallback:
    pytestmark = pytest.mark.asyncio

    @pytest.mark.parametrize(
        "error",
        [LLMError("gateway down"), LLMRateLimitError("quota exhausted")],
        ids=["llm_error", "rate_limit"],
    )
    async def test_llm_failure_returns_median_with_low_confidence(
        self, error: LLMError
    ) -> None:
        engine, gateway = _engine([error, error, error])
        result = await engine.score(INPUT)
        assert result.score == _FALLBACK_SCORE == 5.0
        assert result.confidence == _FALLBACK_CONFIDENCE
        assert result.confidence < 0.7  # review signal for the validation stage
        assert result.rating == DifficultyRating.MEDIUM.value
        assert len(result.factors) == 6
        assert all(f.score == _FALLBACK_SCORE for f in result.factors)
        assert all("fallback" in f.reasoning for f in result.factors)
        assert len(gateway.calls) == 1

    async def test_fallback_still_carries_methodology_version(self) -> None:
        engine, _ = _engine([LLMError("down")])
        result = await engine.score(INPUT)
        assert result.methodology_version == METHODOLOGY_VERSION
        assert result.estimated_time_sec > 0
