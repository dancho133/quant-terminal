# Internal AI-assisted software review

This document records developer-run checks and reviews assisted by OpenAI Codex. It is not a BYTRADER audit, external certification, investment review or claim of complete model correctness. A separate reviewer agent examined the implementation and attempted adversarial reproductions; the integration owner verified fixes through failing-then-passing tests.

## Baseline e7cf3bd

The baseline passed 26 unittest tests. Earlier internal review reproduced and fixed numeric int/float identity differences, ignored surplus CSV fields, uncontrolled malformed-manifest/parser errors, and invented attribution for custom CSVs. That earlier evidence is historical; it does not validate subsequent changes. Baseline IDs were bbc87bc1d4ee46e327d3 and 7838b1e5f5eb082c7e1b.

## Preparation defects and regressions

| Reproduced defect | Correction | Regression |
|---|---|---|
| 1000→800 loss failed the exact 20% halt because 1−800/1000 rounds below 0.2 | Compare close equity with peak × (1−threshold) | `test_exact_drawdown_threshold_halts_before_a_next_day_rebound` |
| Absolute BTC thresholds skipped valid small-capital fills and erased residual position value | Relative notional/equity rebalance tolerance; preserve positive units/cash | `test_fractional_accounting_is_invariant_to_capital_scale`; `test_small_positive_position_is_not_discarded_at_high_price` |
| Order authorization allowed a small negative position from empty holdings | Reject every quantity below −units | `test_risk_gate_rejects_nonnumeric_proposals_and_any_short_quantity` |
| Full-sale algebra left a tiny residual and failed to close an episode | Zero target returns exactly −units | `test_zero_target_sells_exact_holdings_without_a_rounding_residue` |
| Relative rebalance threshold skipped a required zero-target exit after a very large gap | Every nonzero liquidation bypasses the materiality threshold | `test_drawdown_liquidation_is_never_skipped_as_immaterial_after_a_gap` |
| Noncanonical ISO dates were accepted then compared lexically | Require canonical YYYY-MM-DD strings | `test_noncanonical_or_nonstrings_dates_are_rejected_at_configuration` |
| Requested dates outside the snapshot were silently clipped | Reject out-of-dataset evaluation boundaries | `test_requested_window_cannot_be_silently_clipped_to_dataset` |
| Boolean configuration was accepted; nonnumeric values caused TypeError; empty-list params became defaults | Explicit financial-number and parameter-object validation | `tests.test_validation`; gate nonnumeric regression |
| Unterminated CSV quote was accepted as a number | Strict CSV parsing | `test_unterminated_csv_quote_is_not_a_valid_number` |
| Turnover critic/report descriptions ignored configured periods_per_year | Propagate year length into metric/critic/display | `test_annualized_turnover_and_report_use_the_configured_year_length` |
| Extreme ratios entered statistics as infinity; gross benchmark multiplied huge prices before normalizing | Reject non-finite ratios; normalize benchmark first | Extreme-ratio / gross-benchmark tests in `tests.test_validation` |

The API/CLI input regressions include malformed params, nonnumeric capital, NaN costs, invalid dates and controlled failure without generated artifacts. All numerical fixes are small changes in their owning modules; no broker, provider framework or agent service was added.

## Verification command review

A separate review of the new checker found false-success paths for changed dataset metadata, risk events, fabricated robustness returns with a recomputed critic, and an XML root named notsvg. An empty ledger and bootstrap checksum failure also escaped the JSON-summary boundary. Each case was tested before correction.

The checker now validates complete dataset/config/source identity; reconstructs strategy and comparator accounting, signal/fill timing, caps, drawdown latch and events; reruns all declared stress configurations and separately reconciles their ledgers; checks numerical stress metrics; verifies SVG namespaces and CSV correspondence; and records supported initialization/structural failures in verification.json with nonzero exit status.

`tests.test_verification` deliberately changes cash, PnL, fees, signal times, config, engine/data metadata, approval/cap events, maximum drawdown, pending flags, comparator, critic, stress results, NaN, CSV and SVG. This tests that the checker can reject damaged evidence; it is not a proof of complete model correctness.

## Remaining review limits

Account replay does not call the production simulator, RiskManager or metric calculator, but it uses shared feature/strategy functions and standard floating-point arithmetic. Stress reruns use the same simulator; they verify configuration/export consistency, not an alternative market model. Synthetic fixtures validate arithmetic and chronology rather than market profitability.

No statistical significance, calibrated liquidity, intrabar stop, independent upstream price certification, real broker reconciliation or prospective strategy validation is established. Read REVIEWER_GUIDE.md for an assertion-to-code/test map and examples/verification.md for actual current execution evidence. Docker is reported separately if unavailable.
