"""Unit tests for canonical Pydantic models (Session B gate)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from qme.core.constants import (
    DifficultyRating,
    QuestionStatus,
    QuestionType,
    SolutionSource,
)
from qme.core.models import (
    BatchConfig,
    ClassificationResult,
    DifficultyFactor,
    DifficultyResult,
    EnrichedQuestion,
    FormulaRef,
    NormalizedQuestion,
    ProcessQuestionRequest,
    SolutionResult,
    SolutionStep,
    SourceInfo,
    ValidationResult,
)


def make_classification(**overrides) -> ClassificationResult:
    defaults = {
        "category_id": "cat-quant",
        "topic_id": "topic-tsd",
        "concepts": ["speed", "distance"],
        "question_type": "mcq",
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ClassificationResult(**defaults)


def make_solution(**overrides) -> SolutionResult:
    defaults = {
        "steps": [SolutionStep(step_number=1, description="Convert units")],
        "formulas_used": ["unit_conversion"],
        "calculations": [{"expr": "54 * 5/18", "result": 15}],
        "final_answer": "20s",
        "source": SolutionSource.GENERATED,
        "confidence": 0.9,
        "validation_status": "pending",
    }
    defaults.update(overrides)
    return SolutionResult(**defaults)


def make_enriched(**overrides) -> EnrichedQuestion:
    defaults = {
        "content_hash": "a" * 64,
        "question_text": "A train travels at 54 km/hr...",
        "options": {"A": "20s", "B": "24s"},
        "correct_answer": "B",
        "category_id": "cat-quant",
        "topic_id": "topic-tsd",
        "concepts": ["speed"],
        "question_type": "mcq",
        "difficulty_score": 4.5,
        "difficulty_rating": "medium",
        "difficulty_factors": {"reasoning_complexity": 5.0},
        "estimated_time_sec": 90,
        "solution": make_solution(),
        "solution_source": "generated",
        "formulas_used": [
            FormulaRef(
                name="Time = Distance / Speed",
                expression="t = d/v",
                category="motion",
                confidence=0.95,
            )
        ],
        "source_name": "R.S. Aggarwal",
        "source_type": "pdf",
        "source_identifier": "ISBN-9789352534029",
        "processing_version": "0.1.0",
        "model_used": "gpt-4o",
        "prompt_version": "abc123",
        "processing_timestamp": datetime.now(UTC),
        "processing_duration_ms": 12500,
        "token_usage": {"prompt": 1200, "completion": 800, "total": 2000},
        "estimated_cost_usd": 0.005,
        "validation_status": "validated",
        "status": "validated",
    }
    defaults.update(overrides)
    return EnrichedQuestion(**defaults)


class TestEnrichedQuestion:
    def test_valid_construction_and_roundtrip(self) -> None:
        q = make_enriched()
        data = q.model_dump()
        restored = EnrichedQuestion.model_validate(data)
        assert restored.question_id == q.question_id
        assert restored.content_hash == q.content_hash
        assert restored.status == "validated"

    def test_question_id_defaults_to_uuid(self) -> None:
        q = make_enriched()
        assert isinstance(q.question_id, type(uuid4()))

    def test_serialized_keys_match_contract(self) -> None:
        expected_keys = {
            "question_id",
            "content_hash",
            "question_text",
            "options",
            "correct_answer",
            "category_id",
            "topic_id",
            "subtopic_id",
            "concepts",
            "question_type",
            "difficulty_score",
            "difficulty_rating",
            "difficulty_factors",
            "estimated_time_sec",
            "solution",
            "solution_source",
            "formulas_used",
            "source_name",
            "source_type",
            "source_identifier",
            "source_page",
            "source_question_id",
            "processing_version",
            "model_used",
            "prompt_version",
            "processing_timestamp",
            "processing_duration_ms",
            "token_usage",
            "estimated_cost_usd",
            "validation_status",
            "validation_errors",
            "validation_warnings",
            "status",
        }
        assert set(make_enriched().model_dump().keys()) == expected_keys

    @pytest.mark.parametrize("bad_score", [-0.1, 10.1])
    def test_difficulty_score_out_of_range_rejected(self, bad_score: float) -> None:
        with pytest.raises(ValidationError):
            make_enriched(difficulty_score=bad_score)

    def test_empty_question_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_enriched(question_text="")

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_enriched(processing_duration_ms=-1)

    def test_missing_required_field_rejected(self) -> None:
        data = make_enriched().model_dump()
        del data["topic_id"]
        with pytest.raises(ValidationError):
            EnrichedQuestion.model_validate(data)


class TestClassificationResult:
    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            make_classification(confidence=1.5)
        with pytest.raises(ValidationError):
            make_classification(confidence=-0.1)
        assert make_classification(confidence=0.0).confidence == 0.0
        assert make_classification(confidence=1.0).confidence == 1.0

    def test_defaults(self) -> None:
        r = make_classification()
        assert r.subtopic_id is None
        assert r.tags == []
        assert r.reasoning is None


class TestDifficultyResult:
    def make_result(self, **overrides) -> DifficultyResult:
        defaults = {
            "score": 4.5,
            "rating": "medium",
            "factors": [
                DifficultyFactor(
                    name="reasoning_complexity",
                    weight=0.3,
                    score=7.0,
                    reasoning="multi-step",
                )
            ],
            "estimated_time_sec": 90,
            "confidence": 0.8,
            "methodology_version": "v1",
        }
        defaults.update(overrides)
        return DifficultyResult(**defaults)

    @pytest.mark.parametrize("bad_score", [-1.0, 10.5])
    def test_score_out_of_range_rejected(self, bad_score: float) -> None:
        with pytest.raises(ValidationError):
            self.make_result(score=bad_score)

    def test_factor_weight_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DifficultyFactor(name="x", weight=1.5, score=5.0, reasoning="r")

    def test_negative_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self.make_result(estimated_time_sec=-5)


class TestSolutionResult:
    def test_defaults(self) -> None:
        s = make_solution()
        assert s.steps[0].formula_refs == []
        assert s.steps[0].calculation is None

    def test_step_number_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SolutionStep(step_number=0, description="x")

    def test_empty_final_answer_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_solution(final_answer="")


class TestNormalizedQuestion:
    def test_valid(self) -> None:
        q = NormalizedQuestion(
            question_text="What is 10% of 50?",
            options={"A": "5", "B": "10"},
            correct_answer="A",
            source=SourceInfo(name="book.pdf", type="pdf", identifier="ISBN-1"),
        )
        assert q.correct_answer == "A"

    def test_empty_options_allowed_for_numeric(self) -> None:
        q = NormalizedQuestion(
            question_text="Find x if 2x = 10",
            correct_answer="5",
            source=SourceInfo(name="manual", type="manual", identifier="id-1"),
        )
        assert q.options == {}

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NormalizedQuestion(
                question_text="",
                correct_answer="5",
                source=SourceInfo(name="n", type="manual", identifier="i"),
            )


class TestBatchConfig:
    def test_defaults_match_contract(self) -> None:
        c = BatchConfig()
        assert c.generate_solutions is True
        assert c.extract_formulas is True
        assert c.validate is True
        assert c.checkpoint_interval == 10
        assert c.max_retries == 3
        assert c.model_overrides == {}
        assert c.confidence_thresholds == {
            "classification": 0.7,
            "difficulty": 0.7,
            "solution": 0.8,
            "formula": 0.7,
        }

    def test_defaults_are_not_shared(self) -> None:
        a, b = BatchConfig(), BatchConfig()
        a.confidence_thresholds["classification"] = 0.9
        assert b.confidence_thresholds["classification"] == 0.7

    def test_invalid_checkpoint_interval_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BatchConfig(checkpoint_interval=0)


class TestEnums:
    def test_str_enum_equality(self) -> None:
        assert QuestionType.MCQ == "mcq"
        assert DifficultyRating.HARD == "hard"
        assert QuestionStatus.NEEDS_REVIEW == "needs_review"
        assert SolutionSource.GENERATED == "generated"

    def test_enum_used_as_str_field_value(self) -> None:
        s = make_solution(source=SolutionSource.EXTRACTED)
        assert s.source == "extracted"


class TestValidationAndAPIModels:
    def test_validation_result_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ValidationResult(status="validated", issues=[], overall_confidence=2.0)

    def test_process_request_parses_contract_example(self) -> None:
        req = ProcessQuestionRequest(
            question_text="A train travels at 54 km/hr...",
            options={"A": "20s", "B": "24s", "C": "28s", "D": "32s"},
            correct_answer="B",
            source={
                "name": "Quantitative Aptitude by R.S. Aggarwal",
                "type": "pdf",
                "identifier": "ISBN-9789352534029",
                "page": 142,
                "question_id": "Ex-12-Q15",
            },
            config={"generate_solutions": False},
        )
        assert req.config is not None
        assert req.config.generate_solutions is False
        assert req.source.page == 142
