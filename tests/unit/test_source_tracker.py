"""Unit tests: source tracker provenance defaults (FE-008)."""

import logging
from pathlib import Path

import pytest

from qme.ingestion.parsers.base import PartialSource
from qme.ingestion.source_tracker import SourceTracker

INPUT = Path("data/samples/questions.jsonl")


def _resolve(partial: PartialSource | None = None, fallback_type: str = "jsonl"):
    return SourceTracker().resolve(partial, input_path=INPUT, fallback_type=fallback_type)


class TestSourceResolution:
    def test_full_source_preserved(self) -> None:
        partial = PartialSource(
            name="RS Aggarwal",
            type="pdf",
            identifier="ISBN-123",
            page=55,
            question_id="Q-1",
        )
        source = _resolve(partial)
        assert source.name == "RS Aggarwal"
        assert source.type == "pdf"
        assert source.identifier == "ISBN-123"
        assert source.page == 55
        assert source.question_id == "Q-1"

    def test_no_source_defaults_from_file(self) -> None:
        source = _resolve(None)
        assert source.name == "questions.jsonl"
        assert source.type == "jsonl"
        assert source.identifier == "questions.jsonl"
        assert source.page is None
        assert source.question_id is None

    def test_partial_source_filled_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="qme.ingestion.source_tracker"):
            source = _resolve(PartialSource(name="Mock Test 3"))
        assert source.name == "Mock Test 3"
        assert source.type == "jsonl"
        assert source.identifier == "questions.jsonl"
        assert any("Missing source fields" in r.message for r in caplog.records)

    def test_fallback_type_used_for_csv(self) -> None:
        source = _resolve(None, fallback_type="csv")
        assert source.type == "csv"

    def test_control_characters_sanitized(self) -> None:
        source = _resolve(PartialSource(name="Bad\x00Name\x1f"))
        assert source.name == "BadName"

    def test_long_fields_capped(self) -> None:
        source = _resolve(PartialSource(identifier="x" * 500))
        assert len(source.identifier) == 200

    def test_page_and_question_id_preserved_without_name(self) -> None:
        source = _resolve(PartialSource(page=12, question_id="Q-9"))
        assert source.page == 12
        assert source.question_id == "Q-9"
        assert source.name == "questions.jsonl"

    def test_provenance_never_empty(self) -> None:
        for partial in (None, PartialSource(), PartialSource(name="   ")):
            source = _resolve(partial)
            assert source.name
            assert source.type
            assert source.identifier
