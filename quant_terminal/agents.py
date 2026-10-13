"""Future integration contracts. No autonomous or LLM agents are implemented.

A future strategy adapter must return a validated numerical target and must
remain subject to the same independent RiskManager. An LLM explanation cannot
authorize a fill, change limits, erase criticism, or create performance evidence.
"""

from __future__ import annotations

from typing import Any, Protocol

from quant_terminal.features import FeatureRow
from quant_terminal.models import Dataset


class ResearchAgent(Protocol):
    def propose(self, dataset: Dataset) -> dict[str, Any]: ...


class StrategyAgent(Protocol):
    def target(self, feature: FeatureRow, current_weight: float) -> float: ...


class RiskAgent(Protocol):
    def approve_order(
        self, quantity: float, cash: float, units: float, price: float, timestamp: str
    ) -> bool: ...


class CriticAgent(Protocol):
    def review(self, result: dict[str, Any], robustness: dict[str, Any]) -> dict[str, Any]: ...
