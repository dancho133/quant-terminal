# Quant Terminal design

Purpose: a runnable engineering portfolio for a trading/AI team. This is an experimental historical research and paper-trading sandbox. No live execution, LLM service, profitability claim, or secrets.

## Workspace and scope
The shared Codex directory contained unrelated work and no identified implementation. This project is a separate Git repository. A compact Python package and one Streamlit dashboard fulfill the brief. A service architecture or opaque backtesting dependency would add convention and operational complexity.

## Data and causality
Include a fixed BTCUSDT daily OHLCV snapshot for 2023-2025 from public archives with original archive checksums, normalized CSV checksum, timestamps in UTC, provenance and separate upstream dataset terms. A small synthetic fixture exists only for hand-calculated tests. Validation rejects missing daily bars, duplicate/unordered timestamps, non-finite/nonpositive prices, inconsistent ranges and negative volume.
Features are trailing only: daily return, two moving averages, rolling realized volatility, momentum, volume change, and z-score. Unavailable warm-up values remain unavailable.
Two predeclared baselines: momentum fast=20/slow=50; mean reversion lookback=20/entry_z=-1/exit_z=0. Both long-only. No parameter search or selection.

## Execution contract
At close t, strategy proposes a target weight; risk clamps or rejects it. Fill only at open t+1, with adverse directional slippage and fee deductions. Fractional BTC, no borrowing, no shorting; cash plus marked holdings equals equity.
Daily target-weight rebalancing; risk rechecks post-cost exposure at the actual opening price. Independent order validation rejects invalid, short, unaffordable and oversized orders. Risk decisions preserve requested and allowed targets, observed values and limits.
Drawdown is sampled at closes. A drawdown breach permanently halts new entries and requests liquidation at the next open. Gaps can overshoot a threshold; limits cannot guarantee maximum realized loss. Exposure drift is flagged at closes and adjusted at the next open.
The final close is marked, never given a fabricated exit. Pending orders and unresolved halted exposure are recorded. Win rate uses only fully closed position episodes, distinct from individual fills.

## Research and critic
Default development context is 2023-2024 and chronological evaluation is 2025; parameters are declared before evaluating. This retrospective split is not proof of untouched out-of-sample evidence.
Record base, zero-cost and double-cost runs; fixed neighboring parameter runs and two chronological half-windows. Do not choose the best variant. Critic uses visible predeclared thresholds, observations and findings to return PASS/CAUTION/REJECT.
Report full-exposure gross buy-and-hold as a contextual benchmark and a comparator run using identical risk/cost rules and a constant strategy target. No misleading equivalence between different exposures.
Few closed episodes, single-asset concentration and retrospective selection yield CAUTION. A risk halt, negative evaluation return, severe cost fragility or failure of the stated benchmark-relative hypothesis can yield REJECT. Successful risk rejection alone is not research failure. PASS is only satisfaction of these checks.

## Artifacts and presentation
Hash canonical configuration, OHLCV identity and hashes of all numerical engine source files into the experiment ID. Normalize equivalent continuous numeric values before hashing. Exclude wall-clock metadata from canonical output. Persist complete fills, position episodes, bar ledger, risk events, outstanding orders, critic and robustness evidence as JSON; generate self-contained HTML, Markdown and Matplotlib SVG charts from that artifact.
Streamlit controls invoke the same runner on explicit submit and display completed artifacts. Five tabs: Overview, Performance, Trades, Risk, Research. Export JSON and report.
Typed ResearchAgent, StrategyAgent, RiskAgent, CriticAgent protocols document future integration; no implemented LLM agents.
One command uv run quant-terminal-demo installs locked dependencies when needed, produces examples and starts dashboard. Offline runtime after dependency installation. Numerical computation uses the standard library; full CLI report output needs the declared Matplotlib dependency.

## Acceptance
Hand-calculated next-open/slippage/fee ledger; order rejection; permanent halt and next-open liquidation; future-data mutation/prefix invariance; validation failures; closed episode PnL plus unrealized basis reconciliation; critic verdict boundaries; ID changes for data/config/engine, repeatability; CLI artifacts; dashboard submit/export and all tabs; installable wheel from unrelated directory; formatting, lint, core/dashboard suite; real browser screenshot if available.
GitHub publication is explicitly authorized by the brief. Only this project is published. Record actual local and CI evidence separately.
