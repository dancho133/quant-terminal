# Quant Terminal

Historical Market Research & Risk Sandbox.

Review checkout: **codex/bytrader-review**. [Inspect the actual CI runs for this branch](https://github.com/dancho133/quant-terminal/actions?query=branch%3Acodex%2Fbytrader-review); the older main-branch result is not evidence for these changes.

Quant Terminal simulates two explicit baselines on historical daily OHLCV, applies an independent numerical risk gate and screens the results with deterministic rules. A Streamlit dashboard displays the accounting ledger and exports JSON, CSV, Markdown and self-contained HTML reports.

**Implemented:** trailing features; momentum and mean-reversion rules; next-open simulated fills; modeled fees/slippage; cash, positions and average cost basis; risk caps and delayed drawdown liquidation; a same-risk comparator; fixed robustness reruns; a dashboard; and an offline verification command.

**Not implemented:** working LLM agents, autonomous research, live trading or a broker paper account. `agents.py` contains future `Protocol` interfaces only. The critic is Python screening logic, not an AI reviewer or a statistical test. There is no claim of profitability or production readiness.

Development and internal software review were assisted by **OpenAI Codex**. This is development provenance, not external certification or independent investment validation. BYTRADER's review has not yet occurred. Start with [REVIEWER_GUIDE.md](REVIEWER_GUIDE.md) to reproduce evidence and challenge the implementation.

## Install and verify

Prerequisites: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/) and a browser for the UI. The project selects Python 3.12. Initial dependency/Python installation requires internet access.

```sh
git clone --branch codex/bytrader-review https://github.com/dancho133/quant-terminal.git
cd quant-terminal
uv sync --locked --group dev
uv run --offline --locked quant-terminal-verify
```

The last command executes both strategy CLIs and verifies their exports. It writes `artifacts/review/verification.json` with `checked_commit`, `engine_hash`, `dataset_hash`, actual `commands`, `checks`, `failures` and `artifact_paths`. A failed technical check returns nonzero. A correctly computed **REJECT** is a successful research result, not a program error.

```text
Technical verification: PASSED · 12 checks · .../verification.json
momentum: hypothesis REJECT (separate from technical verification)
mean_reversion: hypothesis CAUTION (separate from technical verification)
```

The checker independently reconstructs cash, holdings, basis, PnL, chronology and risk from exported fills. This replay does not call the simulator, RiskManager or production metric calculator. Stress scenarios are rerun using the existing simulator and their accounting is separately replayed; their metrics must match the exported robustness. Features, strategy rules, identity and critic helpers are shared. These checks are not an independent implementation of every indicator or proof of overall financial-model correctness.

## Human demonstration

```sh
uv run --offline --locked quant-terminal-demo
```

