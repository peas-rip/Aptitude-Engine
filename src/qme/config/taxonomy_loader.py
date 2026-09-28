"""Taxonomy loading + validation (FE-002 dependency).

The seed YAML is human-editable and versioned; the loader refuses anything
ambiguous: duplicate IDs at any level, unknown keys, empty names, or a missing
file all raise :class:`QMEError` with context — never partial loads.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from qme.core.exceptions import QMEError

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "taxonomy" / "seed_taxonomy.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Subtopic(_Strict):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)


class Topic(_Strict):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    subtopics: list[Subtopic] = Field(default_factory=list)


class Category(_Strict):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str | None = None
    topics: list[Topic] = Field(min_length=1)


class TaxonomyDocument(_Strict):
    taxonomy_version: int = Field(ge=1)
    name: str = Field(min_length=1)
    categories: list[Category] = Field(min_length=1)


class Taxonomy:
    """Immutable indexed view of the taxonomy document."""

    def __init__(self, doc: TaxonomyDocument) -> None:
        self._doc = doc
        self._category_ids = [c.id for c in doc.categories]
        self._all_ids: set[str] = set()
        for category in doc.categories:
            self._claim(category.id, f"category {category.id}")
            for topic in category.topics:
                self._claim(topic.id, f"topic {topic.id} in {category.id}")
                for subtopic in topic.subtopics:
                    self._claim(subtopic.id, f"subtopic {subtopic.id} in {category.id}/{topic.id}")

    @property
    def version(self) -> int:
        return self._doc.taxonomy_version

    @property
    def document(self) -> TaxonomyDocument:
        return self._doc

    def validate_ids(
        self, category_id: str, topic_id: str, subtopic_id: str | None
    ) -> list[str]:
        """Return human-readable errors for IDs not present in the taxonomy."""
        errors: list[str] = []
        category = next((c for c in self._doc.categories if c.id == category_id), None)
        if category is None:
            valid = ", ".join(self._category_ids)
            return [f"unknown category_id {category_id!r} (valid: {valid})"]

        topic = next((t for t in category.topics if t.id == topic_id), None)
        if topic is None:
            valid = ", ".join(t.id for t in category.topics)
            errors.append(
                f"unknown topic_id {topic_id!r} for category {category_id!r} (valid: {valid})"
            )
            if subtopic_id is not None:
                errors.append(f"unknown subtopic_id {subtopic_id!r} (topic rejected first)")
            return errors

        if subtopic_id is not None and not any(s.id == subtopic_id for s in topic.subtopics):
            valid = ", ".join(s.id for s in topic.subtopics) or "(none defined)"
            errors.append(
                f"unknown subtopic_id {subtopic_id!r} for topic {topic_id!r} (valid: {valid})"
            )
        return errors

    def render_for_prompt(self) -> str:
        """Indented id (name) tree for embedding in classifier prompts."""
        lines: list[str] = []
        for category in self._doc.categories:
            lines.append(f"- {category.id} ({category.name})")
            for topic in category.topics:
                lines.append(f"  - {topic.id} ({topic.name})")
                for subtopic in topic.subtopics:
                    lines.append(f"    - {subtopic.id} ({subtopic.name})")
        return "\n".join(lines)

    def _claim(self, id_value: str, where: str) -> None:
        if id_value in self._all_ids:
            raise QMEError(
                f"duplicate taxonomy id {id_value!r} in {where}",
                context={"taxonomy_version": self._doc.taxonomy_version},
            )
        self._all_ids.add(id_value)


@lru_cache(maxsize=4)
def load_taxonomy(path: Path | None = None) -> Taxonomy:
    """Load, validate, and cache a taxonomy (default: the seed file)."""
    target = path or _DEFAULT_PATH
    if not target.is_file():
        raise QMEError("taxonomy file not found", context={"path": str(target)})
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise QMEError(
            "taxonomy file is not valid YAML",
            context={"path": str(target), "error": str(exc)},
        ) from exc
    if not isinstance(raw, dict):
        raise QMEError(
            "taxonomy file must contain a YAML mapping",
            context={"path": str(target), "actual_type": type(raw).__name__},
        )
    try:
        document = TaxonomyDocument.model_validate(raw)
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise QMEError(
            f"invalid taxonomy document: {issues}",
            context={"path": str(target)},
        ) from exc
    return Taxonomy(document)
