# Reproduce the demonstration

Requirements: Git, uv, browser. First dependency installation needs internet; research runtime uses the bundled snapshot.

```sh
git clone https://github.com/dancho133/quant-terminal.git
cd quant-terminal
uv run --locked quant-terminal-demo
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501). The launcher executes **both** baselines and writes their JSON, HTML, Markdown, SVG and CSV files before starting Streamlit.

A five-minute engineering walkthrough:

1. **Overview:** inspect the actual hypothesis rejection, capital, evaluation dates and experiment ID.
2. **Performance:** compare net equity, same-risk constant-long and contextual gross buy-and-hold; inspect drawdown and metric limitations.
3. **Trades:** trace a prior-close signal to the next-open fill, both modeled costs and cash/holdings after the fill. Closed episodes differ from fill count.
4. **Risk:** inspect requested 40% targets capped to 25%, close exposure drift and explicit rejected proposals. Price gaps can overshoot thresholds.
5. **Research:** inspect assumptions, failure modes, every critic check and fixed robustness reruns. Download the experiment JSON and self-contained HTML.
6. Change the strategy to `mean_reversion` and press **Run experiment**. Draft edits do not change the displayed run until submitted.

The defaults intentionally show different outcomes: momentum receives REJECT; mean reversion receives CAUTION. Positive historical return is not treated as validated alpha.

CLI without the dashboard:

```sh
uv run --locked python -m quant_terminal.run --strategy momentum --asset BTCUSDT --initial-capital 10000
uv run --locked python -m quant_terminal.run --strategy mean_reversion --asset BTCUSDT --initial-capital 10000
```

Reproduce both with no network after installation:

```sh
uv run --offline --locked quant-terminal-demo --no-ui --output artifacts/offline
```

Each folder `artifacts/<experiment-id>/` contains:

| File | Contents |
|---|---|
| experiment.json | Configuration, source/data identity, full simulation, comparator, robustness, critic |
| report.html | Self-contained report with embedded SVG figures; works offline |
| report.md | Same evidence in Markdown with local figure links |
| equity.svg / drawdown.svg / exposure.svg | Standalone research figures |
| trades.csv | Actual simulated fill ledger |

Run checks:

```sh
uv sync --locked --group dev
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m unittest discover -s tests -v
```

For a different port: `uv run --locked quant-terminal-demo --port 8502`.
For a different artifact location: `--output path/to/artifacts`.
For a standalone Streamlit launch, `QUANT_TERMINAL_OUTPUT` selects the output directory.

If uv is missing, install it using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/). If port 8501 is occupied, choose another port; no existing process is terminated.

The bundled market data has separate noncommercial terms; see [NOTICE](quant_terminal/sample_data/NOTICE.md). No credentials, LLM services, external trading accounts or money are used.
