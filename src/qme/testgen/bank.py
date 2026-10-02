"""Upstream bank loading and contract validation.

The three external files ARE the contract:

- ``aptitude_test_blueprint.json`` — declares the bank filenames, the
  test-generation contract (required/optional filters, selection rules,
  output fields) and the chapter/topic/difficulty bucket counts.
- ``book_questions_agent_ready.jsonl`` — one question per line.
- ``aptitude_agent_knowledge.json`` — chapter/topic knowledge (formulas,
  short tricks).

Any violation raises :class:`~qme.testgen.errors.ContractError` with a
field-level report — mismatches are never silently repaired or skipped.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from qme.testgen.errors import ContractError
from qme.testgen.schemas import (
    BankQuestion,
    Blueprint,
    KnowledgeBank,
    KnowledgeTopic,
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

    @property
    def chapters(self) -> list[str]:
        return sorted({q.classification.chapter for q in self.questions})

    @property
    def topics(self) -> list[str]:
        return sorted({q.classification.topic for q in self.questions})

    @property
    def difficulties(self) -> list[str]:
        return sorted({q.classification.difficulty for q in self.questions})

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


def _validate_knowledge(questions: list[BankQuestion], knowledge: KnowledgeBank) -> None:
    issues: list[str] = []
    bank_pairs = {(q.classification.chapter, q.classification.topic) for q in questions}
    for chapter, topic in sorted(bank_pairs):
        chapter_entry = knowledge.chapters.get(chapter)
        if chapter_entry is None:
            issues.append(f"knowledge bank missing chapter {chapter!r}")
            continue
        if topic not in chapter_entry.topics:
            issues.append(f"knowledge bank missing topic {topic!r} under chapter {chapter!r}")
    if issues:
        raise ContractError(
            "knowledge bank does not cover the question bank", issues
        )


def load_bank(blueprint_path: Path) -> Bank:
    """Load and cross-validate the three upstream files (hard stop on mismatch)."""
    blueprint = Blueprint.model_validate(_read_json(blueprint_path, "blueprint"))
    _validate_contract(blueprint)

    questions_path = blueprint_path.parent / blueprint.question_bank
    knowledge_path = blueprint_path.parent / blueprint.knowledge_bank

    questions = _load_questions(questions_path)
    knowledge = KnowledgeBank.model_validate(_read_json(knowledge_path, "knowledge bank"))

    duplicate_ids = [
        qid for qid, n in Counter(q.question_id for q in questions).items() if n > 1
    ]
    if duplicate_ids:
        raise ContractError(
            "question bank has duplicate question_id values",
            [f"duplicate: {qid}" for qid in duplicate_ids[:_MAX_REPORTED_ISSUES]],
        )

    bucket_counts = _validate_bucket_counts(blueprint, questions)
    _validate_knowledge(questions, knowledge)

    logger.info(
        "bank loaded | questions=%d | chapters=%d | blueprint=%s",
        len(questions),
        len(knowledge.chapters),
        blueprint_path.name,
    )
    return Bank(
        questions=questions,
        knowledge=knowledge,
        blueprint=blueprint,
        blueprint_path=blueprint_path,
        bucket_counts=bucket_counts,
    )
