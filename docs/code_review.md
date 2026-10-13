# Independent implementation review

A fresh reviewer inspected the full implementation, documentation, CI and packaging. It independently ran the 13 data/features/accounting/risk tests and used temporary files to reproduce input and identity failures. This was a software review, not investment or legal validation.

The initial verdict was **With fixes**: two Important and two initially Minor findings, no established Critical finding. The integration owner treated all four as required corrections because reliable identity, invalid-data handling and truthful evidence are explicit requirements.

| Confirmed defect | Correction | Regression |
|---|---|---|
| Equal numeric values produced different IDs across API/CLI/UI | Normalize continuous config fields and z-score parameters; retain integer windows | test_semantically_equal_numeric_defaults_share_identity |
| CSV row surplus fields were discarded | Reject any row without exactly six nonempty fields, including the row number | test_csv_rejects_extra_and_missing_row_fields |
| Array manifest and oversized CSV field escaped the CLI error boundary | Require a JSON-object manifest; wrap csv.Error as invalid data | test_malformed_manifest_and_oversized_csv_fail_without_traceback |
| Custom CSV received false source/terms labels | Derive scope and licensing language from actual provenance | test_custom_csv_reports_preserve_unknown_provenance_and_terms |

Each regression was reproduced before its fix; the final full suite passed **26/26**. No second review round or reviewer consensus is used as a substitute for those checks.

The reviewer found no additional actionable defect in delayed drawdown liquidation, final marked holdings, partial cost-basis reconciliation, post-cost exposure sizing, UI draft/submitted state or the absence of parameter-winner selection.

Review boundaries: upstream legal terms, actual remote CI, browser visual rendering and installed-wheel behavior were not certified by the reviewer. The owner verified the source terms, browser rendering/export and fresh-wheel execution separately. Docker remained unexecuted because the CLI was unavailable.
