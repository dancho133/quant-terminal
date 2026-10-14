> Historical initial design/plan. Current implemented scope, fixes and evidence are in README.md, REVIEWER_GUIDE.md and examples/verification.md. Future agent architecture here does not imply working LLM agents.

# Quant Terminal Implementation Plan

> For agentic workers: use superpowers:executing-plans for implementation in this session.

Goal: ship and execute the complete offline research demo described in the design.
Architecture: one Python numerical pipeline with an independent risk manager, deterministic critic, canonical artifacts, and a thin Streamlit viewer.
Tech stack: Python 3.12; stdlib numerical core; Streamlit; uv; Ruff; unittest.
Spec: docs/superpowers/specs/2026-10-13-quant-terminal-design.md

## Global constraints
- Long-only fractional BTC, daily UTC bars; no leverage, live order path, credentials or LLM dependency.
- Signals close t, fills open t+1; final holdings marked and outstanding orders disclosed.
- Each accounting change gets a runnable invariant test. Unfavorable research output remains visible.
- Use the separate project repository; preserve other workspace files.
- User supplied the complete scope and expressly requested implementation without a planning stop.

## Review focus
- Gap beyond risk thresholds: disclose overshoot, latch halt, execute next open.
- Final-bar stop with held units: outstanding risk and holdings remain visible.
- Non-finite CLI parameters or malformed data: fail with a concise error before writing results.
- Changes to robustness/risk source: result ID must change; do not reuse stale artifacts.
- Streamlit form edits: displayed results remain tied to submitted configuration.

## Task 1: Validated data, trailing features and hypotheses
Files: quant_terminal/models.py, data.py, features.py, strategies.py, sample_data/*; tests/test_data_features.py.
Interfaces: Bar, Dataset, CostModel, RiskConfig, ExperimentConfig; load_dataset(asset,path=None); build_features(bars,fast,slow,lookback); make_strategy(name,params) returning target(feature,current_weight).
- [ ] Write and run failures for OHLCV validation and feature prefix invariance.
- [ ] Implement validated typed models, CSV provider, archive importer and two declared hypotheses.
- [ ] Fetch and checksum the bundled snapshot, preserving source terms and provenance.
- [ ] Run tests, inspect CSV and commit.

## Task 2: Independent risk and reconciled simulation
Files: quant_terminal/risk.py, backtest.py; tests/test_backtest_risk.py.
Interfaces: RiskManager.approve_order(quantity,cash,units,price,timestamp); simulate(dataset,strategy,config) -> dict.
- [ ] Write hand-calculated fee/slippage, next-open, rejection, drawdown liquidation and terminal-bar tests; watch failure.
- [ ] Implement target sizing against post-cost equity, risk authorization, cash/basis/episode bookkeeping and complete ledger.
- [ ] Run the entire core suite and commit.

## Task 3: Critic, reproducible experiment and reports
Files: quant_terminal/critic.py, experiment.py, reports.py, run.py, agents.py; tests/test_experiment.py.
Interfaces: run_experiment(config,dataset=None) -> dict; write_artifacts(experiment,out) -> Path; review(result,robustness) -> dict.
- [ ] Write failures for deterministic ID, parameter/cost/window evidence, critic verdicts, self-contained exports and subprocess CLI.
- [ ] Implement fixed robustness runs, comparator, structured findings and canonical source/data/config identity.
- [ ] Generate and inspect real experiment outputs; run core suite and commit.

## Task 4: Runnable dashboard and one-command demo
Files: quant_terminal/dashboard/app.py, demo.py; tests/test_dashboard.py.
- [ ] Write AppTest checks for startup, strategy submission and persisted run identity; watch failure.
- [ ] Implement five tabs, chart/table/report exports, dark theme and demo launch.
- [ ] Install locked dependencies, run tests and launch the actual demo; inspect browser and capture screenshot.

## Task 5: Evidence, documentation and delivery
Files: README.md, DEMO.md, docs/research_design.md, examples/*, .github/workflows/ci.yml, Dockerfile, Makefile, LICENSE.
- [ ] Document actual commands, architecture, risk/critic semantics, metric limits, real/stubbed boundary and roadmap.
- [ ] Format/lint, run all tests, verify installed package from unrelated directory and repeat offline demo ID.
- [ ] Independent whole-project code review; fix confirmed findings with a regression check.
- [ ] Commit complete evidence, create public quant-terminal repository, push, inspect CI and remote revision.
