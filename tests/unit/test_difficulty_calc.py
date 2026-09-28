"""Unit tests: pure difficulty math (FE-003 factor calculation)."""

import pytest

from qme.core.constants import DifficultyRating
from qme.utils.difficulty_calc import estimate_time_sec, rating_for, weighted_score

WEIGHTS = {
    "concept_count": 0.15,
    "reasoning_complexity": 0.30,
    "calculation_complexity": 0.10,
    "steps": 0.20,
    "ambiguity": 0.15,
    "formula_complexity": 0.10,
}
ALL_TENS = {name: 10.0 for name in WEIGHTS}
ALL_ZEROS = {name: 0.0 for name in WEIGHTS}


class TestWeightedScore:
    def test_all_zero_scores_score_zero(self) -> None:
        assert weighted_score(ALL_ZEROS, WEIGHTS) == 0.0

    def test_all_max_scores_score_ten(self) -> None:
        assert weighted_score(ALL_TENS, WEIGHTS) == pytest.approx(10.0)

    def test_weights_sum_is_one(self) -> None:
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)

    def test_known_mix(self) -> None:
        scores = dict(ALL_ZEROS)
        scores["reasoning_complexity"] = 8.0  # 0.30 * 8 = 2.4
        scores["steps"] = 4.0  # 0.20 * 4 = 0.8
        assert weighted_score(scores, WEIGHTS) == pytest.approx(3.2)

    def test_extra_scores_do_not_influence_result(self) -> None:
        scores = dict(ALL_TENS)
        scores["unlisted_factor"] = 0.0
        assert weighted_score(scores, WEIGHTS) == pytest.approx(10.0)

    def test_missing_factor_raises(self) -> None:
        scores = {k: v for k, v in ALL_TENS.items() if k != "steps"}
        with pytest.raises(ValueError, match="missing factor scores: steps"):
            weighted_score(scores, WEIGHTS)

    def test_weights_not_summing_to_one_raise(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            weighted_score(ALL_TENS, {"a": 0.5, "b": 0.7})

    def test_empty_weights_raise(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            weighted_score(ALL_TENS, {})

    @pytest.mark.parametrize("bad", [-0.1, 10.1, float("nan")])
    def test_out_of_range_factor_score_raises(self, bad: float) -> None:
        scores = dict(ALL_ZEROS)
        scores["ambiguity"] = bad
        with pytest.raises(ValueError, match="outside 0-10"):
            weighted_score(scores, WEIGHTS)


class TestRatingFor:
    THRESHOLDS = {"easy_max": 3.5, "medium_max": 6.5}

    @pytest.mark.parametrize("score", [0.0, 1.0, 3.4, 3.5])
    def test_easy(self, score: float) -> None:
        assert rating_for(score, **self.THRESHOLDS) is DifficultyRating.EASY

    @pytest.mark.parametrize("score", [3.51, 5.0, 6.5])
    def test_medium(self, score: float) -> None:
        assert rating_for(score, **self.THRESHOLDS) is DifficultyRating.MEDIUM

    @pytest.mark.parametrize("score", [6.51, 8.0, 10.0])
    def test_hard(self, score: float) -> None:
        assert rating_for(score, **self.THRESHOLDS) is DifficultyRating.HARD

    def test_boundary_precedence_easy_then_medium(self) -> None:
        assert rating_for(3.5, easy_max=3.5, medium_max=6.5) is DifficultyRating.EASY
        assert rating_for(6.5, easy_max=3.5, medium_max=6.5) is DifficultyRating.MEDIUM

    @pytest.mark.parametrize("score", [-0.01, 10.01])
    def test_score_out_of_range_raises(self, score: float) -> None:
        with pytest.raises(ValueError, match="outside 0-10"):
            rating_for(score, **self.THRESHOLDS)

    def test_inverted_thresholds_raise(self) -> None:
        with pytest.raises(ValueError, match="inverted"):
            rating_for(5.0, easy_max=7.0, medium_max=6.5)


class TestEstimateTime:
    def test_zero_score_gives_base_time(self) -> None:
        assert estimate_time_sec(0.0, base_time_sec=30, time_per_point_sec=12) == 30

    def test_max_score_scales_linearly(self) -> None:
        assert estimate_time_sec(10.0, base_time_sec=30, time_per_point_sec=12) == 150

    def test_monotonic_and_positive(self) -> None:
        times = [
            estimate_time_sec(score / 2, base_time_sec=30, time_per_point_sec=12)
            for score in range(21)
        ]
        assert all(t > 0 for t in times)
        assert times == sorted(times)

    @pytest.mark.parametrize("score", [-0.5, 10.5])
    def test_score_out_of_range_raises(self, score: float) -> None:
        with pytest.raises(ValueError, match="outside 0-10"):
            estimate_time_sec(score, base_time_sec=30, time_per_point_sec=12)

    def test_bad_config_raises(self) -> None:
        with pytest.raises(ValueError, match="positive seconds"):
            estimate_time_sec(5.0, base_time_sec=0, time_per_point_sec=12)
