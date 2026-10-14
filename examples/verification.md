# Executed verification — October 14, 2026

Preparation for independent technical review. This record describes developer-run evidence, not BYTRADER certification or investment validation. Source engine SHA-256: cad560d776cb4be902fd983a28edf6a27815dd46e94cc173edb436e7bb09cce8. Dataset SHA-256: c2d7fb5f1c417ebe63a471b88ae2df27c80e0cb7de95e4361ea5ae0f98628c91.

## Current local execution

Windows, CPython 3.12.13. uv.lock pins the installed dependencies. The numerical source differs from the e7cf3bd baseline.

| Command / check | Actual result |
|---|---|
| uv sync --locked --group dev | Exit 0; 47 packages resolved, 45 checked |
| uv run --locked ruff check . | Exit 0; All checks passed |
| uv run --locked ruff format --check . | Exit 0; 35 Python files already formatted |
| uv run --locked python -m unittest discover -s tests -v | Exit 0; **47 tests**, no failures/errors |
| uv run --offline --locked quant-terminal-demo --no-ui | Exit 0; both real experiments exported |
| uv run --offline --locked quant-terminal-verify | Exit 0; **12 aggregate checks**, failures empty |
| uv build | Wheel and source distribution built, exit 0 |
| Locked runtime requirements installed in a new venv | 43 dependencies installed; no system-site-packages |
| Built wheel installed, run outside the source checkout | Import path is the new venv's Lib/site-packages/quant_terminal |
| Installed wheel verifier with --reference-dir source results | Exit 0; **14 checks**, both canonical JSON artifacts equal within stated tolerances |
| Fresh public branch clone + fresh locked venv | Ruff, all 47 tests, offline demo and verifier/reference comparison passed; checkout stayed clean |
| GitHub Actions for source commit 77dbb5e | Four jobs passed: Ubuntu/Windows × Python 3.11/3.12; lint, format, 47 tests, demo, verification and packaging |
| Actual browser | Updated UI, all five tabs, real mean_reversion form submission and both final IDs checked |
| Report rendering | Self-contained updated HTML exported to disk; embedded figures rendered in browser |

The test log contains an intentionally injected checksum failure message from the bootstrap-error regression; the **suite summary is 47 tests / OK / exit 0**. Streamlit AppTest can emit its standard bare-mode missing ScriptRunContext warning; no UI exception or Arrow repair was observed.

Current default outputs: momentum **986c27a8aad849958ea3**, −0.62%, 14 closed episodes, REJECT; mean_reversion **67c6d758d1a82087d6ed**, +4.76%, 15 closed episodes, CAUTION. Both remain retrospective historical simulations.

## Revision and CI provenance

At **e7cf3bd**, 26 tests passed and the IDs were bbc87bc1d4ee46e327d3 / 7838b1e5f5eb082c7e1b. Its final [CI run](https://github.com/dancho133/quant-terminal/actions/runs/38438374392) passed all four Linux/Windows × Python 3.11/3.12 jobs. That historical result does not validate this changed source. [ci-result.json](ci-result.json) now records the current source run separately from that baseline.

The updated numerical source is commit **77dbb5e0b9caf355fb31f052f4ddf9fb0202a230**. Its [verified CI run](https://github.com/dancho133/quant-terminal/actions/runs/38525185413) completed successfully in all four jobs. The fresh clone and installed wheel both reproduced that engine. [verification.json](verification.json) captures a clean checkout with 14 checks including comparison to current examples, no failures, and the exact source SHA. Its absolute paths refer to the capture machine; rerun the command to obtain local paths. Later evidence-only commits do not change numerical source. Use the generated verification.json for checked_commit, worktree_dirty, engine/data hashes, commands, checks, failures and artifact_paths. A dirty checkout's SHA is its base commit; the source fingerprint identifies the executed files. An installed wheel's source SHA is explicitly declared, not independently inferred.

## Scope and unavailable checks

Docker CLI is unavailable locally; no container build/run is claimed. The HTML/JSON/CSV exports on disk are verified. The browser click on HTML download was exercised, but this automation did not deliver a download event or confirmed saved path; end-to-end browser download persistence is **unverified**. No completed video recording is claimed; DEMO.md supplies the 55-second script.

No live broker connection, real-money order, working LLM agent or production deployment was performed. Shared indicator/strategy and stress-simulator logic is disclosed in REVIEWER_GUIDE.md; successful checks do not prove the entire financial model correct.

[Full current test log](test-output.txt) · [Artifact/capture evidence](evidence.json) · [Internal software review](../docs/code_review.md).
