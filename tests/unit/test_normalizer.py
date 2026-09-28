"""Unit tests: normalizer rules (FE-001 validation requirements)."""

import pytest

from qme.core.exceptions import NormalizationError
from qme.core.models import SourceInfo
from qme.ingestion.normalizer import Normalizer
from qme.ingestion.parsers.base import RawQuestion, RawRecord

SOURCE = SourceInfo(name="book.pdf", type="pdf", identifier="book.pdf")


def _record(
    text: str = "What is 2+2?",
    options: dict[str, str] | None = None,
    answer: str = "A",
) -> RawRecord:
    payload: dict = {
        "question_text": text,
        "correct_answer": answer,
        "options": options if options is not None else {"A": "yes", "B": "no"},
    }
    return RawRecord(location="line 1", question=RawQuestion.model_validate(payload))


def _normalize(
    text: str = "What is 2+2?",
    options: dict[str, str] | None = None,
    answer: str = "A",
) -> str:
    result = Normalizer().normalize(_record(text, options, answer), SOURCE)
    return result.correct_answer


class TestQuestionText:
    def test_whitespace_collapsed(self) -> None:
        out = Normalizer().normalize(_record("  What\n is\t2 + 2?  "), SOURCE)
        assert out.question_text == "What is 2 + 2?"

    def test_non_breaking_space_collapsed(self) -> None:
        out = Normalizer().normalize(_record("Find\xa0the\xa0value"), SOURCE)
        assert out.question_text == "Find the value"

    def test_empty_question_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="question_text"):
            Normalizer().normalize(_record("   "), SOURCE)

    def test_oversized_question_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="10240"):
            Normalizer().normalize(_record("x" * 11_000), SOURCE)


class TestOptions:
    def test_keys_uppercased_and_trimmed(self) -> None:
        out = Normalizer().normalize(_record(options={" b ": " 2 "}, answer="B"), SOURCE)
        assert out.options == {"B": "2"}

    def test_values_whitespace_collapsed(self) -> None:
        out = Normalizer().normalize(_record(options={"A": "New   Delhi\nis  capital"}, answer="A"), SOURCE)
        assert out.options["A"] == "New Delhi is capital"

    def test_duplicate_key_after_normalization_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="duplicate option key"):
            Normalizer().normalize(_record(options={"A": "x", "a": "y"}, answer="A"), SOURCE)

    def test_multi_character_key_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="single letter"):
            Normalizer().normalize(_record(options={"Option A": "x"}, answer="A"), SOURCE)

    def test_empty_option_value_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="empty text"):
            Normalizer().normalize(_record(options={"A": "  "}, answer="A"), SOURCE)

    def test_no_options_means_empty_dict(self) -> None:
        out = Normalizer().normalize(_record(options={}, answer="42"), SOURCE)
        assert out.options == {}


class TestAnswerResolution:
    @pytest.mark.parametrize("raw", ["B", "b", "B)", "(B)", "B.", "[b]"])
    def test_key_forms_resolve_to_uppercase_key(self, raw: str) -> None:
        assert _normalize(options={"A": "1", "B": "2"}, answer=raw) == "B"

    def test_answer_matching_option_value_resolves_to_key(self) -> None:
        assert _normalize(options={"A": "30", "B": "36", "C": "40"}, answer="36") == "B"

    def test_answer_matching_option_text_resolves_to_key(self) -> None:
        options = {"A": "Mars", "B": "Venus", "C": "Earth"}
        assert _normalize(options=options, answer="Earth") == "C"

    def test_answer_text_match_is_case_insensitive(self) -> None:
        options = {"A": "Delhi", "B": "Mumbai"}
        assert _normalize(options=options, answer="delhi") == "A"

    def test_multi_key_answers_comma_and_space_forms(self) -> None:
        options = {"A": "1", "B": "2", "C": "3", "D": "4"}
        assert _normalize(options=options, answer="A,C") == "A,C"
        assert _normalize(options=options, answer="A, C") == "A,C"
        assert _normalize(options=options, answer="A C") == "A,C"
        assert _normalize(options=options, answer="AC") == "A,C"

    def test_multi_key_answer_deduplicated(self) -> None:
        options = {"A": "1", "B": "2"}
        assert _normalize(options=options, answer="A,A") == "A"

    def test_answer_not_matching_anything_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="does not match"):
            _normalize(options={"A": "1", "B": "2"}, answer="Z")

    def test_answer_matching_two_values_rejected_as_ambiguous(self) -> None:
        with pytest.raises(NormalizationError, match="matches option values"):
            _normalize(options={"A": "42", "B": "42"}, answer="42")

    def test_numeric_entry_answer_accepted(self) -> None:
        assert _normalize(options={}, answer="42") == "42"

    def test_numeric_entry_with_units_accepted(self) -> None:
        assert _normalize(options={}, answer=" 60 km/h ") == "60 km/h"

    def test_non_numeric_answer_without_options_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="must be numeric"):
            _normalize(options={}, answer="forty two")

    def test_empty_answer_rejected(self) -> None:
        with pytest.raises(NormalizationError, match="correct_answer"):
            _normalize(options={"A": "1"}, answer="   ")

    def test_failure_carries_location_and_field_context(self) -> None:
        with pytest.raises(NormalizationError) as exc_info:
            Normalizer().normalize(
                _record(options={"A": "1"}, answer="nope"),
                SOURCE,
            )
        assert exc_info.value.context["location"] == "line 1"
        assert exc_info.value.context["field"] == "correct_answer"


class TestNormalizedOutput:
    def test_normalized_question_carries_source(self) -> None:
        out = Normalizer().normalize(_record(), SOURCE)
        assert out.source == SOURCE
        assert out.source.name == "book.pdf"

    def test_text_answer_stored_as_resolved_key_not_raw_input(self) -> None:
        out = Normalizer().normalize(
            _record(options={"A": "30", "B": "36"}, answer="36"),
            SOURCE,
        )
        assert out.correct_answer == "B"
