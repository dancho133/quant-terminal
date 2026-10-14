"""Offline reviewer command: execute both CLIs and independently reconcile their exports."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from quant_terminal import __version__
from quant_terminal.backtest import simulate
from quant_terminal.critic import review
from quant_terminal.data import load_dataset
from quant_terminal.experiment import (
    ConstantLong,
    engine_fingerprint,
    experiment_identity,
    normalized_config,
)
from quant_terminal.features import build_features
from quant_terminal.models import CostModel, Dataset, ExperimentConfig, RiskConfig
from quant_terminal.strategies import make_strategy

REL_TOL = 1e-10
ABS_TOL = 1e-10
STRATEGIES = ("momentum", "mean_reversion")
FILES = (
    "experiment.json",
    "report.html",
    "report.md",
    "equity.svg",
    "drawdown.svg",
    "exposure.svg",
    "trades.csv",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close(actual: float, expected: float, name: str) -> None:
    require(type(actual) in (int, float), f"{name}: expected a number, not {type(actual).__name__}")
    require(
        math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL),
        f"{name}: {actual!r} != {expected!r}",
    )


def compare_numerical(actual: Any, expected: Any, path: str = "artifact") -> None:
    """Exact structure/labels/integers; tolerant floats; ignore only Python-version metadata."""
    if path == "artifact.reproducibility.python":
        return
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(actual.keys() == expected.keys(), f"{path}: object keys differ")
        for key in actual:
            compare_numerical(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, list) and isinstance(expected, list):
        require(len(actual) == len(expected), f"{path}: list lengths differ")
        for index, (one, two) in enumerate(zip(actual, expected, strict=True)):
            compare_numerical(one, two, f"{path}[{index}]")
    elif isinstance(actual, float) or isinstance(expected, float):
        require(
            type(actual) in (int, float) and type(expected) in (int, float),
            f"{path}: numeric types differ",
        )
        close(actual, expected, path)
    else:
        require(type(actual) is type(expected) and actual == expected, f"{path}: values differ")


def finite_tree(value: Any, path: str = "artifact") -> None:
    if isinstance(value, float):
        require(math.isfinite(value), f"{path}: non-finite number")
    elif isinstance(value, dict):
        for key, child in value.items():
            finite_tree(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            finite_tree(child, f"{path}[{index}]")


def reconcile(
    result: dict[str, Any], dataset: Dataset, config: ExperimentConfig, comparator: bool
) -> None:
    """Replay exported fills without calling simulate, RiskManager or calculate_metrics."""
    bars = [
        b
        for b in dataset.bars
        if config.evaluation_start <= b.timestamp.date().isoformat() <= config.evaluation_end
    ]
    rows, fills = result["ledger"], result["fills"]
    require(len(rows) == len(bars) >= 2, "evaluation calendar mismatch")
    require(result["risk"]["limits"] == asdict(config.risk), "risk limits mismatch")
    strategy = ConstantLong() if comparator else make_strategy(config.strategy, config.params)
    features = build_features(
        dataset.bars,
        fast=int(strategy.params.get("fast", 20)),
        slow=int(strategy.params.get("slow", 50)),
        lookback=int(strategy.params.get("lookback", 20)),
    )
    feature_map = dict(zip((b.timestamp.isoformat() for b in dataset.bars), features, strict=True))
    cash, units, basis, realized, partial = config.initial_capital, 0.0, 0.0, 0.0, 0.0
    peak, halted, entry, previous_target = cash, False, None, None
    cap = config.risk.exposure_cap
    cursor, episodes = 0, []
    fees, slippage, turnover = 0.0, 0.0, 0.0
    equities = [cash]
    for index, (bar, row) in enumerate(zip(bars, rows, strict=True)):
        timestamp = bar.timestamp.isoformat()
        require(row["timestamp"] == timestamp, "ledger timestamp mismatch")
        count = 0
        while cursor < len(fills) and fills[cursor]["timestamp"] == timestamp:
            fill = fills[cursor]
            require(
                index > 0 and fill["signal_timestamp"] == rows[index - 1]["timestamp"],
                "fill must follow the prior close",
            )
            require(
                fill["side"] in ("BUY", "SELL") and fill["quantity"] > 0,
                "invalid fill side/quantity",
            )
            require(not halted or fill["side"] == "SELL", "entry after drawdown halt")
            sign = 1 if fill["side"] == "BUY" else -1
            quantity = fill["quantity"]
            price = bar.open * (1 + sign * config.costs.slippage_bps / 10000)
            fee = quantity * price * config.costs.fee_bps / 10000
            slip = quantity * abs(price - bar.open)
            close(fill["reference_price"], bar.open, "opening reference price")
            close(fill["price"], price, "adverse fill price")
            close(fill["fee"], fee, "fee on slipped notional")
            close(fill["slippage_cost"], slip, "slippage cost")
            close(fill["requested_target"], previous_target, "requested target")
            close(
                fill["allowed_target"], 0 if halted else min(previous_target, cap), "allowed target"
            )
            require(
                fill["reason"] == ("drawdown_liquidation" if halted else "strategy_target"),
                "fill reason mismatch",
            )
            if sign > 0:
                require(fill["realized_pnl"] is None, "buy cannot realize sale PnL")
                if units == 0:
                    entry, partial = timestamp, 0.0
                basis = (units * basis + quantity * price + fee) / (units + quantity)
            else:
                require(quantity <= units, "short sale")
                pnl = quantity * (price - basis) - fee
                close(fill["realized_pnl"], pnl, "sale realized PnL")
                realized += pnl
                partial += pnl
            cash -= sign * quantity * price + fee
            units += sign * quantity
            if units == 0:
                episodes.append(
                    {"entry_timestamp": entry, "exit_timestamp": timestamp, "net_pnl": partial}
                )
                basis, partial, entry = 0.0, 0.0, None
            require(cash >= -ABS_TOL and units >= 0, "borrowing or negative holdings")
            close(fill["cash_after"], cash, "post-fill cash")
            close(fill["units_after"], units, "post-fill units")
            fees, slippage, turnover = fees + fee, slippage + slip, turnover + quantity * price
            count, cursor = count + 1, cursor + 1
        require(count <= 1, "more than one fill per daily target")
        opening_equity = cash + units * bar.open
        if index:
            if halted or previous_target == 0:
                require(units == 0, "zero-target liquidation must execute even at tiny notional")
            close(
                units * bar.open / opening_equity,
                0 if halted else min(previous_target, cap),
                "post-fill target exposure (or immaterial rebalance)",
            )
        equity = cash + units * bar.close
        peak = max(peak, equity)
        drawdown, exposure = max(0.0, 1 - equity / peak), units * bar.close / equity
        for name, expected in {
            "close": bar.close,
            "cash": cash,
            "units": units,
            "equity": equity,
            "drawdown": drawdown,
            "exposure": exposure,
            "benchmark_equity": config.initial_capital
            if index == 0
            else config.initial_capital * (bar.close / bars[1].open),
        }.items():
            close(row[name], expected, f"ledger {timestamp} {name}")
        halted = halted or equity <= peak * (1 - config.risk.max_drawdown)
        previous_target = strategy.target(feature_map[timestamp], exposure)
        equities.append(equity)
    require(cursor == len(fills), "fill outside evaluation calendar or unordered fills")
    require(result["risk"]["halted"] is halted, "drawdown latch mismatch")
    require(
        len([e for e in result["risk"]["events"] if e["code"] == "ORDER_APPROVED"]) == len(fills),
        "fill/approval count mismatch",
    )
    compare_numerical(result["round_trips"], episodes, "episodes")
    ending = result["ending_position"]
    for name, expected in {
        "cash": cash,
        "units": units,
        "mark_price": bars[-1].close,
        "market_value": units * bars[-1].close,
        "cost_basis": units * basis,
        "unrealized_pnl": units * (bars[-1].close - basis),
        "partial_episode_realized_pnl": partial,
        "estimated_exit_cost": units
        * bars[-1].close
        * (config.costs.slippage_rate + config.costs.fee_rate * (1 - config.costs.slippage_rate)),
    }.items():
        close(ending[name], expected, f"ending {name}")
    close(
        equities[-1] - config.initial_capital,
        realized + ending["unrealized_pnl"],
        "realized + unrealized = equity change",
    )
    require(
        ending["status"] == ("open_marked_position" if units > 0 else "flat")
        and ending["episode_entry"] == entry,
        "terminal position state",
    )
    pending = result["pending_order"]
    require(
        pending["status"] == "unfilled_end_of_data"
        and pending["signal_timestamp"] == rows[-1]["timestamp"],
        "terminal pending order",
    )
    close(pending["requested_target"], previous_target, "terminal proposal")
    close(
        pending["allowed_target"],
        0 if halted else min(previous_target, cap),
        "terminal risk target",
    )
    close(
        result["risk"]["max_observed_drawdown"],
        max(r["drawdown"] for r in rows),
        "risk maximum drawdown",
    )
    expected_events = []
    event_peak, event_halted = config.initial_capital, False
    for row in rows:
        timestamp = row["timestamp"]
        for fill in fills:
            if fill["timestamp"] == timestamp:
                expected_events.append(
                    {
                        "timestamp": timestamp,
                        "code": "ORDER_APPROVED",
                        "action": "APPROVE",
                        "observed": fill["quantity"] * (1 if fill["side"] == "BUY" else -1),
                        "limit": cap,
                    }
                )
        if row["exposure"] > cap + 1e-9:
            expected_events.append(
                {
                    "timestamp": timestamp,
                    "code": "EXPOSURE_DRIFT",
                    "action": "FLAG",
                    "observed": row["exposure"],
                    "limit": cap,
                }
            )
        event_peak = max(event_peak, row["equity"])
        if not event_halted and row["equity"] <= event_peak * (1 - config.risk.max_drawdown):
            event_halted = True
            expected_events.append(
                {
                    "timestamp": timestamp,
                    "code": "DRAWDOWN_HALT",
                    "action": "HALT",
                    "observed": row["drawdown"],
                    "limit": config.risk.max_drawdown,
                }
            )
        target = strategy.target(feature_map[timestamp], row["exposure"])
        if event_halted and target > 0:
            expected_events.append(
                {
                    "timestamp": timestamp,
                    "code": "HALTED_ENTRY",
                    "action": "REJECT",
                    "observed": target,
                    "limit": 0,
                    "allowed": 0,
                }
            )
        elif not event_halted and target > cap:
            expected_events.append(
                {
                    "timestamp": timestamp,
                    "code": "TARGET_CAPPED",
                    "action": "CAP",
                    "observed": target,
                    "limit": cap,
                    "allowed": cap,
                }
            )
    events = result["risk"]["events"]
    require(len(events) == len(expected_events), "risk event count mismatch")
    for event, expected in zip(events, expected_events, strict=True):
        for key, value in expected.items():
            if isinstance(value, (float, int)):
                close(event[key], value, f"risk event {key}")
            else:
                require(event[key] == value, f"risk event {key} mismatch")
    require(
        pending["reason"] == ("drawdown_liquidation" if halted else "strategy_target"),
        "terminal pending reason",
    )
    require(
        pending["requires_trade"] is (abs(pending["allowed_target"] - rows[-1]["exposure"]) > 1e-9),
        "terminal requires_trade flag",
    )
    returns = [b / a - 1 for a, b in zip(equities[:-1], equities[1:], strict=True)]
    sd = statistics.stdev(returns)
    expected_metrics = {
        "total_return": equities[-1] / config.initial_capital - 1,
        "benchmark_return": rows[-1]["benchmark_equity"] / config.initial_capital - 1,
        "ending_equity": equities[-1],
        "fees": fees,
        "slippage_cost": slippage,
        "transaction_costs": fees + slippage,
        "turnover": turnover / config.initial_capital,
        "max_drawdown": max(r["drawdown"] for r in rows),
        "max_exposure": max(r["exposure"] for r in rows),
        "average_exposure": statistics.fmean(r["exposure"] for r in rows),
        "annualized_volatility": sd * math.sqrt(config.periods_per_year),
        "evaluation_bars": len(rows),
        "fill_count": len(fills),
        "number_of_trades": len(episodes),
        "periods_per_year": config.periods_per_year,
    }
    for name, expected in expected_metrics.items():
        close(result["metrics"][name], expected, f"metric {name}")
    for name, expected in {
        "win_rate": sum(e["net_pnl"] > 0 for e in episodes) / len(episodes) if episodes else None,
        "sharpe_like": statistics.fmean(returns) / sd * math.sqrt(config.periods_per_year)
        if sd > 1e-15
        else None,
    }.items():
        if expected is None:
            require(result["metrics"][name] is None, f"undefined metric {name} must be null")
        else:
            close(result["metrics"][name], expected, f"metric {name}")


def check_artifact(
    artifact: dict[str, Any], dataset: Dataset, config: ExperimentConfig
) -> list[dict[str, Any]]:
    config = normalized_config(config)
    checks = []

    def check(name: str, operation: Any) -> None:
        try:
            operation()
            checks.append({"name": name, "passed": True})
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            ArithmeticError,
            AttributeError,
        ) as exc:
            checks.append({"name": name, "passed": False, "detail": str(exc)})

    def identity() -> None:
        require(
            type(artifact["schema_version"]) is int and artifact["schema_version"] == 1,
            "unsupported schema",
        )
        require(artifact["engine_version"] == __version__, "engine version mismatch")
        raw = artifact["config"]
        exported_config = normalized_config(
            ExperimentConfig(
                **(raw | {"risk": RiskConfig(**raw["risk"]), "costs": CostModel(**raw["costs"])})
            )
        )
        require(
            asdict(exported_config) == asdict(config),
            "exported configuration input contract mismatch",
        )
        require(artifact["config"] == asdict(config), "configuration mismatch")
        require(artifact["engine"] == engine_fingerprint(), "numerical engine identity mismatch")
        require(
            artifact["experiment_id"] == experiment_identity(config, dataset),
            "experiment identity mismatch",
        )
        require(
            artifact["dataset"]["sha256"] == dataset.sha256
            and artifact["dataset"]["provenance"] == dataset.provenance,
            "dataset identity mismatch",
        )
        require(
            artifact["strategy"]["name"] == config.strategy
            and artifact["strategy"]["parameters"] == config.params,
            "strategy configuration mismatch",
        )
        require(
            artifact["dataset"]["evaluation_start"][:10] == config.evaluation_start
            and artifact["dataset"]["evaluation_end"][:10] == config.evaluation_end,
            "actual/requested dates mismatch",
        )

        selected = [
            b
            for b in dataset.bars
            if config.evaluation_start <= b.timestamp.date().isoformat() <= config.evaluation_end
        ]
        expected_data = {
            "asset": dataset.asset,
            "interval": "1d",
            "rows": len(dataset.bars),
            "start": dataset.bars[0].timestamp.isoformat(),
            "end": dataset.bars[-1].timestamp.isoformat(),
            "evaluation_start": selected[0].timestamp.isoformat(),
            "evaluation_end": selected[-1].timestamp.isoformat(),
            "prior_context_bars": sum(b.timestamp < selected[0].timestamp for b in dataset.bars),
        }
        require(
            all(artifact["dataset"][key] == value for key, value in expected_data.items()),
            "dataset metadata mismatch",
        )

    def robustness() -> None:
        robust = artifact["robustness"]
        costs = robust["cost_scenarios"]

        def scenario_metrics(scenario: dict[str, Any], scenario_config: ExperimentConfig) -> None:
            outcome = simulate(
                dataset,
                make_strategy(scenario_config.strategy, scenario_config.params),
                scenario_config,
            )
            reconcile(outcome, dataset, scenario_config, False)
            for metric, value in outcome["metrics"].items():
                compare_numerical(scenario[metric], value, f"scenario {metric}")

        require(
            [(s["name"], s["cost_multiplier"]) for s in costs]
            == [("zero_cost", 0), ("base_cost", 1), ("double_cost", 2)],
            "cost scenario structure",
        )
        for name, value in costs[1].items():
            if name in artifact["result"]["metrics"]:
                compare_numerical(value, artifact["result"]["metrics"][name], f"base-cost {name}")
        for factor, scenario in enumerate(costs):
            scenario_metrics(
                scenario,
                replace(
                    config,
                    costs=replace(
                        config.costs,
                        fee_bps=config.costs.fee_bps * factor,
                        slippage_bps=config.costs.slippage_bps * factor,
                    ),
                ),
            )
        variants = robust["parameter_variants"]
        require(len(variants) == 2, "two fixed parameter variants required")
        key = "fast" if config.strategy == "momentum" else "lookback"
        for factor, variant in zip((0.8, 1.2), variants, strict=True):
            value = max(2, round(config.params[key] * factor))
            if key == "fast":
                value = min(value, config.params["slow"] - 1)
            require(
                variant["params"] == config.params | {key: value}
                and variant["nominal_multiplier"] == factor,
                "fixed neighbor configuration",
            )
            scenario_metrics(variant, replace(config, params=variant["params"]))
        rows = artifact["result"]["ledger"]
        windows = robust["time_windows"]
        require(len(windows) == 2, "two chronological reset windows required for the default demo")
        mid = len(rows) // 2
        require(
            [(s["start"], s["end"]) for s in windows]
            == [
                (rows[0]["timestamp"][:10], rows[mid - 1]["timestamp"][:10]),
                (rows[mid]["timestamp"][:10], rows[-1]["timestamp"][:10]),
            ],
            "chronological window boundaries",
        )
        for window in windows:
            scenario_metrics(
                window,
                replace(config, evaluation_start=window["start"], evaluation_end=window["end"]),
            )
        close(
            artifact["result"]["metrics"]["same_risk_benchmark_return"],
            artifact["comparator"]["metrics"]["total_return"],
            "same-risk comparator return",
        )
        require(
            artifact["critic"] == review(artifact["result"], robust),
            "critic does not match declared screening rules",
        )

    check("finite_numbers", lambda: finite_tree(artifact))
    check("configuration_and_identity", identity)
    check(
        "strategy_accounting_causality_risk",
        lambda: reconcile(artifact["result"], dataset, config, False),
    )
    check(
        "comparator_accounting_causality_risk",
        lambda: reconcile(artifact["comparator"], dataset, config, True),
    )
    check("robustness_and_critic", robustness)
    return checks


def check_exports(folder: Path, artifact: dict[str, Any]) -> None:
    require(
        all((folder / name).is_file() and (folder / name).stat().st_size > 0 for name in FILES),
        "missing/empty exported artifact",
    )
    for name in ("equity.svg", "drawdown.svg", "exposure.svg"):
        require(
            ElementTree.parse(folder / name).getroot().tag == "{http://www.w3.org/2000/svg}svg",
            f"invalid SVG: {name}",
        )
    for name in ("report.html", "report.md"):
        text = (folder / name).read_text(encoding="utf-8")
        require(
            artifact["experiment_id"] in text and artifact["critic"]["verdict"] in text,
            f"report identity/verdict: {name}",
        )
        if name.endswith("html"):
            require(
                text.count("<svg") == 3
                and not re.search(r'<(?:script|img|link)\b[^>]*(?:src|href)=["\']https?://', text),
                "HTML report must contain three embedded figures without external assets",
            )
    with (folder / "trades.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, strict=True))
    require(len(rows) == len(artifact["result"]["fills"]), "CSV fill count")
    for row, fill in zip(rows, artifact["result"]["fills"], strict=True):
        require(row.keys() == fill.keys(), "CSV fill columns")
        for key, value in fill.items():
            if value is None:
                require(row[key] == "", f"CSV null {key}")
            elif isinstance(value, (int, float)):
                close(float(row[key]), value, f"CSV {key}")
            else:
                require(row[key] == value, f"CSV {key}")


def commit_context(declared: str | None) -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    if (root / ".git").exists():
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
        )
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
        )
        if commit.returncode == 0 and status.returncode == 0:
            return {
                "checked_commit": commit.stdout.strip(),
                "commit_source": "git",
                "worktree_dirty": bool(status.stdout),
            }
    return {
        "checked_commit": declared,
        "commit_source": "declared-wheel-source" if declared else "unavailable",
        "worktree_dirty": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute and verify both historical baselines offline. REJECT is a valid research result."
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/review"))
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate existing exports without regenerating them.",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        help="Compare canonical JSON against the same engine/data on another platform.",
    )
    parser.add_argument(
        "--checked-commit",
        help="Declare source commit when a wheel has no Git checkout; explicitly marked as declared.",
    )
    args = parser.parse_args()
    if args.checked_commit and not re.fullmatch(r"[0-9a-f]{40}", args.checked_commit):
        parser.error("--checked-commit must be a full lowercase Git SHA")
    args.output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "checked_commit": args.checked_commit,
        "commit_source": "unavailable",
        "worktree_dirty": None,
        "engine_hash": None,
        "dataset_hash": None,
        "commands": [],
        "checks": [],
        "failures": [],
        "artifact_paths": {},
        "hypothesis_verdicts": {},
        "numeric_comparison": {
            "relative_tolerance": REL_TOL,
            "absolute_tolerance": ABS_TOL,
            "ignored_json_paths": ["reproducibility.python"],
            "figures": "structure only; never byte equality",
        },
    }
    try:
        summary.update(commit_context(args.checked_commit))
        summary["engine_hash"] = engine_fingerprint()["sha256"]
        dataset = load_dataset()
        summary["dataset_hash"] = dataset.sha256
    except (ValueError, OSError, TypeError, ArithmeticError) as exc:
        summary["failures"].append({"check": "initialization", "detail": str(exc)})
        (args.output / "verification.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Technical verification: FAILED · initialization: {exc}")
        raise SystemExit(1) from None
    for name in STRATEGIES:
        config = ExperimentConfig(strategy=name)
        folder = args.output / experiment_identity(config, dataset)
        summary["artifact_paths"][name] = str(folder.resolve())
        if not args.check_only:
            command = [
                sys.executable,
                "-m",
                "quant_terminal.run",
                "--strategy",
                name,
                "--output",
                str(args.output.resolve()),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            summary["commands"].append({"argv": command, "exit_code": result.returncode})
            (args.output / f"{name}-cli.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            if result.returncode:
                summary["failures"].append(
                    {
                        "strategy": name,
                        "check": "cli_execution",
                        "detail": f"exit {result.returncode}; see {name}-cli.log",
                    }
                )
                continue
        try:
            artifact = json.loads((folder / "experiment.json").read_text(encoding="utf-8"))
            checks = check_artifact(artifact, dataset, config)
            check_exports(folder, artifact)
            checks.append({"name": "export_structure_and_csv", "passed": True})
            if args.reference_dir:
                reference = json.loads(
                    (args.reference_dir / folder.name / "experiment.json").read_text(
                        encoding="utf-8"
                    )
                )
                compare_numerical(artifact, reference)
                checks.append({"name": "cross_environment_numeric_comparison", "passed": True})
            summary["hypothesis_verdicts"][name] = artifact["critic"]["verdict"]
            for check in checks:
                summary["checks"].append({"strategy": name, **check})
                if not check["passed"]:
                    summary["failures"].append({"strategy": name, **check})
        except (
            ValueError,
            OSError,
            TypeError,
            KeyError,
            IndexError,
            AttributeError,
            ArithmeticError,
            ElementTree.ParseError,
            csv.Error,
        ) as exc:
            summary["failures"].append(
                {
                    "strategy": name,
                    "check": "artifact_read_export_or_comparison",
                    "detail": str(exc),
                }
            )
    path = args.output / "verification.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        f"Technical verification: {'FAILED' if summary['failures'] else 'PASSED'} · {len(summary['checks'])} checks · {path.resolve()}"
    )
    for name, verdict in summary["hypothesis_verdicts"].items():
        print(f"{name}: hypothesis {verdict} (separate from technical verification)")
    raise SystemExit(1 if summary["failures"] else 0)


if __name__ == "__main__":
    main()
