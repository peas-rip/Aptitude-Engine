"""Unit tests: taxonomy loading and validation (FE-002 strictness rules)."""

from pathlib import Path

import pytest

from qme.config.taxonomy_loader import Taxonomy, load_taxonomy
from qme.core.exceptions import QMEError

_MINIMAL = """
taxonomy_version: 2
name: mini
categories:
  - id: category_a
    name: Category A
    topics:
      - id: topic_a
        name: Topic A
        subtopics:
          - id: sub_a
            name: Sub A
"""


class TestSeedTaxonomy:
    def test_seed_loads_with_expected_shape(self) -> None:
        taxonomy = load_taxonomy()
        assert taxonomy.version == 1
        assert len(taxonomy.document.categories) == 4
        assert sum(len(c.topics) for c in taxonomy.document.categories) >= 30
        assert sum(
            len(t.subtopics) for c in taxonomy.document.categories for t in c.topics
        ) >= 60

    def test_render_for_prompt_contains_hierarchy(self) -> None:
        rendered = load_taxonomy().render_for_prompt()
        assert "- quantitative_aptitude (Quantitative Aptitude)" in rendered
        assert "  - percentages (Percentages)" in rendered

    def test_validate_ids_accepts_real_ids(self) -> None:
        taxonomy = load_taxonomy()
        assert taxonomy.validate_ids("quantitative_aptitude", "percentages", None) == []
        assert (
            taxonomy.validate_ids("quantitative_aptitude", "percentages", "basic_percentages")
            == []
        )

    def test_validate_ids_rejects_unknown_category(self) -> None:
        errors = load_taxonomy().validate_ids("astrology", "numbers", None)
        assert len(errors) == 1
        assert "astrology" in errors[0]

    def test_validate_ids_rejects_unknown_topic(self) -> None:
        errors = load_taxonomy().validate_ids("quantitative_aptitude", "alchemy", None)
        assert errors and "alchemy" in errors[0]

    def test_validate_ids_rejects_unknown_subtopic(self) -> None:
        errors = load_taxonomy().validate_ids(
            "quantitative_aptitude", "percentages", "alchemy"
        )
        assert errors and "alchemy" in errors[0]

    def test_load_is_cached(self) -> None:
        assert load_taxonomy() is load_taxonomy()


class TestInvalidDocuments:
    def test_missing_file_raises(self) -> None:
        with pytest.raises(QMEError, match="not found"):
            load_taxonomy(Path("/nonexistent/taxonomy.yaml"))

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.yaml"
        path.write_text("categories: [unclosed", encoding="utf-8")
        with pytest.raises(QMEError, match="not valid YAML"):
            load_taxonomy(path)

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- just\n- a list\n", encoding="utf-8")
        with pytest.raises(QMEError, match="mapping"):
            load_taxonomy(path)

    def test_unknown_key_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "extra.yaml"
        content = _MINIMAL.replace("categories:", "surprise: true\ncategories:")
        path.write_text(content, encoding="utf-8")
        with pytest.raises(QMEError, match="invalid taxonomy"):
            load_taxonomy(path)

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "dup.yaml"
        path.write_text(
            """
taxonomy_version: 2
name: dup
categories:
  - id: same_id
    name: One
    topics:
      - id: topic_a
        name: Topic A
  - id: same_id
    name: Two
    topics:
      - id: topic_b
        name: Topic B
""",
            encoding="utf-8",
        )
        with pytest.raises(QMEError, match="duplicate"):
            load_taxonomy(path)

    def test_duplicate_topic_ids_within_category_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "dup_topic.yaml"
        path.write_text(
            """
taxonomy_version: 2
name: dup
categories:
  - id: cat
    name: Cat
    topics:
      - id: t1
        name: T1
      - id: t1
        name: T1 again
""",
            encoding="utf-8",
        )
        with pytest.raises(QMEError, match="duplicate"):
            load_taxonomy(path)

    def test_valid_document_indexes_taxonomy_object(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.yaml"
        path.write_text(_MINIMAL, encoding="utf-8")
        taxonomy = load_taxonomy(path)
        assert isinstance(taxonomy, Taxonomy)
        assert taxonomy.version == 2
        assert taxonomy.validate_ids("category_a", "topic_a", "sub_a") == []
