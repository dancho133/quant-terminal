"""Small typed contracts shared by numerical modules."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


def finite_number(value: Any) -> bool:
    """Financial inputs are real numbers, never booleans or implicit string conversions."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Dataset:
    asset: str
    bars: tuple[Bar, ...]
    sha256: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CostModel:
    fee_bps: float = 10.0
    slippage_bps: float = 5.0

    def __post_init__(self) -> None:
        for name in ("fee_bps", "slippage_bps"):
            value = getattr(self, name)
            if not finite_number(value) or not 0 <= value < 10_000:
                raise ValueError(f"{name} must be finite and in [0, 10000).")

    @property
    def fee_rate(self) -> float:
        return self.fee_bps / 10_000

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000

    def fill_price(self, reference: float, quantity: float) -> float:
        return reference * (1 + self.slippage_rate * (1 if quantity > 0 else -1))


@dataclass(frozen=True)
class RiskConfig:
    max_position: float = 0.25
    max_exposure: float = 0.50
    max_drawdown: float = 0.20

    def __post_init__(self) -> None:
        for name in ("max_position", "max_exposure", "max_drawdown"):
            value = getattr(self, name)
            if not finite_number(value) or not 0 < value <= 1:
                raise ValueError(f"{name} must be finite and in (0, 1].")

    @property
    def exposure_cap(self) -> float:
        return min(self.max_position, self.max_exposure)


@dataclass(frozen=True)
class ExperimentConfig:
    strategy: str = "momentum"
    asset: str = "BTCUSDT"
    initial_capital: float = 10_000.0
    params: dict[str, int | float] = field(default_factory=dict)
    risk: RiskConfig = field(default_factory=RiskConfig)
    costs: CostModel = field(default_factory=CostModel)
    evaluation_start: str = "2025-01-01"
    evaluation_end: str = "2025-12-31"
    periods_per_year: int = 365

    def __post_init__(self) -> None:
        if not finite_number(self.initial_capital) or self.initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive.")
        if self.strategy not in ("momentum", "mean_reversion"):
            raise ValueError("strategy must be momentum or mean_reversion.")
        if (
            not isinstance(self.asset, str)
            or not self.asset
            or not self.asset.isalnum()
            or self.asset != self.asset.upper()
        ):
            raise ValueError("asset must be an uppercase alphanumeric symbol.")
        if not isinstance(self.params, dict) or any(not isinstance(k, str) for k in self.params):
            raise ValueError("Strategy parameters must be a JSON object with string keys.")
        if not isinstance(self.risk, RiskConfig) or not isinstance(self.costs, CostModel):
            raise ValueError("risk and costs must use the validated configuration contracts.")
        try:
            start, end = (
                date.fromisoformat(self.evaluation_start),
                date.fromisoformat(self.evaluation_end),
            )
        except (ValueError, TypeError) as exc:
            raise ValueError("Evaluation dates must use YYYY-MM-DD.") from exc
        if start.isoformat() != self.evaluation_start or end.isoformat() != self.evaluation_end:
            raise ValueError("Evaluation dates must use YYYY-MM-DD.")
        if start >= end:
            raise ValueError("evaluation_start must precede evaluation_end.")
        if type(self.periods_per_year) is not int or self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be a positive integer.")
