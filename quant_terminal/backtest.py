"""Single-asset daily simulator with explicit next-open fills and complete accounting."""

from __future__ import annotations

import math
from statistics import fmean, stdev
from typing import Any

from quant_terminal.data import validate_bars
from quant_terminal.features import build_features
from quant_terminal.models import Dataset, ExperimentConfig
from quant_terminal.risk import RiskManager
from quant_terminal.strategies import Strategy


def calculate_metrics(
    ledger: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    round_trips: list[dict[str, Any]],
    initial_capital: float,
    periods_per_year: int,
) -> dict[str, Any]:
    equities = [initial_capital, *(r["equity"] for r in ledger)]
    returns = [b / a - 1 for a, b in zip(equities[:-1], equities[1:], strict=True)]
    daily_sd = stdev(returns) if len(returns) >= 2 else 0.0
    fees = sum(f["fee"] for f in fills)
    slippage = sum(f["slippage_cost"] for f in fills)
    return {
        "total_return": equities[-1] / initial_capital - 1,
        "benchmark_return": ledger[-1]["benchmark_equity"] / initial_capital - 1,
        "max_drawdown": max(r["drawdown"] for r in ledger),
        "annualized_volatility": daily_sd * math.sqrt(periods_per_year),
        "sharpe_like": fmean(returns) / daily_sd * math.sqrt(periods_per_year)
        if daily_sd > 1e-15
        else None,
        "win_rate": sum(r["net_pnl"] > 0 for r in round_trips) / len(round_trips)
        if round_trips
        else None,
        "turnover": sum(f["quantity"] * f["price"] for f in fills) / initial_capital,
        "number_of_trades": len(round_trips),
        "fill_count": len(fills),
        "fees": fees,
        "slippage_cost": slippage,
        "transaction_costs": fees + slippage,
        "max_exposure": max(r["exposure"] for r in ledger),
        "average_exposure": fmean(r["exposure"] for r in ledger),
        "ending_equity": equities[-1],
        "evaluation_bars": len(ledger),
        "periods_per_year": periods_per_year,
    }


