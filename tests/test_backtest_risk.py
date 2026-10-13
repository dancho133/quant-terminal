"""Hand-audited execution and risk invariants, independent of historical results."""

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta


class ScriptedStrategy:
    name = "fixture"
    params = {"lookback": 2}
    hypothesis = "Synthetic accounting fixture."
    assumptions = ()
    failure_modes = ()

    def __init__(self, targets):
        self.targets = targets
        self.index = 0

    def target(self, feature, current_weight):
        result = self.targets[min(self.index, len(self.targets) - 1)]
        self.index += 1
        return result


def fixture(open_close):
    from quant_terminal.data import dataset_from_bars
    from quant_terminal.models import Bar

    return dataset_from_bars(
        "BTCUSDT",
        tuple(
            Bar(
                datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                o,
                max(o, c) + 1,
                min(o, c) - 1,
                c,
                100,
            )
            for i, (o, c) in enumerate(open_close)
        ),
    )


def config(days=4, **kwargs):
    from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig

    options = dict(
        initial_capital=1000,
        evaluation_start="2024-01-01",
        evaluation_end=f"2024-01-{days:02d}",
        costs=CostModel(0, 0),
        risk=RiskConfig(1, 1, 1),
    )
    return ExperimentConfig(**(options | kwargs))


