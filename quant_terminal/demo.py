"""One command creates two research artifacts and starts the actual dashboard."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from quant_terminal.experiment import run_experiment
from quant_terminal.models import ExperimentConfig
from quant_terminal.reports import write_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline historical research demo; no live orders."
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="Generate both baselines without starting a server."
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.exit(2, "Choose a port in [1024, 65535].\n")
    try:
        for name in ("momentum", "mean_reversion"):
            artifact = run_experiment(ExperimentConfig(strategy=name))
            folder = write_artifacts(artifact, args.output)
            print(
                f"{name}: {artifact['experiment_id']} · {artifact['critic']['verdict']} · {folder.resolve()}",
                flush=True,
            )
    except (ValueError, OSError, ArithmeticError) as exc:
        parser.exit(2, f"Demo failed: {exc}\n")
    if args.no_ui:
        return
    app = Path(__file__).parent / "dashboard" / "app.py"
    environment = os.environ | {"QUANT_TERMINAL_OUTPUT": str(args.output.resolve())}
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.address=127.0.0.1",
        f"--server.port={args.port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--theme.base=dark",
        "--theme.primaryColor=#5CBFB5",
        "--theme.backgroundColor=#0D1117",
        "--theme.secondaryBackgroundColor=#151C25",
        "--theme.textColor=#E3EAF2",
    ]
    print(f"Dashboard: http://127.0.0.1:{args.port} · Ctrl+C to stop", flush=True)
    try:
        raise SystemExit(subprocess.call(command, env=environment))
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
