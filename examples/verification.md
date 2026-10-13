# Executed verification — October 13, 2026

Local environment: Windows, CPython 3.12.13, uv 0.12.3, Streamlit 1.65.0, Matplotlib 3.11.2, Ruff 0.17.0. Dependencies are recorded in uv.lock.

| Check | Actual result |
|---|---|
| Dependency installation / locked sync | Completed |
| Ruff lint | All checks passed |
| Ruff format check | All source files already formatted |
| Full unittest suite | 26 tests, 0 failures/errors |
| Hand-calculated next-open fees, slippage and PnL | Passed |
| Risk authorization, target cap, drawdown latch and delayed liquidation | Passed |
| Final holdings, unfilled orders and cost-basis reconciliation | Passed |
| Future-bar feature/ledger/fill mutation | Passed |
| Critic PASS/CAUTION/REJECT and robustness checks | Passed |
| Int/float equivalents across API/CLI defaults | Same experiment identity |
| Surplus/missing CSV fields, malformed manifest and parser errors | Controlled rejection with no artifact |
| User CSV source/terms reporting | No invented provider attribution |
| One-command real dashboard startup | Executed; localhost server started |
| API / CLI / dashboard default run | Momentum ID bbc87bc1d4ee46e327d3 |
| Mean-reversion form submission | ID 7838b1e5f5eb082c7e1b, CAUTION |
| Browser inspection | All five tabs, actual charts, controls, criticism and JSON download checked |
| Self-contained HTML report | Opened in browser; SVG figures and structured evidence rendered |
| Offline two-baseline run | Executed with uv --offline --locked |
| Wheel and source distribution | Successfully built |
| Fresh installed-wheel run | Both baselines executed from a directory outside the repository |
| Installed wheel vs source artifacts | Complete numerical JSON objects equal |
| Historical source integrity | All 36 archive SHA-256 values verified; 1096 consecutive valid daily bars |
| Fresh clone of the public GitHub repository | Both demo baselines and all 26 tests passed |

See [test-output.txt](test-output.txt) for the actual full local test log, and
[evidence.json](evidence.json) for checksums, sizes, metrics and engine identity.

Browser captures:
[overview](../docs/images/dashboard-overview.jpg),
[mean reversion](../docs/images/dashboard-mean-reversion.jpg),
[performance](../docs/images/dashboard-performance.jpg),
[HTML report](../docs/images/research-report.jpg).
Captures include the actual experiment IDs, not illustrative placeholders.

The [active workflow](../.github/workflows/ci.yml) targets Linux and Windows with Python 3.11 and 3.12. It runs lint, formatting, all tests, both offline baselines and packaging. Access was explicitly approved and the GitHub CLI token's workflow scope was verified before publication. Inspect [GitHub Actions](https://github.com/dancho133/quant-terminal/actions) for the current remote result; local and fresh-clone evidence is recorded separately here.

Dockerfile is provided, but Docker was unavailable locally and no container build/run is claimed.
No live broker connection, real-money order, LLM/API invocation, or production deployment was performed.
