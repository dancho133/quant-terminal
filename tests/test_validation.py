"""Input-boundary regressions reproduced during the BYTRADER preparation review."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quant_terminal.data import load_dataset
from quant_terminal.experiment import run_experiment
from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig
from quant_terminal.strategies import make_strategy


class ValidationTests(unittest.TestCase):
    def test_extreme_price_ratio_is_rejected_before_statistics(self):
        from datetime import UTC, datetime, timedelta

        from quant_terminal.features import build_features
        from quant_terminal.models import Bar

        bars = tuple(
            Bar(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i), p, p, p, p, 1)
            for i, p in enumerate((1e-308, 1e308, 1e308))
        )
        with self.assertRaisesRegex(ValueError, "numerical range"):
            build_features(bars, fast=2, slow=3, lookback=2)

    def test_gross_benchmark_normalizes_price_before_multiplying_capital(self):
        import math
        from datetime import UTC, datetime, timedelta

        from quant_terminal.backtest import simulate
        from quant_terminal.data import dataset_from_bars
        from quant_terminal.models import Bar
        from tests.test_backtest_risk import ScriptedStrategy

        data = dataset_from_bars(
            "BTCUSDT",
            tuple(
                Bar(
                    datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    1e308,
                    1e308,
                    1e308,
                    1e308,
                    1,
                )
                for i in range(3)
            ),
        )
        result = simulate(
            data, ScriptedStrategy([0]), ExperimentConfig(evaluation_end="2025-01-03")
        )
        self.assertTrue(all(math.isfinite(r["benchmark_equity"]) for r in result["ledger"]))
        self.assertEqual(result["metrics"]["benchmark_return"], 0)

    def test_noncanonical_or_nonstrings_dates_are_rejected_at_configuration(self):
        for value in ("20250101", "2025-W01-1", None, 20250101):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ExperimentConfig(evaluation_start=value)

    def test_requested_window_cannot_be_silently_clipped_to_dataset(self):
        for start, end in (("2022-01-01", "2025-12-31"), ("2025-01-01", "2026-01-01")):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "dataset"):
                run_experiment(ExperimentConfig(evaluation_start=start, evaluation_end=end))

    def test_nonnumeric_and_boolean_financial_configuration_is_rejected(self):
        for value in ("10", None, True, [], float("nan"), float("inf")):
            for constructor, field in (
                (CostModel, "fee_bps"),
                (CostModel, "slippage_bps"),
                (RiskConfig, "max_position"),
                (RiskConfig, "max_exposure"),
                (RiskConfig, "max_drawdown"),
                (ExperimentConfig, "initial_capital"),
            ):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    constructor(**{field: value})
        with self.assertRaises(ValueError):
            ExperimentConfig(periods_per_year=True)

    def test_parameters_must_be_a_mapping_with_string_keys(self):
        for value in ([], "", 1, {1: 10}, {"fast": 20, 1: 10}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_strategy("momentum", value)
            with self.subTest(config=value), self.assertRaises(ValueError):
                ExperimentConfig(params=value)

    def test_unterminated_csv_quote_is_not_a_valid_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                'timestamp,open,high,low,close,volume\n2025-01-01T00:00:00Z,100,101,99,100,"100\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "CSV"):
                load_dataset(path=path)

    def test_cli_rejects_window_mismatch_and_malformed_values_without_artifacts(self):
        cases = (
            ["--start", "20250101"],
            ["--start", "2022-01-01"],
            ["--end", "2026-01-01"],
            ["--params", "[]"],
            ["--params", '{"fast":true}'],
            ["--params", '{"entry_z":NaN}', "--strategy", "mean_reversion"],
            ["--fee-bps", "nan"],
            ["--initial-capital", "not-a-number"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            for index, args in enumerate(cases):
                output = Path(tmp) / f"out-{index}"
                with self.subTest(args=args):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "quant_terminal.run",
                            "--output",
                            str(output),
                            *args,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
