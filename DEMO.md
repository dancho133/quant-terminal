# Real demonstration and recording script

Install once: `uv sync --locked --group dev`. Then:

```sh
uv run --offline --locked quant-terminal-demo
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501). Both real historical runs are written before the dashboard starts. If occupied, use `--port 8502`. Stop with Ctrl+C; do not terminate unrelated processes.

## 55-second recording

Use the actual terminal and app. If loading exceeds its slot, cut only idle wait time and label the cut.

| Time | Visible action | Spoken explanation |
|---|---|---|
| 0–7 s | Run the command, show both IDs and dashboard URL, then open it | “This historical simulator runs both baselines locally without an API key.” |
| 7–15 s | Overview: momentum REJECT, −0.62%, dates and ID | “Momentum was rejected after modeled costs. Rejection is a valid research result.” |
| 15–25 s | Research: flagged NEGATIVE_RETURN, BENCHMARK_UNDERPERFORMANCE and WEAK_AFTER_COSTS | “These are deterministic checks with observations and thresholds, not an LLM opinion.” |
| 25–35 s | Risk: 25% cap, 50% exposure limit, 20% drawdown threshold, TARGET_CAPPED events | “A 40% proposal is capped to 25%. Drawdown is checked at closes; next-open liquidation can lose more through a gap.” |
| 35–45 s | Select mean_reversion, click Run experiment, wait for CAUTION / +4.76% | “The second result is positive but inconclusive: one market, a small sample and retrospective selection.” |
| 45–55 s | Research: Download self-contained HTML, open the actual downloaded file | “The report preserves configuration, risk events and criticism. No working LLM agents or live orders are connected.” |

For longer inspection use [REVIEWER_GUIDE.md](REVIEWER_GUIDE.md). Trades distinguishes fills from closed episodes. Ending positions retain unrealized PnL and an unfilled target; no terminal exit is invented. Form drafts do not change displayed evidence until submitted.

## Automated demo

```sh
uv run --offline --locked quant-terminal-verify --output artifacts/review
```

Expect technical PASSED / exit 0, momentum REJECT, mean_reversion CAUTION. Read verification.json. Failed technical checks return nonzero. Generate reports without a server or verification:

```sh
uv run --offline --locked quant-terminal-demo --no-ui --output artifacts/demo
```

Each folder contains experiment.json, report.html, report.md, trades.csv, equity.svg, drawdown.svg and exposure.svg. HTML embeds its figures and works offline. JSON is canonical evidence; charts are not correctness proofs.

## Actual captures

[Overview](docs/images/dashboard-overview.jpg), [Risk](docs/images/dashboard-risk.jpg), [Research](docs/images/dashboard-research.jpg), [Performance](docs/images/dashboard-performance.jpg), [mean reversion](docs/images/dashboard-mean-reversion.jpg), and [exported report](docs/images/research-report.jpg) show the running updated code. IDs and capture hashes are recorded in [examples/evidence.json](examples/evidence.json). No mockup images are used. This is a prepared recording script; a finished video is not claimed.

Historical results are simulated. Code: MIT; data and derived outputs: separate noncommercial terms in [NOTICE](quant_terminal/sample_data/NOTICE.md). OpenAI Codex assisted development and does not make runtime strategy decisions.
