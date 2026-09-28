"""Unit tests: strict structured-output schema enforcement (structured-only rule)."""

from qme.core.exceptions import LLMResponseFormatError
from qme.core.models import ClassificationResult, SolutionResult
from qme.llm.structured_output import parse_model, strict_schema


def _walk(node) -> dict:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


class TestStrictSchema:
    def test_every_object_has_additional_properties_false(self) -> None:
        for model in (ClassificationResult, SolutionResult):
            for node in _walk(strict_schema(model)):
                if node.get("type") == "object" and "properties" in node:
                    assert node["additionalProperties"] is False

    def test_every_object_requires_all_properties(self) -> None:
        for model in (ClassificationResult, SolutionResult):
            for node in _walk(strict_schema(model)):
                if node.get("type") == "object" and "properties" in node:
                    assert set(node["required"]) == set(node["properties"])

    def test_cosmetic_keys_stripped_everywhere(self) -> None:
        for model in (ClassificationResult, SolutionResult):
            for node in _walk(strict_schema(model)):
                assert "title" not in node
                assert "default" not in node

    def test_nullable_field_stays_nullable_and_required(self) -> None:
        schema = strict_schema(ClassificationResult)
        assert "subtopic_id" in schema["required"]
        subtopic_schema = schema["properties"]["subtopic_id"]
        branches = subtopic_schema.get("anyOf", [subtopic_schema])
        types = []
        for branch in branches:
            types.extend(branch.get("type", []) if isinstance(branch.get("type"), list) else [branch.get("type")])
        assert "null" in types

    def test_nested_defs_are_strict_too(self) -> None:
        schema = strict_schema(SolutionResult)
        assert "$defs" in schema
        for definition in schema["$defs"].values():
            if definition.get("type") == "object" and "properties" in definition:
                assert definition["additionalProperties"] is False
                assert set(definition["required"]) == set(definition["properties"])


class TestParseModel:
    def _content(self) -> str:
        return (
            '{"category_id": "quantitative_aptitude", "topic_id": "percentages",'
            ' "subtopic_id": "basic_percentages", "concepts": ["percentage"],'
            ' "question_type": "mcq", "tags": [], "confidence": 0.9, "reasoning": null}'
        )

    def test_valid_content_parsed_to_typed_model(self) -> None:
        result = parse_model(ClassificationResult, self._content())
        assert isinstance(result, ClassificationResult)
        assert result.topic_id == "percentages"

    def test_invalid_json_raises_response_format_error(self) -> None:
        try:
            parse_model(ClassificationResult, "not json {oops")
        except LLMResponseFormatError as exc:
            assert exc.context["model"] == "ClassificationResult"
            assert exc.context["raw"].startswith("not json")
        else:
            raise AssertionError("expected LLMResponseFormatError")

    def test_schema_violation_raises_response_format_error(self) -> None:
        bad = self._content().replace('"confidence": 0.9', '"confidence": 3.5')
        try:
            parse_model(ClassificationResult, bad)
        except LLMResponseFormatError:
            pass
        else:
            raise AssertionError("expected LLMResponseFormatError")

    def test_missing_field_raises_response_format_error(self) -> None:
        bad = '{"category_id": "x", "topic_id": "y"}'
        try:
            parse_model(ClassificationResult, bad)
        except LLMResponseFormatError:
            pass
        else:
            raise AssertionError("expected LLMResponseFormatError")
