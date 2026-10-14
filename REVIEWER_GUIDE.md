# Independent technical review guide

Audience: BYTRADER engineers and their AI review agents. The target is a compact historical simulator, not an AI trading service. Report defects, unsupported claims and missing evidence; do not assume tests, screenshots or developer explanations prove overall correctness.

Review branch: `codex/bytrader-review`. Until merged, clone with `git clone --branch codex/bytrader-review https://github.com/dancho133/quant-terminal.git`; the default main checkout remains the earlier prototype. Restart the dashboard after changing numerical source so the running process and on-disk source belong to the same revision.

## Short route

1. Record `git rev-parse HEAD` and `git status --short`. Read README's implemented functions and limits, then `models.py`, `risk.py`, `backtest.py`, `experiment.py`.
2. Install once: `uv sync --locked --group dev`.
3. Run `uv run --offline --locked quant-terminal-verify`. Expect exit **0**, technical **PASSED**, momentum **REJECT**, mean reversion **CAUTION**, and `artifacts/review/verification.json`. A hypothesis's REJECT must not make technical verification fail.
4. Inspect JSON configuration, source/data hashes, fills, ledger, risk events, terminal holdings, comparator and robustness. Trace one sale to its acquisition basis and one fill to the previous close.
5. Run full unittest/Ruff/offline demo below. Inspect boundary and corruption tests, then challenge them with additional fixtures.
6. Start `uv run --offline --locked quant-terminal-demo`, inspect Research/Risk/Trades, change strategy and export HTML/JSON. [DEMO.md](DEMO.md) has a 55-second recording script.

## Assertion map

| Assertion to test | Implementation | Test or command | Limitation |
|---|---|---|---|
| Historical data has declared provenance and integrity | `data.py`, `sample_data/*.json`, `NOTICE.md` | `load_dataset()`, verifier; inspect 36 archive hashes | Integrity is not independent verification of exchange prices |
| Strict CSV fields, valid UTC dates and finite OHLCV | `data.py` | `tests.test_data_features`, `tests.test_validation` | Daily consecutive bars only, no missing-bar imputation |
| Requested dates equal actual evaluation dates | `models.py`, `backtest.py` | `test_requested_window_cannot_be_silently_clipped_to_dataset`; verifier metadata | Both boundaries inside the data; no clipping |
| Invalid types, NaN/Inf and boolean financial inputs fail | `models.py`, `strategies.py`, `run.py` | `tests.test_validation` | Standard int/float; unsupported magnitudes can fail |
| Features use trailing data only | `features.py` | `test_features_use_trailing_values_and_preserve_prefix` | Numerical causality tests do not rule out upstream revision bias |
| Signals fill at next open | `backtest.py` | `test_next_open_fills_reconcile_slippage_fees_and_realized_pnl`; verifier replay | Timestamp denotes bar opening; close is available after bar completion |
| Future changes cannot alter earlier execution | `features.py`, `backtest.py` | `test_future_mutation_does_not_change_earlier_ledger_or_fills` | Does not test every possible dataset-origin leak |
| Costs apply on both sides of execution | `models.py`, `backtest.py` | Hand-calculated next-open test; verifier price/fee replay | Fixed bps, not measured liquidity/impact |
| Cash + units × close equals equity | `backtest.py` | Target-cap test; verifier all rows | Float tolerance; no broker reconciliation |
| Realized + unrealized PnL equals equity change | `backtest.py` | `test_rebalancing_reconciles_closed_plus_open_cost_basis`; verifier | Average basis includes buy fees; no tax accounting |
| Fractional holdings are not erased by fixed epsilon | `backtest.py` | Capital-scale and high-price residual-position tests | Immaterial rebalance threshold: notional/open equity ≤ 1e-12 |
| Zero target closes exactly all holdings, even after an extreme gap | `risk.py`, `backtest.py` | Zero-target rounding and immaterial-gap liquidation tests | Every nonzero liquidation executes; no lot-size restrictions |
| No short/borrowed cash order is authorized | `risk.py` | Invalid/oversized/unaffordable/no-short tests | Tiny negative rounding cash allowed only relative to opening equity |
| Caps use post-cost opening equity | `risk.py` | `test_target_caps_apply_to_post_cost_equity_and_preserve_proposal`; verifier | Close exposure can drift; tighter cap governs one asset |
| Exact drawdown threshold latches | `risk.py` | `test_exact_drawdown_threshold_halts_before_a_next_day_rebound` | Daily closes; no intrabar stop |
| Halt exits at next open, including gap losses | `risk.py`, `backtest.py` | Drawdown gap test; verifier event replay | Loss can exceed the threshold |
| Terminal holdings stay marked; orders stay unfilled | `backtest.py` | Final-holdings / final-close-halt tests; verifier | Marked return excludes eventual exit cost |
| Comparator uses identical modeled rules | `experiment.py` | Verifier separately replays `comparator` | Exposure/halts can differ; gross 100% B&H has different risk |
| Stress configurations and results match their exports | `experiment.py`, `verify.py` | Robustness tests; verifier reruns and reconciles all seven scenarios | Simulator is shared; not an alternative independent financial model |
| Annualization follows configuration | `backtest.py`, `critic.py`, `reports.py` | `test_annualized_turnover_and_report_use_the_configured_year_length` | Scaling assumption, zero cash risk-free yield, no dependence correction |
| Critic gives deterministic evidenced verdicts | `critic.py` | PASS/CAUTION/REJECT and fragile-cost tests; verifier | Heuristics, not significance or permission to trade |
| Identity changes with numerical source/config/data | `experiment.py` | Identity and int/float-equivalence tests; verifier | Python version is metadata outside numerical identity |
| Exports preserve real evidence | `reports.py`, `verify.py` | Export tests; JSON/CSV/HTML/SVG checks | Graph validation is structural; figures do not prove correctness |
| Corruption fails verification with a JSON summary | `verify.py` | `tests.test_verification` | Covers cash/PnL/fees/signal time/config/data/engine/risk/critic/stress/NaN/empty ledger/CSV/SVG and bootstrap failure |
| Form drafts do not replace submitted results | `dashboard/app.py` | `tests.test_dashboard`; real browser walkthrough | Session state; no persistence service |
| There are no working LLM agents | `agents.py`, `pyproject.toml` | Inspect Protocol declarations and runtime imports | Future contracts only; strategies and critic are code |

