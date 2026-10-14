"""Trailing-only features; missing warm-up values are never backfilled."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, pstdev, stdev

from quant_terminal.models import Bar


@dataclass(frozen=True)
class FeatureRow:
    return_1: float | None = None
    fast_ma: float | None = None
    slow_ma: float | None = None
    volatility: float | None = None
    momentum: float | None = None
    volume_change: float | None = None
    zscore: float | None = None


def build_features(
    bars: tuple[Bar, ...], fast: int = 20, slow: int = 50, lookback: int = 20
) -> tuple[FeatureRow, ...]:
    """Daily volatility is unannualized sample SD; z-score uses population SD."""
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 2 for n in (fast, slow, lookback)):
        raise ValueError("Feature windows must be integers >= 2.")
    closes = [b.close for b in bars]
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("Price ratios exceed the supported floating-point numerical range.")
    result = []
    # ponytail: trailing slices are O(n * window); optimize only for intraday-scale data.
    for i, bar in enumerate(bars):
        window = closes[max(0, i - lookback + 1) : i + 1]
        sd = pstdev(window) if len(window) == lookback else None
        result.append(
            FeatureRow(
                return_1=returns[i - 1] if i else None,
                fast_ma=fmean(closes[i - fast + 1 : i + 1]) if i + 1 >= fast else None,
                slow_ma=fmean(closes[i - slow + 1 : i + 1]) if i + 1 >= slow else None,
                volatility=stdev(returns[i - lookback : i]) if i >= lookback else None,
                momentum=bar.close / closes[i - lookback] - 1 if i >= lookback else None,
                volume_change=bar.volume / bars[i - 1].volume - 1
                if i and bars[i - 1].volume > 0
                else None,
                zscore=(bar.close - fmean(window)) / sd
                if sd and math.isfinite(sd)
                else (0.0 if sd == 0 else None),
            )
        )
    return tuple(result)