class BacktestRiskTests(unittest.TestCase):
    def test_next_open_fills_reconcile_slippage_fees_and_realized_pnl(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.models import CostModel

        result = simulate(
            fixture([(100, 100), (110, 120), (130, 130)]),
            ScriptedStrategy([0.5, 0, 0]),
            config(3, costs=CostModel(100, 100)),
        )
        buy, sell = result["fills"]
        qty = 500 / 111.1055  # Half of post-cost marked equity; independently derived.
        self.assertEqual(buy["timestamp"], "2024-01-02T00:00:00+00:00")
        self.assertEqual(buy["signal_timestamp"], "2024-01-01T00:00:00+00:00")
        self.assertAlmostEqual(buy["quantity"], qty)
        self.assertAlmostEqual(buy["price"], 111.1)
        self.assertAlmostEqual(buy["fee"], qty * 1.111)
        self.assertAlmostEqual(sell["price"], 128.7)
        self.assertAlmostEqual(result["ledger"][1]["cash"], 1000 - qty * 112.211)
        self.assertAlmostEqual(result["ledger"][1]["equity"], 1000 - qty * 112.211 + qty * 120)
        self.assertAlmostEqual(result["ledger"][-1]["equity"], 1000 + qty * 15.202)
        self.assertAlmostEqual(result["round_trips"][0]["net_pnl"], qty * 15.202)
        self.assertEqual(result["metrics"]["number_of_trades"], 1)
        self.assertEqual(result["metrics"]["win_rate"], 1)
        self.assertAlmostEqual(
            result["metrics"]["transaction_costs"],
            sum(f["fee"] + f["slippage_cost"] for f in result["fills"]),
        )

    def test_drawdown_latches_and_liquidates_at_next_open_with_gap_loss(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.models import RiskConfig

        result = simulate(
            fixture([(100, 100), (100, 60), (50, 50), (200, 200)]),
            ScriptedStrategy([1]),
            config(risk=RiskConfig(1, 1, 0.2)),
        )
        self.assertEqual([f["side"] for f in result["fills"]], ["BUY", "SELL"])
        self.assertEqual(result["fills"][1]["timestamp"], "2024-01-03T00:00:00+00:00")
        self.assertEqual(result["fills"][1]["reason"], "drawdown_liquidation")
        self.assertAlmostEqual(result["ledger"][-1]["equity"], 500)
        self.assertTrue(result["risk"]["halted"])
        self.assertAlmostEqual(result["metrics"]["max_drawdown"], 0.5)
        self.assertTrue(any(e["code"] == "DRAWDOWN_HALT" for e in result["risk"]["events"]))

    def test_final_holdings_are_marked_without_fabricating_a_terminal_exit(self):
        from quant_terminal.backtest import simulate

        result = simulate(
            fixture([(100, 100), (100, 100), (150, 150)]), ScriptedStrategy([1]), config(3)
        )
        self.assertEqual(len(result["fills"]), 1)
        self.assertAlmostEqual(result["ending_position"]["units"], 10)
        self.assertAlmostEqual(result["ending_position"]["unrealized_pnl"], 500)
        self.assertAlmostEqual(result["metrics"]["total_return"], 0.5)
        self.assertIsNone(result["metrics"]["win_rate"])
        self.assertEqual(result["metrics"]["number_of_trades"], 0)
        self.assertEqual(result["pending_order"]["status"], "unfilled_end_of_data")

    def test_final_close_halt_retains_unresolved_risk_exposure(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.models import RiskConfig

        result = simulate(
            fixture([(100, 100), (100, 60)]),
            ScriptedStrategy([1]),
            config(2, risk=RiskConfig(1, 1, 0.2)),
        )
        self.assertTrue(result["risk"]["halted"])
        self.assertAlmostEqual(result["ending_position"]["units"], 10)
        self.assertEqual(result["pending_order"]["reason"], "drawdown_liquidation")

    def test_risk_rejects_invalid_oversized_unaffordable_and_short_orders(self):
        from quant_terminal.models import CostModel, RiskConfig
        from quant_terminal.risk import RiskManager

        gate = RiskManager(RiskConfig(0.25, 0.5, 0.2), CostModel(10, 5), 1000)
        for qty, cash, units in (
            (float("nan"), 1000, 0),
            (5, 1000, 0),
            (11, 1000, 0),
            (-1, 1000, 0),
        ):
            self.assertFalse(gate.approve_order(qty, cash, units, 100, "fixture"))
        self.assertEqual(len([e for e in gate.events if e["action"] == "REJECT"]), 4)

    def test_target_caps_apply_to_post_cost_equity_and_preserve_proposal(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.models import CostModel, RiskConfig

        result = simulate(
            fixture([(100, 100), (100, 100), (100, 100)]),
            ScriptedStrategy([0.4]),
            config(3, costs=CostModel(100, 100), risk=RiskConfig(0.5, 0.1, 0.2)),
        )
        self.assertAlmostEqual(result["ledger"][1]["exposure"], 0.1)
        decisions = [e for e in result["risk"]["events"] if e["code"] == "TARGET_CAPPED"]
        self.assertEqual(decisions[0]["observed"], 0.4)
        self.assertEqual(decisions[0]["allowed"], 0.1)
        self.assertGreaterEqual(min(r["cash"] for r in result["ledger"]), -1e-8)
        for row in result["ledger"]:
            self.assertAlmostEqual(row["equity"], row["cash"] + row["units"] * row["close"])

    def test_future_mutation_does_not_change_earlier_ledger_or_fills(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.data import dataset_from_bars

        first = fixture([(100, 100), (110, 110), (120, 115), (110, 100)])
        changed = dataset_from_bars(
            first.asset,
            first.bars[:3]
            + (replace(first.bars[3], open=10000, close=10000, high=10001, low=9999),),
        )
        one = simulate(first, ScriptedStrategy([0.4, 0.4, 0]), config())
        two = simulate(changed, ScriptedStrategy([0.4, 0.4, 0]), config())
        self.assertEqual(one["ledger"][:3], two["ledger"][:3])
        self.assertEqual(
            [f for f in one["fills"] if f["timestamp"] < "2024-01-04"],
            [f for f in two["fills"] if f["timestamp"] < "2024-01-04"],
        )

    def test_rebalancing_reconciles_closed_plus_open_cost_basis(self):
        from quant_terminal.backtest import simulate
        from quant_terminal.models import CostModel

        result = simulate(
            fixture([(100, 100), (100, 120), (130, 140), (120, 120)]),
            ScriptedStrategy([0.4]),
            config(costs=CostModel(10, 5)),
        )
        realized = sum(f["realized_pnl"] or 0 for f in result["fills"])
        self.assertAlmostEqual(
            result["ledger"][-1]["equity"] - 1000,
            realized + result["ending_position"]["unrealized_pnl"],
            places=7,
        )


if __name__ == "__main__":
    unittest.main()
