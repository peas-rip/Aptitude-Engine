"""Pure difficulty math (FE-003): scoring, rating buckets, time model.

Deterministic, no I/O, no LLM — every function is a candidate for exhaustive
unit tests. All thresholds arrive as arguments so config stays the single
source of truth (factor weights are config-only; the LLM never sets them).
"""

from collections.abc import Mapping

from qme.core.constants import DifficultyRating

_WEIGHT_SUM_TOLERANCE = 1e-6


def weighted_score(
    scores: Mapping[str, float], weights: Mapping[str, float]
) -> float:
    """Weighted sum of factor scores, scaled back to 0.0-10.0.

    Every weighted factor must have a score; weights must sum to 1.0.
    Raises ``ValueError`` on misconfiguration or incomplete input — a wrong
    score must never be produced silently.
    """
    if not weights:
        raise ValueError("difficulty weights are empty")
    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"difficulty weights must sum to 1.0, got {total}")
    missing = [name for name in weights if name not in scores]
    if missing:
        raise ValueError(f"missing factor scores: {', '.join(sorted(missing))}")
    result = sum(weights[name] * scores[name] for name in weights)
    for name, value in scores.items():
        if not 0.0 <= value <= 10.0:
            raise ValueError(f"factor {name!r} score {value} outside 0-10")
    return max(0.0, min(10.0, result))


def rating_for(
    score: float, *, easy_max: float, medium_max: float
) -> DifficultyRating:
    """Bucket a 0-10 score: easy <= easy_max < medium <= medium_max < hard."""
    if not 0.0 <= score <= 10.0:
        raise ValueError(f"difficulty score {score} outside 0-10")
    if easy_max >= medium_max:
        raise ValueError(
            f"rating thresholds inverted: easy_max {easy_max} >= medium_max {medium_max}"
        )
    if score <= easy_max:
        return DifficultyRating.EASY
    if score <= medium_max:
        return DifficultyRating.MEDIUM
    return DifficultyRating.HARD


def estimate_time_sec(
    score: float, *, base_time_sec: int, time_per_point_sec: int
) -> int:
    """Linear time model: base seconds plus a per-difficulty-point allowance."""
    if base_time_sec < 1 or time_per_point_sec < 0:
        raise ValueError("time model config must yield positive seconds")
    if not 0.0 <= score <= 10.0:
        raise ValueError(f"difficulty score {score} outside 0-10")
    return max(1, round(base_time_sec + time_per_point_sec * score))
