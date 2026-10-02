"""Deterministic quota selection over the bank.

``select`` applies one :class:`Selection` (filters + count) to the bank.
Filter problems (unknown values or zero matches) raise
:class:`SelectionError`; quota shortfalls and already-selected overlaps are
reported, never silently ignored. Selection is seeded: the same seed always
yields the same questions in bank order.
"""

import random
from dataclasses import dataclass

from qme.testgen.bank import Bank
from qme.testgen.errors import SelectionError
from qme.testgen.schemas import BankQuestion, Selection, Shortage


@dataclass
class SelectionResult:
    picked: list[BankQuestion]
    shortage: Shortage | None = None
    overlap_excluded: int = 0


def _matches(q: BankQuestion, s: Selection) -> bool:
    c = q.classification
    if s.chapter is not None and c.chapter != s.chapter:
        return False
    if s.topic is not None and c.topic != s.topic:
        return False
    if s.difficulty is not None and c.difficulty != s.difficulty:
        return False
    if s.question_type is not None and q.agent_metadata.question_type != s.question_type:
        return False
    if s.skills and not (set(s.skills) & set(q.agent_metadata.skills)):
        return False
    if s.page_min is not None and (q.source.page or 0) < s.page_min:
        return False
    return not (s.page_max is not None and (q.source.page or 0) > s.page_max)


def _report_unknown_filters(bank: Bank, s: Selection) -> tuple[list[str], dict]:
    issues: list[str] = []
    available: dict[str, list[str]] = {}
    if s.chapter is not None and s.chapter not in bank.chapters:
        issues.append(f"chapter {s.chapter!r} not in bank (available: {bank.chapters})")
        available["chapters"] = bank.chapters
    if s.topic is not None and s.topic not in bank.topics:
        issues.append(f"topic {s.topic!r} not in bank (available: {bank.topics})")
        available["topics"] = bank.topics
    if s.difficulty is not None and s.difficulty not in bank.difficulties:
        issues.append(
            f"difficulty {s.difficulty!r} not in bank (available: {bank.difficulties})"
        )
        available["difficulties"] = bank.difficulties
    if not issues:
        issues.append(
            f"no question matches filters {s.filter_summary()!r} "
            f"across {len(bank.questions)} questions"
        )
        return issues, {"filters": s.filter_summary(), "total_questions": len(bank.questions)}
    return issues, {"available": available}


def select(
    bank: Bank,
    selection: Selection,
    rng: random.Random,
    selection_index: int = 0,
    exclude: set[str] | None = None,
) -> SelectionResult:
    """Pick up to ``selection.count`` new questions for the request."""
    exclude = exclude or set()
    matching = [q for q in bank.questions if _matches(q, selection)]
    if not matching:
        issues, details = _report_unknown_filters(bank, selection)
        raise SelectionError(
            f"selection #{selection_index} cannot be satisfied: " + "; ".join(issues),
            details,
        )

    eligible = [q for q in matching if q.question_id not in exclude]
    overlap_excluded = len(matching) - len(eligible)

    if len(eligible) > selection.count:
        picked_ids = set(rng.sample([q.question_id for q in eligible], selection.count))
        picked = [q for q in eligible if q.question_id in picked_ids]
    else:
        picked = eligible

    shortage = None
    if len(picked) < selection.count:
        shortage = Shortage(
            selection_index=selection_index,
            requested=selection.count,
            provided=len(picked),
            shortfall=selection.count - len(picked),
            filters=selection.filter_summary(),
        )
    return SelectionResult(
        picked=picked, shortage=shortage, overlap_excluded=overlap_excluded
    )
