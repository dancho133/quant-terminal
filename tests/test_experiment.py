"""Experiment identity, deterministic criticism and artifact integration."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


def reviewer_fixture():
    result = {
        "metrics": {
            "total_return": 0.20,
            "same_risk_benchmark_return": 0.12,
            "benchmark_return": 0.3,
            "number_of_trades": 30,
            "sharpe_like": 1.0,
            "max_drawdown": 0.05,
            "turnover": 2.0,
            "evaluation_bars": 365,
            "asset_concentration": 0.5,
        },
        "risk": {"halted": False, "limits": {"max_drawdown": 0.2}, "events": []},
        "ending_position": {"units": 0},
    }
    evidence = {
        "cost_scenarios": [
            {"name": "zero_cost", "total_return": 0.21},
            {"name": "base_cost", "total_return": 0.20},
            {"name": "double_cost", "total_return": 0.18},
        ],
        "parameter_variants": [{"total_return": 0.19}, {"total_return": 0.21}],
        "time_windows": [{"total_return": 0.08}, {"total_return": 0.09}],
        "retrospective_selection": False,
    }
    return result, evidence


class ExperimentTests(unittest.TestCase):
    def test_annualized_turnover_and_report_use_the_configured_year_length(self):
        from quant_terminal.experiment import run_experiment
        from quant_terminal.models import ExperimentConfig
        from quant_terminal.reports import markdown_report

        artifact = run_experiment(ExperimentConfig(strategy="mean_reversion", periods_per_year=252))
        observed = next(
            c["observed"] for c in artifact["critic"]["checks"] if c["code"] == "EXCESSIVE_TURNOVER"
        )
        self.assertAlmostEqual(observed, 5.780982133655282, places=8)
        self.assertIn("sqrt(252)", markdown_report(artifact))

    def test_custom_csv_reports_preserve_unknown_provenance_and_terms(self):
        from quant_terminal.data import load_dataset
        from quant_terminal.experiment import run_experiment
        from quant_terminal.models import ExperimentConfig
        from quant_terminal.reports import html_report, markdown_report

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.csv"
            path.write_text(
                "timestamp,open,high,low,close,volume\n"
                + "".join(
                    f"2025-01-{day:02d}T00:00:00Z,100,101,99,100,100\n" for day in range(1, 5)
                ),
                encoding="utf-8",
            )
            artifact = run_experiment(
                ExperimentConfig(evaluation_end="2025-01-04"), load_dataset("BTCUSDT", path)
            )
            self.assertEqual(artifact["scope"]["dataset"], "user_csv")
            for report in (markdown_report(artifact), html_report(artifact)):
                self.assertNotIn("Binance Vision", report)
                self.assertIn("unverified", report)

    def test_malformed_manifest_and_oversized_csv_fail_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.csv"
            header = "timestamp,open,high,low,close,volume\n"
            valid = "2025-01-01T00:00:00Z,100,101,99,100,100\n"
            command = [
                sys.executable,
                "-m",
                "quant_terminal.run",
                "--data",
                str(path),
                "--output",
                str(Path(tmp) / "out"),
            ]
            cases = (
                ("manifest", "[]", header + valid),
                (
                    "oversized",
                    "{}",
                    header + "2025-01-01T00:00:00Z,100,101,99,100," + "1" * 140000 + "\n",
                ),
            )
            for name, metadata, csv_content in cases:
                path.write_text(csv_content, encoding="utf-8")
                path.with_suffix(".json").write_text(metadata, encoding="utf-8")
                with self.subTest(name=name):
                    failed = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    self.assertEqual(failed.returncode, 2, failed.stderr)
                    self.assertNotIn("Traceback", failed.stderr)
                    self.assertFalse((Path(tmp) / "out").exists())

    def test_semantically_equal_numeric_defaults_share_identity(self):
        from quant_terminal.data import load_dataset
        from quant_terminal.experiment import experiment_identity
        from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig

        data = load_dataset()
        api = ExperimentConfig()
        cli = ExperimentConfig(initial_capital=10000, costs=CostModel(10, 5))
        self.assertEqual(experiment_identity(api, data), experiment_identity(cli, data))
        integer_risk = ExperimentConfig(risk=RiskConfig(1, 1, 1))
        float_risk = ExperimentConfig(risk=RiskConfig(1.0, 1.0, 1.0))
        self.assertEqual(
            experiment_identity(integer_risk, data), experiment_identity(float_risk, data)
        )
        integer_z = ExperimentConfig(strategy="mean_reversion", params={"entry_z": -1, "exit_z": 0})
        float_z = ExperimentConfig(strategy="mean_reversion")
        self.assertEqual(experiment_identity(integer_z, data), experiment_identity(float_z, data))

    def test_critic_pass_caution_reject_have_structured_evidence(self):
        from quant_terminal.critic import review

        result, evidence = reviewer_fixture()
        self.assertEqual(review(result, evidence)["verdict"], "PASS")
        low_sample = copy.deepcopy(result)
        low_sample["metrics"]["number_of_trades"] = 2
        caution = review(low_sample, evidence)
        self.assertEqual(caution["verdict"], "CAUTION")
        self.assertTrue(any(c["code"] == "FEW_TRADES" and c["flagged"] for c in caution["checks"]))
        failed = copy.deepcopy(result)
        failed["metrics"]["total_return"] = -0.01
        rejected = review(failed, evidence)
        self.assertEqual(rejected["verdict"], "REJECT")
        self.assertTrue(
            any(c["code"] == "NEGATIVE_RETURN" and c["flagged"] for c in rejected["checks"])
        )
        self.assertEqual(rejected["conclusion"], "Hypothesis rejected.")
        self.assertTrue(all("observed" in c and "threshold" in c for c in rejected["checks"]))

    def test_successful_order_rejection_does_not_reject_research(self):
        from quant_terminal.critic import review

        result, evidence = reviewer_fixture()
        result["risk"]["events"] = [{"action": "REJECT", "code": "EXPOSURE_LIMIT"}]
        self.assertEqual(review(result, evidence)["verdict"], "PASS")

    def test_critic_flags_fragile_costs_parameters_and_windows(self):
        from quant_terminal.critic import review

        result, evidence = reviewer_fixture()
        evidence["cost_scenarios"][-1]["total_return"] = -0.02
        evidence["parameter_variants"][-1]["total_return"] = -0.2
        evidence["time_windows"][-1]["total_return"] = -0.01
        verdict = review(result, evidence)
        flagged = {c["code"] for c in verdict["checks"] if c["flagged"]}
        self.assertTrue(
            {"COST_FRAGILITY", "PARAMETER_SENSITIVITY", "WINDOW_INSTABILITY"} <= flagged
        )
        self.assertEqual(verdict["verdict"], "REJECT")

    def test_experiment_id_is_stable_and_changes_with_config_data_and_engine(self):
        from quant_terminal.data import dataset_from_bars, load_dataset
        from quant_terminal.experiment import experiment_identity, run_experiment
        from quant_terminal.models import ExperimentConfig

        cfg = ExperimentConfig()
        data = load_dataset()
        first = run_experiment(cfg, data)
        second = run_experiment(cfg, data)
        self.assertEqual(first, second)
        self.assertEqual(len(first["experiment_id"]), 20)
        self.assertNotEqual(
            first["experiment_id"],
            run_experiment(replace(cfg, initial_capital=20000), data)["experiment_id"],
        )
        changed_bar = replace(data.bars[-1], volume=data.bars[-1].volume + 1)
        changed = dataset_from_bars(data.asset, data.bars[:-1] + (changed_bar,), data.provenance)
        self.assertNotEqual(experiment_identity(cfg, data), experiment_identity(cfg, changed))
        self.assertNotEqual(
            experiment_identity(cfg, data, engine_hash="one"),
            experiment_identity(cfg, data, engine_hash="two"),
        )
        self.assertEqual(len(first["robustness"]["cost_scenarios"]), 3)
        self.assertEqual(len(first["robustness"]["parameter_variants"]), 2)
        self.assertEqual(len(first["robustness"]["time_windows"]), 2)
        self.assertIn("same_risk_benchmark_return", first["result"]["metrics"])
        self.assertEqual(first["dataset"]["provenance"]["kind"], "historical_public_snapshot")

    def test_reports_are_self_contained_and_preserve_rejection(self):
        from quant_terminal.experiment import run_experiment
        from quant_terminal.models import ExperimentConfig
        from quant_terminal.reports import write_artifacts

        artifact = run_experiment(ExperimentConfig(strategy="mean_reversion"))
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_artifacts(artifact, Path(tmp))
            restored = json.loads((folder / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, artifact)
            html = (folder / "report.html").read_text(encoding="utf-8")
            self.assertIn("<svg", html)
            self.assertNotIn("<script src=", html)
            self.assertIn(artifact["critic"]["conclusion"], html)
            self.assertIn(artifact["critic"]["verdict"], (folder / "report.md").read_text())
            self.assertTrue((folder / "equity.svg").is_file())
            self.assertTrue((folder / "drawdown.svg").is_file())
            self.assertTrue((folder / "trades.csv").is_file())

    def test_cli_generates_artifact_and_invalid_capital_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [sys.executable, "-m", "quant_terminal.run", "--output", tmp]
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Experiment", result.stdout)
            self.assertEqual(len(list(Path(tmp).glob("*/experiment.json"))), 1)
            bad = subprocess.run(
                command + ["--initial-capital", "nan"], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(bad.returncode, 2)
            self.assertIn("finite", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