## Commands and expected results

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests -v
uv run --offline --locked quant-terminal-demo --no-ui --output artifacts/demo
uv run --offline --locked quant-terminal-verify --output artifacts/review
uv build
```

Rounded default results: momentum **−0.62%**, close drawdown **3.56%**, 14 closed episodes, REJECT; mean reversion **+4.76%**, drawdown **5.63%**, 15 closed episodes, CAUTION. Same-risk comparator approximately **−0.48%**. These retrospective results are not a future-profitability expectation.

The reviewer command records both actual CLI exit codes and twelve aggregate technical checks. `failures` is authoritative. `--check-only` checks existing files without regenerating them; after intentionally damaging an artifact in a disposable output folder it must return nonzero:

```sh
uv run --offline --locked quant-terminal-verify --check-only --output artifacts/review
```

The summary records `checked_commit` and `worktree_dirty`. For a dirty tree that SHA is the base commit; `engine_hash` identifies actual numerical source. A wheel has no Git checkout: `--checked-commit <full-source-sha>` records an explicitly **declared** source commit. Without it, commit is `null` / `commit_source: unavailable`. An unrelated parent repository is not used. If the output directory is unwritable, JSON cannot be saved; the OS error remains a nonzero failure.

## Numerical comparison rules

Same numerical source, normalized config and dataset/provenance require exact IDs, object/list structure, categorical values, integers and null locations. Floats use `math.isclose(rel_tol=1e-10, abs_tol=1e-10)`; these are consistency tolerances, not confidence intervals. Ignore only `reproducibility.python` across supported Python versions. Never require report/graph bytes, fonts, screenshots or platform output paths to match.

```sh
uv run --offline --locked quant-terminal-verify --output artifacts/second --reference-dir artifacts/review
```

This compares both full canonical JSON artifacts. Changed engine/config/data need separate analysis rather than relaxed comparison or copied IDs. At `e7cf3bd`, IDs were `bbc87bc1d4ee46e327d3` / `7838b1e5f5eb082c7e1b`; preparation fixes change source hashes, so new IDs are expected.

## Installed wheel in a clean environment

```sh
uv build
uv export --locked --no-dev --no-emit-project --format requirements.txt --output-file /absolute/path/to/locked-runtime.txt
uv venv /absolute/path/to/wheel-review --python 3.12
uv pip install --python /absolute/path/to/wheel-review/bin/python -r /absolute/path/to/locked-runtime.txt
uv pip install --python /absolute/path/to/wheel-review/bin/python --no-deps dist/quant_terminal-0.1.0-py3-none-any.whl
```

Windows uses `C:\...\wheel-review\Scripts\python.exe` instead of `.../bin/python`. Create a new environment without system-site-packages. Run its Python from **outside the checkout**, with PYTHONPATH absent:

```sh
/absolute/path/to/wheel-review/bin/python -m quant_terminal.verify --output /absolute/path/to/wheel-results --reference-dir /absolute/path/to/source-results --checked-commit <full-source-sha>
```

Install from a populated uv cache with `--offline` if available; an empty cache needs internet once. Runtime uses bundled data. Confirm `quant_terminal.__file__` points into that new environment, detecting omitted package data or accidental source imports.

## Review boundaries

[examples/verification.md](examples/verification.md) records actual executed checks and their source/CI revisions. [Internal software review](docs/code_review.md) lists reproduced defects and AI-assisted review limits. Neither is a BYTRADER audit or certification of complete model correctness. A secret-pattern scan supports only its checked publication scope; it is not a general security audit.

Remaining work includes stronger independent indicator fixtures, adversarial execution paths, real liquidity/lot rules, licensed multi-asset data, prospective trial-selection controls and broker reconciliation. Report any unavailable check, including Docker, as unavailable instead of assuming it passed.
