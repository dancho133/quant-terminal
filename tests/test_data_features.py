"""Regression checks: malformed data, trailing-only features and hypothesis state."""

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta


def bars_at(prices):
    from quant_terminal.models import Bar

    return tuple(
        Bar(datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i), p, p + 1, p - 1, p, 100 + i)
        for i, p in enumerate(prices)
    )


class DataFeatureTests(unittest.TestCase):
    def test_ohlcv_rejects_nonfinite_and_impossible_ranges(self):
        from quant_terminal.data import validate_bars

        good = bars_at([100, 101, 102])
        for damaged in (
            replace(good[1], close=float("nan")),
            replace(good[1], volume=-1),
            replace(good[1], high=90),
            replace(good[1], low=110),
            replace(good[1], open=0),
        ):
            with self.subTest(damaged=damaged), self.assertRaises(ValueError):
                validate_bars((good[0], damaged, good[2]))

    def test_daily_schema_rejects_missing_duplicate_and_unordered_bars(self):
        from quant_terminal.data import validate_bars

        good = bars_at([100, 101, 102])
        for rows in ((good[0], good[2]), (good[0], good[0]), tuple(reversed(good)), ()):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_bars(rows)

    def test_features_use_trailing_values_and_preserve_prefix(self):
        from quant_terminal.features import build_features

        first = bars_at([100, 110, 121, 100])
        result = build_features(first, fast=2, slow=3, lookback=2)
        self.assertIsNone(result[0].fast_ma)
        self.assertIsNone(result[0].return_1)
        self.assertAlmostEqual(result[1].return_1, 0.1)
        self.assertAlmostEqual(result[2].fast_ma, 115.5)
        self.assertAlmostEqual(result[2].slow_ma, 110.33333333333333)
        self.assertAlmostEqual(result[2].momentum, 0.21)
        self.assertAlmostEqual(result[2].volatility, 0.0)
        self.assertAlmostEqual(result[1].volume_change, 0.01)
        changed = first[:3] + (replace(first[3], close=10000, high=10001, open=10000),)
        self.assertEqual(result[:3], build_features(changed, fast=2, slow=3, lookback=2)[:3])
        self.assertEqual(result[:3], build_features(first[:3], fast=2, slow=3, lookback=2))

    def test_strategy_is_flat_during_warmup_and_has_stateful_exit(self):
        from quant_terminal.features import FeatureRow
        from quant_terminal.strategies import make_strategy

        momentum = make_strategy("momentum", {"fast": 2, "slow": 3, "lookback": 2})
        self.assertEqual(momentum.target(FeatureRow(), 0), 0)
        self.assertEqual(
            momentum.target(FeatureRow(fast_ma=110, slow_ma=100, momentum=0.1), 0), 0.4
        )
        self.assertEqual(
            momentum.target(FeatureRow(fast_ma=90, slow_ma=100, momentum=-0.1), 0.2), 0
        )
        reversion = make_strategy("mean_reversion", {"lookback": 3})
        self.assertEqual(reversion.target(FeatureRow(zscore=-2), 0), 0.4)
        self.assertEqual(reversion.target(FeatureRow(zscore=-0.2), 0.2), 0.4)
        self.assertEqual(reversion.target(FeatureRow(zscore=0.1), 0.2), 0)

    def test_parameters_reject_bad_windows_and_nonfinite_risk(self):
        from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig
        from quant_terminal.strategies import make_strategy

        for params in ({"fast": 0}, {"fast": 50, "slow": 20}, {"lookback": 2.5}, {"typo": 10}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                make_strategy("momentum", params)
        for call in (
            lambda: RiskConfig(max_position=float("nan")),
            lambda: RiskConfig(max_exposure=1.1),
            lambda: CostModel(fee_bps=-1),
            lambda: CostModel(slippage_bps=10000),
            lambda: ExperimentConfig(initial_capital=float("inf")),
        ):
            with self.assertRaises(ValueError):
                call()


if __name__ == "__main__":
    unittest.main()
