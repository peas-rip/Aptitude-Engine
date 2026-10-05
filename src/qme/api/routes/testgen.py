"""Testgen HTTP endpoints (API_CONTRACTS 1.7).

Stateless JSON only — no file writes, no client-supplied paths. The bank is
cached by the mtimes of all three upstream files (blueprint, question bank,
knowledge bank), so replacing any of them is picked up on the next request
without a restart; any contract violation surfaces as a 503 with the full
field report (never silently tolerated).
"""

import json
import logging
import random
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from qme.api.exceptions import NotFoundError, UnauthorizedError
from qme.config.settings import get_settings
from qme.testgen import generate_practice, generate_test, load_bank
from qme.testgen.bank import Bank
from qme.testgen.errors import ContractError, SelectionError
from qme.testgen.schemas import (
    ChapterKnowledge,
    GeneratedTest,
    KnowledgeTerms,
    PracticeRequest,
    PracticeSet,
    SubmitRequest,
    TestRequest,
    TestResult,
    TestSpec,
)
from qme.testgen.scoring import score_test
from qme.testgen.spec import compile_spec, parse_test_request

logger = logging.getLogger(__name__)

_cache: dict = {"key": None, "bank": None}


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate ``X-API-Key`` against ``QME_API_KEY`` (empty key = open, dev only)."""
    expected = get_settings().qme_api_key
    if not expected:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise UnauthorizedError("missing or invalid X-API-Key header")


def _dep_paths(blueprint_path: Path) -> tuple[Path, Path]:
    """Question-bank + knowledge paths declared by the blueprint."""
    try:
        data = json.loads(blueprint_path.read_text(encoding="utf-8"))
        return (
            blueprint_path.parent / data["question_bank"],
            blueprint_path.parent / data["knowledge_bank"],
        )
    except FileNotFoundError as exc:
        raise ContractError(f"blueprint not readable: {blueprint_path} ({exc.strerror})") from exc
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ContractError(f"blueprint not valid JSON: {blueprint_path} ({exc})") from exc


def get_bank() -> Bank:
    """Serve the validated bank, revalidating whenever any bank file changes."""
    path: Path = get_settings().qme_blueprint_path
    questions_path, knowledge_path = _dep_paths(path)
    try:
        key = (
            str(path),
            path.stat().st_mtime_ns,
            questions_path.stat().st_mtime_ns,
            knowledge_path.stat().st_mtime_ns,
        )
    except OSError as exc:
        raise ContractError(f"bank file not readable: {exc}") from exc
    if _cache["bank"] is None or _cache.get("key") != key:
        bank = load_bank(path)
        _cache.update(key=key, bank=bank)
        logger.info(
            "bank loaded | path=%s | questions=%d | sources=%s",
            path,
            len(bank.questions),
            bank.source_names,
        )
    return _cache["bank"]


def _new_seed() -> int:
    return random.SystemRandom().randrange(10**9)


def _parse_body(data: dict[str, Any]) -> TestRequest | TestSpec:
    """Shape discrimination with schema errors mapped to VALIDATION_ERROR."""
    try:
        return parse_test_request(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


router = APIRouter(
    prefix="/api/v1",
    tags=["testgen"],
    dependencies=[Depends(_require_api_key)],
)


@router.get("/bank/meta")
def bank_meta(bank: Annotated[Bank, Depends(get_bank)]) -> dict:
    """Discovery: sources, qualified chapters, feasibility counts, contract."""
    return {
        "sources": [s.model_dump() for s in bank.source_infos()],
        "chapters": bank.qualified_chapters,
        "topics": bank.topics,
        "difficulties": bank.difficulties,
        "question_count": len(bank.questions),
        "buckets": bank.blueprint.buckets,
        "knowledge_coverage": bank.knowledge_coverage().model_dump(),
        "contract": bank.blueprint.test_generation_contract.model_dump(),
    }


@router.post("/tests", response_model=GeneratedTest)
def create_test(
    request: dict[str, Any], bank: Annotated[Bank, Depends(get_bank)]
) -> GeneratedTest:
    """Assemble a test from either request shape (deterministic per seed)."""
    parsed = _parse_body(request)
    if isinstance(parsed, TestSpec):
        if parsed.seed is None:
            parsed.seed = _new_seed()
        parsed = compile_spec(bank, parsed)
    elif parsed.seed is None:
        parsed.seed = _new_seed()
    return generate_test(bank, parsed)


@router.post("/tests/submit", response_model=TestResult)
def submit_test(
    submission: SubmitRequest, bank: Annotated[Bank, Depends(get_bank)]
) -> TestResult:
    """Regenerate the submitted test and score the answers (1.7 round-trip)."""
    parsed = _parse_body(submission.request)
    if parsed.seed is None:
        raise SelectionError(
            "submission request is missing the seed echoed by POST /tests; "
            "send the original request body including seed",
            {"violations": [{"rule": "seed_required", "actual": None}]},
        )
    if isinstance(parsed, TestSpec):
        parsed = compile_spec(bank, parsed)
    test = generate_test(bank, parsed)
    return score_test(
        test.questions,
        submission.answers,
        test_id=submission.test_id or test.test_id,
        elapsed_seconds=submission.elapsed_seconds,
    )


@router.post("/practice", response_model=PracticeSet)
def create_practice(
    request: PracticeRequest, bank: Annotated[Bank, Depends(get_bank)]
) -> PracticeSet:
    """Build one deterministic page of a practice set (1.7)."""
    return generate_practice(bank, request)


@router.get("/chapters/{chapter_key}/knowledge", response_model=ChapterKnowledge)
def chapter_knowledge(
    chapter_key: str,
    bank: Annotated[Bank, Depends(get_bank)],
    topic: Annotated[str | None, Query()] = None,
) -> ChapterKnowledge:
    """Formulas + shortcut tricks for one chapter (source-less, on demand)."""
    label = bank.chapter_label(chapter_key)
    if label not in bank.chapters:
        raise NotFoundError(f"chapter {label!r} not found")
    entry = bank.knowledge.chapters.get(label)
    if entry is None:
        return ChapterKnowledge(chapter=label, topic=topic)
    if topic is not None:
        found = entry.topics.get(topic)
        terms = (
            {topic: KnowledgeTerms(formulas=found.formulas, short_tricks=found.short_tricks)}
            if found is not None
            else {}
        )
    else:
        terms = {
            name: KnowledgeTerms(formulas=t.formulas, short_tricks=t.short_tricks)
            for name, t in entry.topics.items()
        }
    return ChapterKnowledge(
        chapter=label,
        topic=topic,
        formula_summary=entry.chapter_formula_summary,
        topics=terms,
    )
