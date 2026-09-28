"""DifficultyEngine stage (FE-003): explainable 0-10 difficulty scoring.

Contract split (security rule: factor weights come from config, never the LLM):
- the LLM returns only per-factor scores + reasonings + confidence
  (:class:`DifficultyAssessment`, strict json_schema)
- pure functions in :mod:`qme.utils.difficulty_calc` compute the weighted
  score, rating bucket, and estimated time from config thresholds
- gateway failures after retries fall back to the median score with an
  explicitly low confidence (never silent; the low confidence is the
  review signal consumed by the later validation stage)
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from qme.config.settings import Settings, get_settings
from qme.core.exceptions import LLMError, QMEError
from qme.core.models import DifficultyFactor, DifficultyInput, DifficultyResult
from qme.llm.gateway import LLMGateway
from qme.llm.prompt_manager import PromptManager
from qme.utils.difficulty_calc import estimate_time_sec, rating_for, weighted_score

logger = logging.getLogger(__name__)

_PROMPT_NAME = "difficulty_v1"
METHODOLOGY_VERSION = "difficulty_v1"
_FALLBACK_SCORE = 5.0
_FALLBACK_CONFIDENCE = 0.2


class FactorScore(BaseModel):
    """LLM-returned score + reasoning for one difficulty factor."""

    score: float = Field(ge=0.0, le=10.0)
    reasoning: str = Field(min_length=1)


class DifficultyAssessment(BaseModel):
    """Strict schema the LLM fills — weights, rating, and time never come from it."""

    concept_count: FactorScore
    reasoning_complexity: FactorScore
    calculation_complexity: FactorScore
    steps: FactorScore
    ambiguity: FactorScore
    formula_complexity: FactorScore
    confidence: float = Field(ge=0.0, le=1.0)


class DifficultyEngine:
    """Implements the ``DifficultyEngine`` Protocol (score is the only entry point)."""

    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        prompts: PromptManager | None = None,
        model: str | None = None,
        settings: Settings | None = None,
        prompt_dir: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._gateway = gateway or LLMGateway(settings=self._settings)
        self._prompts = prompts or PromptManager(prompt_dir)
        self._model = model or self._settings.model_difficulty
        self._weights = dict(self._settings.difficulty_factor_weights)
        expected = set(DifficultyAssessment.model_fields) - {"confidence"}
        if set(self._weights) != expected:
            raise QMEError(
                "difficulty_factor_weights do not match the assessment schema",
                context={
                    "weights": sorted(self._weights),
                    "expected": sorted(expected),
                },
            )

    async def score(self, input: DifficultyInput) -> DifficultyResult:
        prompt = self._prompts.load(_PROMPT_NAME)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": prompt.render()},
            {
                "role": "user",
                # JSON-serialized data: braces are data, never template input.
                "content": json.dumps(
                    {
                        "question_text": input.question_text,
                        "options": input.options,
                        "correct_answer": input.correct_answer,
                        "classification": input.classification.model_dump(),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            response = await self._gateway.complete(
                messages=messages,
                schema=DifficultyAssessment,
                model=self._model,
                stage="difficulty",
            )
        except LLMError as exc:
            logger.warning(
                "difficulty LLM unavailable, using median fallback | model=%s | %s",
                self._model,
                exc,
            )
            return self._fallback_result()
        logger.debug(
            "difficulty LLM call | model=%s | tokens=%d+%d | attempts=%d",
            response.model,
            response.prompt_tokens,
            response.completion_tokens,
            response.attempts,
        )
        return self._build(response.value)

    def _build(self, assessment: DifficultyAssessment) -> DifficultyResult:
        factor_by_name = {
            "concept_count": assessment.concept_count,
            "reasoning_complexity": assessment.reasoning_complexity,
            "calculation_complexity": assessment.calculation_complexity,
            "steps": assessment.steps,
            "ambiguity": assessment.ambiguity,
            "formula_complexity": assessment.formula_complexity,
        }
        scores = {name: fs.score for name, fs in factor_by_name.items()}
        score = weighted_score(scores, self._weights)
        rating = rating_for(
            score,
            easy_max=self._settings.difficulty_easy_max,
            medium_max=self._settings.difficulty_medium_max,
        )
        estimated = estimate_time_sec(
            score,
            base_time_sec=self._settings.difficulty_base_time_sec,
            time_per_point_sec=self._settings.difficulty_time_per_point_sec,
        )
        factors = [
            DifficultyFactor(
                name=name,
                weight=self._weights[name],
                score=factor_by_name[name].score,
                reasoning=factor_by_name[name].reasoning,
            )
            for name in self._weights
        ]
        return DifficultyResult(
            score=score,
            rating=rating.value,
            factors=factors,
            estimated_time_sec=estimated,
            confidence=assessment.confidence,
            methodology_version=METHODOLOGY_VERSION,
        )

    def _fallback_result(self) -> DifficultyResult:
        """Median score, low confidence — FE-003 error handling, logged above."""
        score = weighted_score(
            {name: _FALLBACK_SCORE for name in self._weights}, self._weights
        )
        rating = rating_for(
            score,
            easy_max=self._settings.difficulty_easy_max,
            medium_max=self._settings.difficulty_medium_max,
        )
        estimated = estimate_time_sec(
            score,
            base_time_sec=self._settings.difficulty_base_time_sec,
            time_per_point_sec=self._settings.difficulty_time_per_point_sec,
        )
        return DifficultyResult(
            score=score,
            rating=rating.value,
            factors=[
                DifficultyFactor(
                    name=name,
                    weight=weight,
                    score=_FALLBACK_SCORE,
                    reasoning="median fallback: LLM unavailable after retries",
                )
                for name, weight in self._weights.items()
            ],
            estimated_time_sec=estimated,
            confidence=_FALLBACK_CONFIDENCE,
            methodology_version=METHODOLOGY_VERSION,
        )