def simulate(dataset: Dataset, strategy: Strategy, config: ExperimentConfig) -> dict[str, Any]:
    validate_bars(dataset.bars)
    if dataset.asset != config.asset:
        raise ValueError("Dataset asset does not match experiment configuration.")
    if (
        config.evaluation_start < dataset.bars[0].timestamp.date().isoformat()
        or config.evaluation_end > dataset.bars[-1].timestamp.date().isoformat()
    ):
        raise ValueError("Evaluation dates must lie within the dataset; windows are never clipped.")
    indices = [
        i
        for i, b in enumerate(dataset.bars)
        if config.evaluation_start <= b.timestamp.date().isoformat() <= config.evaluation_end
    ]
    if len(indices) < 2:
        raise ValueError("Evaluation window needs at least two daily bars in the dataset.")
    features = build_features(
        dataset.bars,
        fast=int(strategy.params.get("fast", 20)),
        slow=int(strategy.params.get("slow", 50)),
        lookback=int(strategy.params.get("lookback", 20)),
    )
    gate = RiskManager(config.risk, config.costs, config.initial_capital)
    cash, units, unit_basis = config.initial_capital, 0.0, 0.0
    fills, ledger, episodes = [], [], []
    pending = None
    episode_start, episode_pnl = None, 0.0
    benchmark_entry = dataset.bars[indices[1]].open

    for local, index in enumerate(indices):
        bar = dataset.bars[index]
        timestamp = bar.timestamp.isoformat()
        if pending is not None:
            target = 0.0 if gate.halted else pending["allowed_target"]
            if target is not None:
                quantity = gate.quantity_for_target(target, cash, units, bar.open)
                # Ignore only immaterial rebalances; every nonzero liquidation must execute.
                opening_equity = cash + units * bar.open
                trade_required = quantity != 0 and (
                    target == 0 or abs(quantity) * bar.open > 1e-12 * opening_equity
                )
                if trade_required and gate.approve_order(
                    quantity, cash, units, bar.open, timestamp
                ):
                    old_units = units
                    fill_price = config.costs.fill_price(bar.open, quantity)
                    absolute = abs(quantity)
                    fee = absolute * fill_price * config.costs.fee_rate
                    slip = absolute * abs(fill_price - bar.open)
                    realized = None
                    if quantity > 0:
                        if old_units == 0:
                            episode_start, episode_pnl = timestamp, 0.0
                        unit_basis = (old_units * unit_basis + quantity * fill_price + fee) / (
                            old_units + quantity
                        )
                    else:
                        realized = absolute * (fill_price - unit_basis) - fee
                        episode_pnl += realized
                    cash -= quantity * fill_price + fee
                    units += quantity
                    if units == 0:
                        units = 0.0
                        episodes.append(
                            {
                                "entry_timestamp": episode_start,
                                "exit_timestamp": timestamp,
                                "net_pnl": episode_pnl,
                            }
                        )
                        unit_basis, episode_start, episode_pnl = 0.0, None, 0.0
                    if -1e-12 * opening_equity <= cash < 0:
                        cash = 0.0
                    if cash < 0 or units < 0:
                        raise ArithmeticError(
                            "Portfolio accounting violated no-borrowing/no-short invariants."
                        )
                    fills.append(
                        {
                            "timestamp": timestamp,
                            "signal_timestamp": pending["signal_timestamp"],
                            "side": "BUY" if quantity > 0 else "SELL",
                            "quantity": absolute,
                            "reference_price": bar.open,
                            "price": fill_price,
                            "fee": fee,
                            "slippage_cost": slip,
                            "realized_pnl": realized,
                            "requested_target": pending["requested_target"],
                            "allowed_target": target,
                            "reason": "drawdown_liquidation" if gate.halted else pending["reason"],
                            "cash_after": cash,
                            "units_after": units,
                        }
                    )
        equity = cash + units * bar.close
        exposure = units * bar.close / equity
        drawdown = gate.observe_close(timestamp, equity, exposure)
        ledger.append(
            {
                "timestamp": timestamp,
                "close": bar.close,
                "cash": cash,
                "units": units,
                "equity": equity,
                "drawdown": drawdown,
                "exposure": exposure,
                "benchmark_equity": config.initial_capital
                if local == 0
                else config.initial_capital * (bar.close / benchmark_entry),
            }
        )
        requested = strategy.target(features[index], exposure)
        allowed = gate.constrain_target(requested, timestamp)
        pending = {
            "signal_timestamp": timestamp,
            "requested_target": requested,
            "allowed_target": allowed,
            "reason": "drawdown_liquidation" if gate.halted else "strategy_target",
        }
    assert pending is not None
    pending["status"] = "unfilled_end_of_data"
    pending["requires_trade"] = (
        pending["allowed_target"] is not None
        and abs(pending["allowed_target"] - ledger[-1]["exposure"]) > 1e-9
    )
    final = ledger[-1]
    ending = {
        "units": units,
        "cash": cash,
        "mark_price": final["close"],
        "market_value": units * final["close"],
        "cost_basis": units * unit_basis,
        "unrealized_pnl": units * (final["close"] - unit_basis),
        "partial_episode_realized_pnl": episode_pnl,
        "episode_entry": episode_start,
        "estimated_exit_cost": units
        * final["close"]
        * (config.costs.slippage_rate + config.costs.fee_rate * (1 - config.costs.slippage_rate)),
        "status": "open_marked_position" if units > 0 else "flat",
    }
    return {
        "metrics": calculate_metrics(
            ledger, fills, episodes, config.initial_capital, config.periods_per_year
        ),
        "ledger": ledger,
        "fills": fills,
        "round_trips": episodes,
        "risk": gate.summary(),
        "ending_position": ending,
        "pending_order": pending,
    }
