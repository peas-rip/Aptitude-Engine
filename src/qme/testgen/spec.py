"""Friendly-shape test request: discrimination, rule table, compilation.

API_CONTRACTS 1.7 — exactly one shape per ``POST /tests`` body. The friendly
shape (:class:`TestSpec`) is validated against the rule table (count
multiple of 5, minimums, mixed composition, feasibility) and compiled to the
legacy :class:`TestRequest`/``Selection`` list the selector already
understands; the selector and assembler stay unchanged.

Every rule violation raises :class:`~qme.testgen.errors.SelectionError` →
API envelope ``422 INVALID_INPUT`` with machine-readable ``details``
(rule, actual value, valid/available options). Nothing is silently clamped,
rounded, or dropped.
"""

import logging
from typing import NoReturn, cast

from qme.testgen.bank import Bank
from qme.testgen.errors import SelectionError
from qme.testgen.schemas import (
    CHAPTER_SEP,
    DIFFICULTY_RANK,
    Difficulty,
    Selection,
    TestRequest,
    TestSpec,
    qualify_chapter,
)

logger = logging.getLogger(__name__)

COUNT_MULTIPLE = 5
MIN_TEST_QUESTIONS = 10
MIN_ALL_SCOPE_QUESTIONS = 30
VALID_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")

_LEGACY_KEYS = {"selections"}
_FRIENDLY_KEYS = {"difficulty", "count", "chapters", "sources"}


def parse_test_request(data: dict) -> TestRequest | TestSpec:
    """Discriminate the two ``POST /tests`` shapes (exactly one per body)."""
    has_legacy = bool(_LEGACY_KEYS & data.keys())
    has_friendly = bool(_FRIENDLY_KEYS & data.keys())
    if has_legacy and has_friendly:
        both = sorted(_FRIENDLY_KEYS & data.keys())
        raise SelectionError(
            "request carries both the legacy 'selections' shape and friendly-shape "
            f"fields ({', '.join(both)}); send exactly one shape",
            {"violations": [{"rule": "single_shape", "conflicting_fields": both}]},
        )
    if has_legacy:
        return TestRequest.model_validate(data)
    return TestSpec.model_validate(data)


def _raise(violations: list[dict], extra: dict | None = None) -> NoReturn:
    details: dict = {"violations": violations}
    if extra:
        details.update(extra)
    raise SelectionError(
        "test request violates the request rules: "
        + "; ".join(f"{v['rule']} (actual: {v.get('actual')!r})" for v in violations),
        details,
    )


def _scope(bank: Bank, spec: TestSpec) -> tuple[list[str], list[str]]:
    """Resolve sources + chapters to the in-scope qualified chapter keys.

    Raises (via :func:`_raise`) on unknown/empty/contradictory scope.
    """
    violations: list[dict] = []

    if spec.sources is None:
        sources = bank.source_names
    elif not spec.sources:
        violations.append(
            {"rule": "sources_not_empty", "actual": [], "expected": "omit for all sources"}
        )
        sources = []
    else:
        unknown = [s for s in spec.sources if s not in bank.source_names]
        if unknown:
            violations.append(
                {"rule": "unknown_source", "actual": unknown, "expected": bank.source_names}
            )
        sources = sorted(set(spec.sources) - set(unknown))

    if spec.chapters is None:
        chapter_keys = [
            qualify_chapter(q.source.name, q.classification.chapter)
            for q in bank.questions
            if q.source.name in sources
        ]
        chapter_keys = sorted(set(chapter_keys))
    elif not spec.chapters:
        violations.append(
            {"rule": "chapters_not_empty", "actual": [], "expected": "omit for all chapters"}
        )
        chapter_keys = []
    else:
        chapter_keys = []
        for key in spec.chapters:
            try:
                label = bank.resolve_chapter(key)
            except SelectionError as exc:
                violations.append({"rule": "unknown_chapter", "actual": key, "detail": str(exc)})
                continue
            source = key.partition(CHAPTER_SEP)[0] if CHAPTER_SEP in key else None
            if source is None:
                matching = sorted(
                    {
                        q.source.name
                        for q in bank.questions
                        if q.classification.chapter == label
                    }
                )
                if len(matching) == 1:
                    source = matching[0]
                else:
                    violations.append(
                        {"rule": "ambiguous_chapter", "actual": key, "expected": [
                            qualify_chapter(s, label) for s in matching
                        ]}
                    )
                    continue
            if source not in sources:
                violations.append(
                    {
                        "rule": "chapter_outside_sources",
                        "actual": key,
                        "expected": f"chapter within selected sources {sources!r}",
                    }
                )
                continue
            chapter_keys.append(qualify_chapter(source, label))
        chapter_keys = sorted(set(chapter_keys))

    if violations:
        _raise(
            violations,
            {"available": {"sources": bank.source_names, "chapters": bank.qualified_chapters}},
        )
    return sources, chapter_keys


