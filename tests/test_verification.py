"""The reviewer command must distinguish valid REJECT from broken accounting."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_terminal.data import load_dataset
from quant_terminal.experiment import run_experiment
from quant_terminal.models import ExperimentConfig


class VerificationTests(unittest.TestCase):
    def test_offline_verifier_executes_both_strategies_and_writes_traceable_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-m", "quant_terminal.verify", "--output", tmp],
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((Path(tmp) / "verification.json").read_text())
            self.assertEqual(summary["failures"], [])
            self.assertEqual(set(summary["artifact_paths"]), {"momentum", "mean_reversion"})
            self.assertEqual(
                summary["hypothesis_verdicts"], {"momentum": "REJECT", "mean_reversion": "CAUTION"}
            )
            for name in ("checked_commit", "engine_hash", "dataset_hash", "commands", "checks"):
                self.assertIn(name, summary)
            self.assertTrue(all(c["passed"] for c in summary["checks"]))
            self.assertTrue(all(c["exit_code"] == 0 for c in summary["commands"]))

    def test_verifier_catches_independent_tampering_of_accounting_and_identity(self):
        from quant_terminal.verify import check_artifact

        config = ExperimentConfig()
        dataset = load_dataset()
        artifact = run_experiment(config, dataset)
        self.assertTrue(all(c["passed"] for c in check_artifact(artifact, dataset, config)))
        for description, mutate in (
            (
                "cap event",
                lambda a: next(
                    e for e in a["result"]["risk"]["events"] if e["code"] == "TARGET_CAPPED"
                ).__setitem__("allowed", 1),
            ),
            ("empty ledger", lambda a: a["result"].__setitem__("ledger", [])),
            (
                "dataset",
                lambda a: a["dataset"].update(
                    asset="ETHUSDT", rows=7, start="1900-01-01T00:00:00Z"
                ),
            ),
            (
                "risk approval",
                lambda a: next(
                    e for e in a["result"]["risk"]["events"] if e["code"] == "ORDER_APPROVED"
                ).update(action="REJECT", timestamp="1900-01-01"),
            ),
            (
                "risk drawdown",
                lambda a: a["result"]["risk"].__setitem__("max_observed_drawdown", 99),
            ),
            (
                "terminal pending",
                lambda a: a["result"]["pending_order"].__setitem__(
                    "requires_trade", not a["result"]["pending_order"]["requires_trade"]
                ),
            ),
            ("cash", lambda a: a["result"]["ledger"][1].__setitem__("cash", 9999)),
            (
                "realized pnl",
                lambda a: a["result"]["ending_position"].__setitem__("unrealized_pnl", 123),
            ),
            (
                "signal time",
                lambda a: a["result"]["fills"][0].__setitem__(
                    "signal_timestamp", a["result"]["fills"][0]["timestamp"]
                ),
            ),
            ("fee", lambda a: a["result"]["fills"][0].__setitem__("fee", 0)),
            ("config", lambda a: a["config"].__setitem__("initial_capital", 20000)),
            ("engine", lambda a: a["engine"].__setitem__("sha256", "bad")),
            (
                "nonfinite",
                lambda a: a["robustness"]["cost_scenarios"][0].__setitem__(
                    "total_return", float("nan")
                ),
            ),
            ("comparator", lambda a: a["comparator"]["metrics"].__setitem__("total_return", 99)),
            ("critic", lambda a: a["critic"].__setitem__("verdict", "PASS")),
        ):
            changed = copy.deepcopy(artifact)
            mutate(changed)
            with self.subTest(description=description):
                self.assertTrue(
                    any(not c["passed"] for c in check_artifact(changed, dataset, config))
                )

    def test_fabricated_robustness_cannot_pass_with_a_recomputed_critic(self):
        from quant_terminal.critic import review
        from quant_terminal.verify import check_artifact

        dataset, config = load_dataset(), ExperimentConfig()
        artifact = run_experiment(config, dataset)
        for group in ("parameter_variants", "time_windows", "cost_scenarios"):
            changed = copy.deepcopy(artifact)
            changed["robustness"][group][0]["total_return"] = 99
            changed["critic"] = review(changed["result"], changed["robustness"])
            with self.subTest(group=group):
                self.assertTrue(
                    any(not c["passed"] for c in check_artifact(changed, dataset, config))
                )

    def test_initialization_failure_is_recorded_in_summary(self):
        from quant_terminal.verify import main

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(sys, "argv", ["verify", "--output", tmp]),
                patch(
                    "quant_terminal.verify.load_dataset",
                    side_effect=ValueError("CSV checksum does not match its provenance manifest."),
                ),
                self.assertRaises(SystemExit) as failed,
            ):
                main()
            self.assertEqual(failed.exception.code, 1)
            summary = json.loads((Path(tmp) / "verification.json").read_text())
            self.assertTrue(summary["failures"])

    def test_check_only_mode_returns_nonzero_for_missing_or_damaged_artifact(self):
        from quant_terminal.reports import write_artifacts
        from quant_terminal.verify import check_exports

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            missing = subprocess.run(
                [sys.executable, "-m", "quant_terminal.verify", "--check-only", "--output", tmp],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(missing.returncode, 0)
            artifact = run_experiment(ExperimentConfig())
            folder = write_artifacts(artifact, output)
            (folder / "equity.svg").write_text("<notsvg/>")
            with self.assertRaises(ValueError):
                check_exports(folder, artifact)
            (folder / "trades.csv").write_text("wrong,column\n1,2\n")
            damaged = subprocess.run(
                [sys.executable, "-m", "quant_terminal.verify", "--check-only", "--output", tmp],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(damaged.returncode, 0)
            self.assertTrue(json.loads((output / "verification.json").read_text())["failures"])

    def test_numerical_comparison_allows_python_metadata_but_rejects_changed_result(self):
        from quant_terminal.verify import compare_numerical

        artifact = run_experiment(ExperimentConfig())
        other = copy.deepcopy(artifact)
        other["reproducibility"]["python"] = "3.11.99"
        other["result"]["metrics"]["total_return"] += 1e-13
        compare_numerical(artifact, other)
        other["result"]["ledger"][-1]["equity"] += 1
        with self.assertRaises(ValueError):
            compare_numerical(artifact, other)


if __name__ == "__main__":
    unittest.main()
