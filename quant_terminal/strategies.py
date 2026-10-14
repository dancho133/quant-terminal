"""Predeclared baseline hypotheses. Strategies propose; they cannot execute."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from quant_terminal.features import FeatureRow


class Strategy(Protocol):
    name: str
    params: dict[str, int | float]
    hypothesis: str
    assumptions: tuple[str, ...]
    failure_modes: tuple[str, ...]

    def target(self, feature: FeatureRow, current_weight: float) -> float: ...


@dataclass(frozen=True)
class BaselineStrategy:
    name: str
    params: dict[str, int | float]
    hypothesis: str
    assumptions: tuple[str, ...]
    failure_modes: tuple[str, ...]

    def target(self, feature: FeatureRow, current_weight: float) -> float:
        """Propose 40% long or cash. Independent risk may cap the proposal."""
        if self.name == "momentum":
            if feature.fast_ma is None or feature.slow_ma is None or feature.momentum is None:
                return 0.0
            return 0.4 if feature.fast_ma > feature.slow_ma and feature.momentum > 0 else 0.0
        if feature.zscore is None:
            return 0.0
        if current_weight > 1e-10:
            return 0.4 if feature.zscore < self.params["exit_z"] else 0.0
        return 0.4 if feature.zscore <= self.params["entry_z"] else 0.0


def make_strategy(name: str, params: dict[str, int | float] | None = None) -> BaselineStrategy:
    supplied = {} if params is None else params
    if not isinstance(supplied, dict) or any(not isinstance(k, str) for k in supplied):
        raise ValueError("Strategy parameters must be a JSON object with string keys.")
    defaults: dict[str, int | float]
    if name == "momentum":
        defaults = {"fast": 20, "slow": 50, "lookback": 20}
        hypothesis = "A trailing trend filter improves evaluation-period return over the same-risk constant-long comparator after costs."
        assumptions = (
            "Daily trends persist into the next bar.",
            "Open-price fills approximate executable liquidity.",
        )
        failures = (
            "Whipsaw in sideways regimes.",
            "Late exits after gaps.",
            "Costs consume small trend moves.",
        )
    elif name == "mean_reversion":
        defaults = {"lookback": 20, "entry_z": -1.0, "exit_z": 0.0}
        hypothesis = "Buying trailing downside deviations improves evaluation-period return over the same-risk constant-long comparator after costs."
        assumptions = (
            "Negative deviations revert before persistent drawdown.",
            "Trailing scale is informative in the next bar.",
        )
        failures = (
            "A falling market stays below its trailing mean.",
            "Volatility shifts invalidate z-scores.",
            "Small reversions disappear after costs.",
        )
    else:
        raise ValueError(f"Unknown strategy: {name}")
    if set(supplied) - set(defaults):
        raise ValueError(f"Unknown strategy parameters: {sorted(set(supplied) - set(defaults))}")
    merged = defaults | supplied
    for key, value in merged.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be finite.")
        if key in ("fast", "slow", "lookback") and (not isinstance(value, int) or value < 2):
            raise ValueError(f"{key} must be an integer >= 2.")
    if name == "momentum" and merged["fast"] >= merged["slow"]:
        raise ValueError("fast must be smaller than slow.")
    if name == "mean_reversion" and merged["entry_z"] >= merged["exit_z"]:
        raise ValueError("entry_z must be smaller than exit_z.")
    return BaselineStrategy(name, merged, hypothesis, assumptions, failures)
