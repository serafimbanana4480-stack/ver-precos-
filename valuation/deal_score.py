"""Pure, side-effect-free deal-scoring utilities.

These functions are intentionally framework-agnostic: no database access, no
I/O, no global state. That keeps them unit-testable in isolation and lets the
DB-backed :class:`analysis.deal_scorer.DealScorer` and the Streamlit dashboard
reuse the exact same scoring logic.

This module is the "clean code" reference used in interviews -- see
``tests/unit/test_deal_score.py`` for the accompanying test suite.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional, Sequence


def compute_market_median(
    prices: Sequence[float], iqr_filter: bool = True
) -> Optional[float]:
    """Median price of comparable vehicles, robust to outliers.

    Args:
        prices: Non-negative listing prices for comparable vehicles.
        iqr_filter: When ``True``, drop extreme outliers with the 1.5*IQR
            rule before computing the median (guards against可笑 listings).

    Returns:
        Median price, or ``None`` when fewer than 3 valid prices are supplied
        (not enough signal to trust a market estimate).

    Examples:
        >>> compute_market_median([10000, 11000, 12000, 13000])
        11500.0
        >>> compute_market_median([500, 1000, 50000])  # 50000 is an outlier
        750.0
        >>> compute_market_median([100.0])  # too few samples
        None
    """
    cleaned: List[float] = [float(p) for p in prices if p and p > 0]
    if len(cleaned) < 3:
        return None

    if not iqr_filter:
        return statistics.median(cleaned)

    q1, _, q3 = statistics.quantiles(cleaned, n=4)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    filtered = [p for p in cleaned if lower <= p <= upper]
    # If filtering removes everything (degenerate spread), fall back to all.
    sample = filtered or cleaned
    return statistics.median(sample)


@dataclass(frozen=True)
class DealScore:
    """Result of scoring a single vehicle against the market."""

    score: float  # 0-10, higher = better deal
    market_median: Optional[float]
    diff_percent: Optional[float]  # (median - price) / median * 100
    is_good_deal: bool
    km_adjustment: float
    reason: str = ""


def score_deal(
    price: float,
    market_median: Optional[float],
    km: int = 0,
    *,
    neutral_score: float = 5.0,
    per_percent_point: float = 0.15,
    good_deal_threshold: float = 7.5,
) -> DealScore:
    """Score a vehicle's deal quality on a 0-10 scale.

    Scoring model:
        * ``5.0`` means the vehicle is priced exactly at the market median.
        * Each 1% the price sits *below* median adds ``per_percent_point``
          (≈ +1.5 points per 10% discount).
        * Mileage tiers nudge the base score:
            - < 30k km : +1.0   (very low mileage premium)
            - < 80k km : +0.3   (below-average mileage)
            - > 130k km: -1.0   (high mileage penalty)
            - > 200k km: -2.0   (very high mileage penalty)

    The final score is clamped to ``[0, 10]``.

    Args:
        price: Asking price in EUR.
        market_median: Median market price from :func:`compute_market_median`,
            or ``None`` when insufficient comparables exist.
        km: Vehicle mileage in km.
        neutral_score: Score assigned when priced at median (no data penalty).
        per_percent_point: Score weight per percent point of discount/premium.
        good_deal_threshold: ``is_good_deal`` becomes ``True`` at/above this.

    Returns:
        A :class:`DealScore` with the final score and supporting detail.

    Examples:
        >>> r = score_deal(9000, 10000, km=50000)
        >>> r.score > 5.0 and r.is_good_deal
        True
        >>> score_deal(20000, None).reason
        'Insufficient market data (< 3 comparables)'
    """
    if market_median is None or market_median <= 0:
        return DealScore(
            score=neutral_score,
            market_median=None,
            diff_percent=None,
            is_good_deal=False,
            km_adjustment=0.0,
            reason="Insufficient market data (< 3 comparables)",
        )

    diff_percent = (market_median - price) / market_median * 100.0
    score = neutral_score + diff_percent * per_percent_point

    km_adjustment = 0.0
    if km < 30_000:
        km_adjustment = 1.0
    elif km < 80_000:
        km_adjustment = 0.3
    elif km > 200_000:
        km_adjustment = -2.0
    elif km > 130_000:
        km_adjustment = -1.0
    score += km_adjustment

    score = max(0.0, min(10.0, score))
    return DealScore(
        score=round(score, 2),
        market_median=round(market_median, 2),
        diff_percent=round(diff_percent, 2),
        is_good_deal=score >= good_deal_threshold,
        km_adjustment=km_adjustment,
    )
