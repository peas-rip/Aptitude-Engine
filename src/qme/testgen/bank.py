"""Upstream bank loading and contract validation.

The three external files ARE the contract:

- ``aptitude_test_blueprint.json`` — declares the bank filenames, the
  test-generation contract (required/optional filters, selection rules,
  output fields) and the chapter/topic/difficulty bucket counts.
- ``book_questions_agent_ready.jsonl`` — one question per line.
- ``aptitude_agent_knowledge.json`` — chapter/topic knowledge (formulas,
  short tricks). Knowledge is OPTIONAL per chapter: gaps never block the
  load — they are reported (API_CONTRACTS 1.7 ``knowledge_coverage``) and
  the knowledge endpoint answers with empty lists.

Any violation raises :class:`~qme.testgen.errors.ContractError` with a
field-level report — mismatches are never silently repaired or skipped.
``question_id`` must be globally unique across sources (ids are never
rewritten — the producer namespaces them, e.g. ``tcs-12``).
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from qme.testgen.errors import ContractError, SelectionError
from qme.testgen.schemas import (
    CHAPTER_SEP,
    BankQuestion,
    Blueprint,
    ChapterInfo,
    KnowledgeBank,
    KnowledgeCoverage,
    KnowledgeTopic,
    SourceInfo,
    qualify_chapter,
)

logger = logging.getLogger(__name__)

_EXPECTED_REQUIRED_FILTERS = ["chapter", "topic", "difficulty"]
_EXPECTED_OUTPUT_FIELDS = ["test_id", "questions", "answer_key", "coverage", "timing"]
_MAX_REPORTED_ISSUES = 15


@dataclass
class Bank:
    """Validated, in-memory view of the three upstream files."""

    questions: list[BankQuestion]
    knowledge: KnowledgeBank
    blueprint: Blueprint
    blueprint_path: Path
    bucket_counts: Counter = field(default_factory=Counter)
    knowledge_missing: list[str] = field(default_factory=list)

    @property
    def chapters(self) -> list[str]:
        return sorted({q.classification.chapter for q in self.questions})

    @property
    def qualified_chapters(self) -> list[str]:
        return sorted(
            {
                qualify_chapter(q.source.name, q.classification.chapter)
                for q in self.questions
            }
        )

    @property
    def topics(self) -> list[str]:
        return sorted({q.classification.topic for q in self.questions})

    @property
    def difficulties(self) -> list[str]:
        return sorted({q.classification.difficulty for q in self.questions})

    @property
    def source_names(self) -> list[str]:
        return sorted({q.source.name for q in self.questions})

    def source_infos(self) -> list[SourceInfo]:
        """Per-source chapter breakdowns for ``GET /bank/meta`` pickers."""
        infos: list[SourceInfo] = []
        for source in self.source_names:
            questions = [q for q in self.questions if q.source.name == source]
            chapters: list[ChapterInfo] = []
            for label in sorted({q.classification.chapter for q in questions}):
                own = [q for q in questions if q.classification.chapter == label]
                chapters.append(
                    ChapterInfo(
                        key=qualify_chapter(source, label),
                        label=label,
                        question_count=len(own),
                        difficulty_counts=dict(
                            Counter(q.classification.difficulty for q in own)
                        ),
                    )
                )
            infos.append(
                SourceInfo(
                    name=source,
                    question_count=len(questions),
                    chapters=chapters,
                )
            )
        return infos

    def knowledge_coverage(self) -> KnowledgeCoverage:
        labels = sorted({q.classification.chapter for q in self.questions})
        missing = set(self.knowledge_missing)
        return KnowledgeCoverage(
            covered_chapters=[c for c in labels if c not in missing],
            missing_chapters=[c for c in labels if c in missing],
        )

    def chapter_label(self, key: str) -> str:
        """Strip the source qualifier (``"Src › Label"`` -> ``"Label"``).

        Unqualified keys pass through — knowledge lookup is source-less.
        """
        if CHAPTER_SEP in key:
            return key.partition(CHAPTER_SEP)[2]
        return key

    def resolve_chapter(self, key: str) -> str:
        """Resolve a chapter key to its unqualified label or raise.

        Qualified keys must name an existing source + chapter pair; raw
        labels must match exactly one source (never silently merged).
        """
        if CHAPTER_SEP in key:
            source, _, label = key.partition(CHAPTER_SEP)
            if source not in self.source_names:
                raise SelectionError(
                    f"unknown source {source!r} in chapter key",
                    {"available": {"sources": self.source_names}},
                )
            if not any(
                q.source.name == source and q.classification.chapter == label
                for q in self.questions
            ):
                owned = sorted(
                    {
                        q.classification.chapter
                        for q in self.questions
                        if q.source.name == source
                    }
                )
                raise SelectionError(
                    f"chapter {label!r} not found in source {source!r}",
                    {"available": {"chapters": owned}},
                )
            return label
        matches = sorted(
            {q.source.name for q in self.questions if q.classification.chapter == key}
        )
        if not matches:
            raise SelectionError(
                f"unknown chapter {key!r}",
                {"available": {"chapters": self.chapters}},
            )
        if len(matches) > 1:
            raise SelectionError(
                f"chapter {key!r} is ambiguous across sources; qualify it as "
                f"{qualify_chapter(matches[0], key)!r}",
                {"ambiguous": [qualify_chapter(s, key) for s in matches]},
            )
        return key

    def knowledge_for(self, chapter: str, topic: str) -> KnowledgeTopic | None:
        chapter_entry = self.knowledge.chapters.get(chapter)
        if chapter_entry is None:
            return None
        return chapter_entry.topics.get(topic)


def _read_json(path: Path, label: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{label} is not valid JSON: {path} ({exc})") from exc


def _load_questions(path: Path) -> list[BankQuestion]:
    if not path.exists():
        raise ContractError(f"question bank not found: {path}")
    questions: list[BankQuestion] = []
    issues: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            questions.append(BankQuestion.model_validate_json(line))
        except ValidationError as exc:
            fields = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in exc.errors()[:4]
            )
            issues.append(f"line {number}: {fields}")
            if len(issues) >= _MAX_REPORTED_ISSUES:
                issues.append(f"... (report capped at {_MAX_REPORTED_ISSUES} lines)")
                break
    if issues:
        raise ContractError(
            f"{path.name}: {len(issues)} question record(s) violate the bank schema",
            issues,
        )
    if not questions:
        raise ContractError(f"{path.name}: bank contains no questions")
    return questions


def _validate_contract(blueprint: Blueprint) -> None:
    contract = blueprint.test_generation_contract
    issues: list[str] = []
    if contract.required_filters != _EXPECTED_REQUIRED_FILTERS:
        issues.append(
            "required_filters: expected "
            f"{_EXPECTED_REQUIRED_FILTERS}, got {contract.required_filters}"
        )
    missing_outputs = [f for f in _EXPECTED_OUTPUT_FIELDS if f not in contract.output_fields]
    if missing_outputs:
        issues.append(f"output_fields missing {missing_outputs}")
    if not contract.selection_rules:
        issues.append("selection_rules: empty")
    if issues:
        raise ContractError("blueprint test_generation_contract violated", issues)


def _validate_bucket_counts(blueprint: Blueprint, questions: list[BankQuestion]) -> Counter:
    actual: Counter[tuple[str, str, str]] = Counter(
        (q.classification.chapter, q.classification.topic, q.classification.difficulty)
        for q in questions
    )
    issues: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for chapter, topics in blueprint.buckets.items():
        for topic, difficulties in topics.items():
            for difficulty, expected in difficulties.items():
                key = (chapter, topic, difficulty)
                seen.add(key)
                got = actual.get(key, 0)
                if got != expected:
                    issues.append(
                        f"buckets[{chapter}][{topic}][{difficulty}]: "
                        f"blueprint says {expected}, bank has {got}"
                    )
    for key, got in actual.items():
        if key not in seen:
            issues.append(
                f"bank has {got} question(s) at {key} but blueprint buckets omit it"
            )
    if issues:
        raise ContractError("blueprint buckets do not match the question bank", issues)
    return actual


def _knowledge_gaps(
    questions: list[BankQuestion], knowledge: KnowledgeBank
) -> tuple[list[str], list[str]]:
    """Report knowledge gaps without blocking the load (knowledge is optional).

    Returns ``(issues, missing_chapters)``: a chapter is missing when any of
    its (chapter, topic) pairs has no knowledge entry.
    """
    issues: list[str] = []
    missing: set[str] = set()
    bank_pairs = sorted({(q.classification.chapter, q.classification.topic) for q in questions})
    for chapter, topic in bank_pairs:
        chapter_entry = knowledge.chapters.get(chapter)
        if chapter_entry is None:
            issues.append(f"knowledge bank missing chapter {chapter!r}")
            missing.add(chapter)
            continue
        if topic not in chapter_entry.topics:
            issues.append(
                f"knowledge bank missing topic {topic!r} under chapter {chapter!r}"
            )
            missing.add(chapter)
    return issues, sorted(missing)


def load_bank(blueprint_path: Path) -> Bank:
    """Load and cross-validate the three upstream files (hard stop on mismatch)."""
    blueprint = Blueprint.model_validate(_read_json(blueprint_path, "blueprint"))
    _validate_contract(blueprint)

    questions_path = blueprint_path.parent / blueprint.question_bank
    knowledge_path = blueprint_path.parent / blueprint.knowledge_bank

    questions = _load_questions(questions_path)
    knowledge = KnowledgeBank.model_validate(_read_json(knowledge_path, "knowledge bank"))

    by_id: dict[str, list[BankQuestion]] = {}
    for q in questions:
        by_id.setdefault(q.question_id, []).append(q)
    duplicate_ids = {qid: qs for qid, qs in by_id.items() if len(qs) > 1}
    if duplicate_ids:
        report = []
        for qid, qs in sorted(duplicate_ids.items())[:_MAX_REPORTED_ISSUES]:
            sources = sorted({q.source.name for q in qs})
            report.append(
                f"question_id {qid!r} appears {len(qs)}x (sources: {sources})"
            )
        report.append(
            "question_id must be globally unique across sources — prefix ids "
            "per source (e.g. 'tcs-12'); ids are never rewritten"
        )
        raise ContractError("question bank has duplicate question_id values", report)

    bucket_counts = _validate_bucket_counts(blueprint, questions)
    knowledge_issues, knowledge_missing = _knowledge_gaps(questions, knowledge)
    if knowledge_issues:
        logger.warning(
            "knowledge gaps reported (non-blocking) | file=%s | gaps=%d | chapters_missing=%d",
            knowledge_path.name,
            len(knowledge_issues),
            len(knowledge_missing),
        )

    logger.info(
        "bank loaded | questions=%d | chapters=%d | sources=%d | blueprint=%s",
        len(questions),
        len({q.classification.chapter for q in questions}),
        len({q.source.name for q in questions}),
        blueprint_path.name,
    )
    return Bank(
        questions=questions,
        knowledge=knowledge,
        blueprint=blueprint,
        blueprint_path=blueprint_path,
        bucket_counts=bucket_counts,
        knowledge_missing=knowledge_missing,
    )
