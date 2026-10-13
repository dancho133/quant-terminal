"""Real dashboard interaction; widgets submit the same numerical experiment runner."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "quant_terminal" / "dashboard" / "app.py"


class DashboardTests(unittest.TestCase):
    def test_structured_critic_fields_render_without_arrow_type_repair(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"QUANT_TERMINAL_OUTPUT": tmp}),
        ):
            with self.assertNoLogs("streamlit.dataframe_util", level="INFO"):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
                self.assertFalse(app.exception)

    def test_dashboard_runs_all_five_tabs_and_submits_a_new_strategy(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"QUANT_TERMINAL_OUTPUT": tmp}),
        ):
            app = AppTest.from_file(str(APP), default_timeout=30).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(
                [t.label for t in app.tabs],
                ["Overview", "Performance", "Trades", "Risk", "Research"],
            )
            first_id = app.session_state["experiment"]["experiment_id"]
            app.selectbox(key="strategy").set_value("mean_reversion")
            app.number_input(key="initial_capital").set_value(20000.0)
            app.button(key="run_experiment").click().run()
            self.assertFalse(app.exception, str(app.exception))
            artifact = app.session_state["experiment"]
            self.assertEqual(artifact["config"]["strategy"], "mean_reversion")
            self.assertEqual(artifact["config"]["initial_capital"], 20000)
            self.assertNotEqual(artifact["experiment_id"], first_id)
            self.assertTrue((Path(tmp) / artifact["experiment_id"] / "report.html").is_file())
            self.assertGreaterEqual(len(app.get("download_button")), 3)

    def test_form_draft_does_not_replace_displayed_experiment(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"QUANT_TERMINAL_OUTPUT": tmp}),
        ):
            app = AppTest.from_file(str(APP), default_timeout=30).run()
            original = app.session_state["experiment"]["experiment_id"]
            app.number_input(key="initial_capital").set_value(25000.0).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["experiment"]["experiment_id"], original)
            self.assertEqual(app.session_state["experiment"]["config"]["initial_capital"], 10000)


if __name__ == "__main__":
    unittest.main()
