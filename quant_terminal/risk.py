"""Numerical risk authority. Strategies cannot bypass its order authorization."""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from quant_terminal.models import CostModel, RiskConfig


class RiskManager:
    def __init__(self, limits: RiskConfig, costs: CostModel, initial_capital: float) -> None:
        if not math.isfinite(initial_capital) or initial_capital <= 0:
            raise ValueError("Risk manager requires positive initial capital.")
        self.limits = limits
        self.costs = costs
        self.peak = initial_capital
        self.max_drawdown = 0.0
        self.halted = False
        self.events: list[dict[str, Any]] = []

    def record(
        self, timestamp: str, code: str, action: str, observed: Any, limit: Any, **extra: Any
    ) -> None:
        if isinstance(observed, float) and not math.isfinite(observed):
            observed = repr(observed)
        self.events.append(
            {
                "timestamp": timestamp,
                "code": code,
                "action": action,
                "observed": observed,
                "limit": limit,
                **extra,
            }
        )

    def observe_close(self, timestamp: str, equity: float, exposure: float) -> float:
        """Close sampling cannot bound losses through gaps or intrabar excursions."""
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("Nonpositive or non-finite portfolio equity.")
        self.peak = max(self.peak, equity)
        drawdown = max(0.0, 1 - equity / self.peak)
        self.max_drawdown = max(self.max_drawdown, drawdown)
        if exposure > self.limits.exposure_cap + 1e-9:
            self.record(
                timestamp,
                "EXPOSURE_DRIFT",
                "FLAG",
                exposure,
                self.limits.exposure_cap,
                reason="Close mark exceeded the cap; adjust next open.",
            )
        if drawdown >= self.limits.max_drawdown and not self.halted:
            self.halted = True
            self.record(
                timestamp,
                "DRAWDOWN_HALT",
                "HALT",
                drawdown,
                self.limits.max_drawdown,
                reason="Cancel entries; liquidate at the next open.",
            )
        return drawdown

    def constrain_target(self, target: float, timestamp: str) -> float | None:
        if not math.isfinite(target) or not 0 <= target <= 1:
            self.record(timestamp, "INVALID_TARGET", "REJECT", target, "[0, 1]")
            return None
        if self.halted:
            if target > 0:
                self.record(timestamp, "HALTED_ENTRY", "REJECT", target, 0, allowed=0)
            return 0.0
        allowed = min(target, self.limits.exposure_cap)
        if target > allowed:
            self.record(
                timestamp, "TARGET_CAPPED", "CAP", target, self.limits.exposure_cap, allowed=allowed
            )
        return allowed

    def quantity_for_target(self, weight: float, cash: float, units: float, price: float) -> float:
        """Solve weight against post-cost equity marked at the un-slipped open."""
        equity = cash + units * price
        difference = weight * equity - units * price
        if difference >= 0:
            expense = self.costs.fill_price(price, 1) * (1 + self.costs.fee_rate)
            return difference / (price + weight * (expense - price))
        proceeds = self.costs.fill_price(price, -1) * (1 - self.costs.fee_rate)
        sell_units = -difference / (price - weight * (price - proceeds))
        return -min(units, sell_units)

    def approve_order(
        self, quantity: float, cash: float, units: float, price: float, timestamp: str
    ) -> bool:
        inputs = (quantity, cash, units, price)
        code = None
        observed: Any = quantity
        limit: Any = None
        if any(not math.isfinite(v) for v in inputs) or price <= 0 or cash < -1e-8 or units < 0:
            code = "INVALID_ORDER"
        elif quantity > 0 and self.halted:
            code, limit = "HALTED_ENTRY", 0
        elif quantity < -units - 1e-10:
            code, limit = "SHORT_ORDER", units
        else:
            fill = self.costs.fill_price(price, quantity)
            fee = abs(quantity) * fill * self.costs.fee_rate
            next_cash = cash - quantity * fill - fee
            next_units = units + quantity
            equity = next_cash + next_units * price
            exposure = next_units * price / equity if equity > 0 else math.inf
            if next_cash < -1e-8 or equity <= 0:
                code, observed, limit = "INSUFFICIENT_CASH", next_cash, 0
            elif quantity > 0 and exposure > self.limits.exposure_cap + 1e-9:
                code, observed, limit = "EXPOSURE_LIMIT", exposure, self.limits.exposure_cap
        if code:
            self.record(
                timestamp,
                code,
                "REJECT",
                observed,
                limit,
                reason="Proposed order failed independent authorization.",
            )
            return False
        self.record(timestamp, "ORDER_APPROVED", "APPROVE", quantity, self.limits.exposure_cap)
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "limits": asdict(self.limits),
            "halted": self.halted,
            "max_observed_drawdown": self.max_drawdown,
            "events": self.events,
        }