def _difficulty_composition(spec: TestSpec) -> tuple[str, dict[str, int]]:
    """Validate the difficulty block; return ``(mode, per-difficulty counts)``."""
    violations: list[dict] = []
    block = spec.difficulty

    if block.mode == "single":
        if block.value is None:
            violations.append(
                {
                    "rule": "single_requires_value",
                    "actual": None,
                    "expected": list(VALID_DIFFICULTIES),
                }
            )
            _raise(violations)
        return "single", {block.value: spec.count}

    if not block.counts:
        violations.append(
            {
                "rule": "mixed_requires_counts",
                "actual": block.counts,
                "expected": "non-empty {easy, medium, hard} counts summing to count",
            }
        )
        _raise(violations)

    invalid_keys = sorted(set(block.counts) - set(VALID_DIFFICULTIES))
    if invalid_keys:
        violations.append(
            {
                "rule": "mixed_unknown_difficulty",
                "actual": invalid_keys,
                "expected": list(VALID_DIFFICULTIES),
            }
        )
    negative = {k: v for k, v in block.counts.items() if v < 0}
    if negative:
        violations.append(
            {"rule": "mixed_negative_count", "actual": negative, "expected": ">= 0"}
        )
    elif not invalid_keys:
        total = sum(block.counts.values())
        if total != spec.count:
            violations.append(
                {
                    "rule": "mixed_counts_sum",
                    "actual": total,
                    "expected": spec.count,
                }
            )
    if violations:
        _raise(violations)
    return "mixed", dict(block.counts)


def compile_spec(bank: Bank, spec: TestSpec) -> TestRequest:
    """Validate the friendly shape against the rule table and compile it."""
    sources, chapter_keys = _scope(bank, spec)

    violations: list[dict] = []
    if spec.count % COUNT_MULTIPLE != 0:
        violations.append(
            {
                "rule": "count_multiple_of_5",
                "actual": spec.count,
                "expected": f"multiple of {COUNT_MULTIPLE}",
            }
        )
    minimum = MIN_ALL_SCOPE_QUESTIONS if spec.chapters is None else MIN_TEST_QUESTIONS
    if spec.count < minimum:
        violations.append(
            {
                "rule": "count_minimum",
                "actual": spec.count,
                "expected": (
                    f">= {minimum} ({'all-chapters test' if minimum == MIN_ALL_SCOPE_QUESTIONS else 'any test'})"
                ),
            }
        )

    mode, requested = _difficulty_composition(spec)
    if violations:
        _raise(violations)

    scope = [
        q
        for q in bank.questions
        if q.source.name in sources
        and qualify_chapter(q.source.name, q.classification.chapter) in chapter_keys
    ]
    available: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    for q in scope:
        available[q.classification.difficulty] += 1
    short = {
        d: {"requested": n, "available": available[d]}
        for d, n in sorted(requested.items(), key=lambda kv: DIFFICULTY_RANK[kv[0]])
        if n > available[d]
    }
    if short:
        _raise(
            [
                {
                    "rule": "feasibility",
                    "actual": d,
                    "requested": v["requested"],
                    "available": v["available"],
                }
                for d, v in short.items()
            ],
            {"available_by_difficulty": available},
        )

    # The qualified-chapter list encodes BOTH chapter and source scope, so
    # the compiled selections always filter on it (sources > 1 supported).
    selections = [
        Selection(count=n, difficulty=cast(Difficulty, d), chapters=chapter_keys)
        for d, n in sorted(requested.items(), key=lambda kv: DIFFICULTY_RANK[kv[0]])
        if n > 0
    ]
    logger.info(
        "friendly test compiled | scope=%s | mode=%s | selections=%d | count=%d",
        "all" if spec.chapters is None else f"{len(chapter_keys)} chapters",
        mode,
        len(selections),
        spec.count,
    )
    return TestRequest(
        test_id=spec.test_id,
        title=spec.title,
        seed=spec.seed,
        selections=selections,
        include_solutions=True,
    )
