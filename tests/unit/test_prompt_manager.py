"""Unit tests: versioned prompt templates (FE-008 prompt_version)."""

from hashlib import sha256
from pathlib import Path

import pytest

from qme.core.exceptions import LLMError
from qme.llm.prompt_manager import PromptManager


class TestLoad:
    def test_classifier_prompt_loads_from_default_dir(self) -> None:
        prompt = PromptManager().load("classifier_v1")
        assert prompt.name == "classifier_v1"
        assert "$taxonomy" in prompt.content

    def test_version_is_sha256_of_content(self) -> None:
        prompt = PromptManager().load("classifier_v1")
        expected = sha256(prompt.content.encode("utf-8")).hexdigest()
        assert prompt.version == expected
        assert len(prompt.version) == 64

    def test_missing_template_raises(self) -> None:
        with pytest.raises(LLMError) as excinfo:
            PromptManager().load("does_not_exist")
        assert "does_not_exist" in str(excinfo.value)


class TestRender:
    def test_substitutes_trusted_variables(self) -> None:
        prompt = PromptManager().load("classifier_v1")
        rendered = prompt.render(taxonomy="- quantitative_aptitude (Quantitative Aptitude)")
        assert "$taxonomy" not in rendered
        assert "- quantitative_aptitude (Quantitative Aptitude)" in rendered

    def test_literal_braces_are_not_interpolation(self) -> None:
        prompt = PromptManager().load("classifier_v1")
        rendered = prompt.render(taxonomy='JSON like {"a": 1} stays literal')
        assert '{"a": 1}' in rendered

    def test_missing_placeholder_raises_llm_error(self) -> None:
        prompt = PromptManager().load("classifier_v1")
        with pytest.raises(LLMError) as excinfo:
            prompt.render()  # taxonomy not provided
        assert "taxonomy" in str(excinfo.value)

    def test_malformed_placeholder_raises_llm_error(self, tmp_path: Path) -> None:
        (tmp_path / "bad.txt").write_text("cost $5 per call", encoding="utf-8")
        loaded = PromptManager(tmp_path).load("bad")
        with pytest.raises(LLMError) as excinfo:
            loaded.render()
        assert "malformed" in str(excinfo.value)