Both experiments are generated before [http://127.0.0.1:8501](http://127.0.0.1:8501) starts. Stop with Ctrl+C. Use `--port 8502` if occupied. [DEMO.md](DEMO.md) includes a 55-second recording script and export steps.

Default data: **1,096 BTCUSDT daily bars, 2023-01-01–2025-12-31**. Earlier bars supply feature context; **2025** is the retrospectively selected evaluation period.

| Baseline | Net marked return | Same-risk constant-long | Max close drawdown | Closed episodes | Critic |
|---|---:|---:|---:|---:|---|
| Momentum, MA 20/50 | −0.62% | −0.48% | 3.56% | 14 | REJECT |
| Mean reversion, 20-day z-score | +4.76% | −0.48% | 5.63% | 15 | CAUTION |

These are historical simulations after modeled costs, not live results. The positive result remains inconclusive. Changing numerical source changes the experiment ID even if default returns stay equal. At `e7cf3bd` the IDs were `bbc87bc1d4ee46e327d3` / `7838b1e5f5eb082c7e1b`; current IDs and hashes are in [examples](examples/README.md) and each new verification summary.

![Actual running dashboard](docs/images/dashboard-overview.jpg)

## Implementation path

```text
data.py → features.py → strategies.py → risk.py → backtest.py
                            experiment.py → critic.py
                            canonical JSON → reports.py / dashboard/app.py
                            exported evidence → verify.py
```

The numerical engine uses the Python standard library. Streamlit/Pandas display results; Matplotlib renders figures. There is no database, broker, queue, agent framework or hidden credential requirement.

| Module | Responsibility |
|---|---|
| `models.py`, `data.py` | Validated config, strict daily UTC CSV, provenance and hashes |
| `features.py`, `strategies.py` | Trailing indicators and predeclared long-or-cash targets |
| `risk.py`, `backtest.py` | Independent authorization, next-open fills, cash/basis/PnL ledger |
| `experiment.py`, `critic.py` | Content identity, comparator, fixed stress runs and screening verdict |
| `reports.py`, `dashboard/app.py` | Exports and five-tab UI using the canonical experiment |
| `run.py`, `demo.py`, `verify.py` | Experiment CLI, human demo and reviewer command |
| `agents.py` | Future typed interfaces; no LLM implementation |

## Execution contract and limitations

- Signals observe data through close **t**; fills occur only at open **t+1**. The last close produces an unfilled proposal.
- Both baselines propose 40% long or cash. Default position cap is 25%, exposure cap 50%; the tighter limit governs one asset. Sizing uses post-cost equity marked at the opening reference price.
- Fees apply to slipped notional on buys and sells. Partial-sale realized PnL uses average acquisition basis including entry fees. Ending equity includes unrealized holdings; eventual exit costs are reported separately.
- The gate blocks borrowing and shorts. Drawdown is sampled at closes. Reaching the threshold permanently blocks entries and queues next-open liquidation. Gaps can exceed it; exposure can drift above the cap between adjustments.
- The constant-long comparator uses the same calendar, capital, target proposal, costs and risk rules. Its exposure/halts may differ. Gross 100% buy-and-hold is context with zero costs and different risk.
- Robustness uses zero/base/double costs, two fixed nearby windows and two chronological fresh-capital resets. It does not select a winner, remove selection bias or establish significance.

Only one daily asset is included. Fills assume fractional lots and sufficient liquidity. There is no order book, intrabar execution, calibrated spread/impact, funding, tax, lot-rule or operational-failure model. Annualization is a configured scaling assumption with zero cash risk-free return and no dependence correction. Float arithmetic is checked within stated tolerances; this is not arbitrary-precision accounting. Unsupported numerical magnitudes can fail rather than yield a usable experiment.

PASS means declared heuristic checks passed; it is not a probability, alpha validation or trading permission. Future LLM proposals, if implemented, would still pass the numerical risk gate.

## Verification evidence

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests -v
uv run --offline --locked quant-terminal-demo --no-ui
uv run --offline --locked quant-terminal-verify
uv build
```

Tests cover hand-derived arithmetic, future-data mutations, risk boundaries, invalid inputs, identity, UI submissions and tampered artifacts. [Recorded verification](examples/verification.md) distinguishes the 26-test baseline from this revision. [Internal AI-assisted software review](docs/code_review.md) records reproduced defects and review limits. Passing checks support specific engineering assertions; they do not certify the entire model.

The [workflow](.github/workflows/ci.yml) runs lint, format, unittest, offline demo, automatic verification and packaging on Linux/Windows with Python 3.11/3.12. Inspect the [actual Actions run](https://github.com/dancho133/quant-terminal/actions) for the reviewed commit: an older passing badge is not evidence for a new revision. Numerical comparisons use explicit tolerances; figure bytes are never compared.

## Data and licensing

The snapshot comes from [Binance Vision public spot archives](https://github.com/binance/binance-public-data); all 36 original checksums were verified at import. No prices were synthesized or backfilled. Synthetic fixtures are labeled test evidence. Integrity hashes do not establish exchange-data completeness or live execution suitability.

Code is **MIT**. Data and derived example outputs have separate **noncommercial CC BY-NC-SA 4.0 and supplemental upstream terms**. See [NOTICE](quant_terminal/sample_data/NOTICE.md) and [upstream terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md). Commercial data use needs an appropriately licensed provider.

Custom CSV: exactly `timestamp,open,high,low,close,volume`, consecutive finite valid daily bars at 00:00 UTC. Both evaluation dates must lie inside the dataset; windows are never clipped. User-provider source and license declarations remain unverified.

```sh
uv run --offline --locked quant-terminal --data data.csv --start 2025-01-01 --end 2025-12-31
```

Optional explicit-network import to a **new** path:

```sh
uv run --locked python -m quant_terminal.data --asset BTCUSDT --start 2025-01 --end 2025-12 --output artifacts/imported/BTCUSDT-1d.csv
```

## Future work

Not implemented: prospective registered walk-forward evaluation; licensed multi-asset data/portfolio accounting; measured liquidity and lot rules; an observable broker paper adapter; optional LLM proposal/explanation adapters. [Research design](docs/research_design.md) explains remaining failure boundaries. These plans do not imply current functionality.
