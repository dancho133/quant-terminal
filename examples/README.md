# Executed examples for technical review

Generated from actual updated runner executions on October 14, 2026. Both use the bundled dataset and default costs/risk/evaluation; results are historical simulations.

| Strategy | Current ID | Verdict | Evidence |
|---|---|---|---|
| Momentum | 986c27a8aad849958ea3 | REJECT | [HTML](986c27a8aad849958ea3/report.html), [Markdown](986c27a8aad849958ea3/report.md), [JSON](986c27a8aad849958ea3/experiment.json) |
| Mean reversion | 67c6d758d1a82087d6ed | CAUTION | [HTML](67c6d758d1a82087d6ed/report.html), [Markdown](67c6d758d1a82087d6ed/report.md), [JSON](67c6d758d1a82087d6ed/experiment.json) |

Each folder also contains equity.svg, drawdown.svg, exposure.svg and trades.csv. HTML embeds its figures. These files are executed output, not mockups or profitability claims.

[Baseline metrics](baseline-e7cf3bd.json) preserve e7cf3bd evidence. Fixing numerical source changes IDs; the default strategy returns remain the same within documented float tolerances. Old report copies were replaced by current reports to avoid ambiguous positioning.

[Verification](verification.md), [actual test log](test-output.txt), [artifact/capture hashes](evidence.json), [internal review](../docs/code_review.md), [reviewer guide](../REVIEWER_GUIDE.md).

```sh
uv run --offline --locked quant-terminal-verify --output artifacts/review
```

Initial dependency installation needs internet. Code is MIT; bundled data and derived reports/charts follow separate noncommercial dataset terms in [NOTICE](../quant_terminal/sample_data/NOTICE.md).
