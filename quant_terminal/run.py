"""CLI: execute an experiment and export the same canonical artifact used by the UI."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from quant_terminal.data import load_dataset
from quant_terminal.experiment import run_experiment
from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig
from quant_terminal.reports import write_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Historical research simulation. No live trading.")
    parser.add_argument("--strategy", choices=("momentum", "mean_reversion"), default="momentum")
    parser.add_argument("--asset", default="BTCUSDT")
    parser.add_argument("--initial-capital", type=float, default=10000)
    parser.add_argument("--fee-bps", type=float, default=10)
    parser.add_argument("--slippage-bps", type=float, default=5)
    parser.add_argument("--max-position", type=float, default=0.25)
    parser.add_argument("--max-exposure", type=float, default=0.50)
    parser.add_argument("--max-drawdown", type=float, default=0.20)
    parser.add_argument("--start", default="2025-01-01", help="Evaluation start YYYY-MM-DD.")
    parser.add_argument("--end", default="2025-12-31", help="Evaluation end YYYY-MM-DD.")
    parser.add_argument("--params", default="{}", help="Strategy parameter JSON object.")
    parser.add_argument("--data", type=Path, help="Optional validated daily OHLCV CSV.")
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        params = json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("--params must be a JSON object.")
        config = ExperimentConfig(
            args.strategy,
            args.asset,
            args.initial_capital,
            params,
            RiskConfig(args.max_position, args.max_exposure, args.max_drawdown),
            CostModel(args.fee_bps, args.slippage_bps),
            args.start,
            args.end,
        )
        artifact = run_experiment(config, load_dataset(args.asset, args.data))
        folder = write_artifacts(artifact, args.output)
    except (ValueError, OSError, ArithmeticError) as exc:
        parser.exit(2, f"Experiment failed: {exc}\n")
    metrics = artifact["result"]["metrics"]
    print(f"Experiment {artifact['experiment_id']} | {args.strategy} | {args.asset}")
    print(
        f"Evaluation: {artifact['dataset']['evaluation_start'][:10]} .. {artifact['dataset']['evaluation_end'][:10]}"
    )
    print(
        f"Return {metrics['total_return']:+.2%} | same-risk comparator {metrics['same_risk_benchmark_return']:+.2%} | gross buy-and-hold {metrics['benchmark_return']:+.2%}"
    )
    print(
        f"Max drawdown {metrics['max_drawdown']:.2%} | closed episodes {metrics['number_of_trades']} | fills {metrics['fill_count']} | costs {metrics['transaction_costs']:.2f} USDT"
    )
    print(f"Critic {artifact['critic']['verdict']}: {artifact['critic']['conclusion']}")
    print(f"Artifacts: {folder.resolve()}")


if __name__ == "__main__":
    main()
