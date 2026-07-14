"""Unit tests for the pure deal-scoring module (valuation.deal_score).

These tests run WITHOUT a database or network -- they verify the scoring
math in isolation, which is the point of keeping this logic pure.
"""
import math
import pytest

from valuation.deal_score import (
    DealScore,
    compute_market_median,
    score_deal,
)


# --------------------------------------------------------------------------- #
# compute_market_median
# --------------------------------------------------------------------------- #
class TestComputeMarketMedian:
    def test_returns_median_for_even_count(self):
        assert compute_market_median([10000, 11000, 12000, 13000]) == 11500.0

    def test_returns_median_for_odd_count(self):
        assert compute_market_median([10000, 11000, 12000]) == 11000.0

    def test_too_few_samples_returns_none(self):
        assert compute_market_median([100.0]) is None
        assert compute_market_median([100.0, 200.0]) is None

    def test_filters_extreme_outlier(self):
        # Tight cluster [10k..16k] plus one wild outlier (1_000_000).
        # q3=15750, IQR=4500 -> upper bound = 15750 + 6750 = 22500,
        # so 1_000_000 is dropped and the median is of the cluster (13000).
        result = compute_market_median(
            [10000, 11000, 12000, 13000, 14000, 15000, 16000, 1_000_000]
        )
        assert result == 13000.0

    def test_ignores_zero_and_negative_prices(self):
        assert compute_market_median([0, -5, 10000, 12000, 14000]) == 12000.0

    def test_iqr_filter_can_be_disabled(self):
        # Without filtering, median of all four values (incl. huge outlier).
        result = compute_market_median([500, 1000, 1500, 1_000_000], iqr_filter=False)
        assert result == (1000 + 1500) / 2  # 1250.0

    def test_value_near_upper_bound_is_kept(self):
        # 50000 is NOT an outlier under the 1.5*IQR rule, so it stays.
        # q1=625, q3=37875, IQR=37250 -> upper = 37875 + 55875 = 93750.
        assert compute_market_median([500, 1000, 1500, 50000]) == 1250.0

    def test_empty_input_returns_none(self):
        assert compute_market_median([]) is None


# --------------------------------------------------------------------------- #
# score_deal
# --------------------------------------------------------------------------- #
class TestScoreDeal:
    def test_neutral_when_at_median(self):
        # price == median, km=60000 -> +0.3 km bonus -> 5.3 (clamped free).
        r = score_deal(price=10000, market_median=10000, km=60000)
        assert r.score == 5.3
        assert r.diff_percent == 0.0
        assert not r.is_good_deal

    def test_discount_increases_score(self):
        # +10% discount * 0.15 = +1.5 ; km=60000 -> +0.3 => 6.8
        r = score_deal(price=9000, market_median=10000, km=60000)
        assert r.score == 6.8
        assert r.diff_percent == 10.0

    def test_large_discount_is_good_deal(self):
        # +50% * 0.15 = +7.5 ; km=60000 -> +0.3 => 12.8 clamped to 10.0
        r = score_deal(price=5000, market_median=10000, km=60000)
        assert r.score == 10.0
        assert r.is_good_deal

    def test_overpriced_gets_penalized(self):
        # -20% * 0.15 = -3.0 ; km=60000 -> +0.3 => 2.3
        r = score_deal(price=12000, market_median=10000, km=60000)
        assert r.score == 2.3
        assert not r.is_good_deal

    def test_low_mileage_bonus(self):
        r = score_deal(price=10000, market_median=10000, km=10000)
        assert r.km_adjustment == 1.0
        assert r.score == 6.0

    def test_very_high_mileage_penalty(self):
        r = score_deal(price=10000, market_median=10000, km=250000)
        assert r.km_adjustment == -2.0
        assert r.score == 3.0

    def test_high_mileage_penalty(self):
        r = score_deal(price=10000, market_median=10000, km=150000)
        assert r.km_adjustment == -1.0
        assert r.score == 4.0

    def test_score_clamped_to_zero(self):
        # Massively overpriced + very high mileage -> must not go negative.
        r = score_deal(price=1_000_000, market_median=10000, km=300000)
        assert r.score == 0.0

    def test_score_clamped_to_ten(self):
        r = score_deal(price=100, market_median=10000, km=1000)
        assert r.score == 10.0

    def test_missing_market_data_returns_neutral_with_reason(self):
        r = score_deal(price=20000, market_median=None)
        assert r.score == 5.0
        assert r.market_median is None
        assert r.reason.startswith("Insufficient market data")
        assert not r.is_good_deal

    def test_invalid_market_median_treated_as_missing(self):
        r = score_deal(price=20000, market_median=0)
        assert r.score == 5.0
        assert r.reason.startswith("Insufficient market data")

    def test_good_deal_threshold_default(self):
        # At km=60000 (+0.3 bonus): price 9000 -> 10% off * 0.15 = 1.5 + 0.3 = 6.8 (NOT good).
        # price 8000 -> 20% off * 0.15 = 3.0 + 0.3 = 8.3 (good, >= 7.5).
        r_low = score_deal(price=9000, market_median=10000, km=60000)
        r_high = score_deal(price=8000, market_median=10000, km=60000)
        assert not r_low.is_good_deal
        assert r_high.is_good_deal

    def test_custom_threshold(self):
        r = score_deal(price=9000, market_median=10000, km=60000, good_deal_threshold=6.0)
        assert r.is_good_deal  # score 6.8 >= 6.0

    def test_no_km_bonus_at_median(self):
        # km=0 -> falls into <30000 tier -> +1.0 bonus.
        r = score_deal(price=10000, market_median=10000, km=0)
        assert r.km_adjustment == 1.0
        assert r.score == 6.0
