# Quant Terminal — Research report

Agentic Market Research & Risk Sandbox

**Experiment:** 7838b1e5f5eb082c7e1b  
**Strategy:** mean_reversion · **Asset:** BTCUSDT  
**Evaluation:** 2025-01-01 — 2025-12-31  
**Critic:** CAUTION

## Hypothesis

Buying trailing downside deviations improves evaluation-period return over the same-risk constant-long comparator after costs.

## Dataset

1096 daily bars: 2023-01-01 — 2025-12-31.
Source: Binance Vision spot archives.
Normalized OHLCV SHA-256: c2d7fb5f1c417ebe63a471b88ae2df27c80e0cb7de95e4361ea5ae0f98628c91.
Feature context before evaluation: 731 bars.
The evaluation window is a retrospective split, not proven untouched out-of-sample evidence.

## Parameters and assumptions

~~~json
{
  "asset": "BTCUSDT",
  "costs": {
    "fee_bps": 10.0,
    "slippage_bps": 5.0
  },
  "evaluation_end": "2025-12-31",
  "evaluation_start": "2025-01-01",
  "initial_capital": 10000.0,
  "params": {
    "entry_z": -1.0,
    "exit_z": 0.0,
    "lookback": 20
  },
  "periods_per_year": 365,
  "risk": {
    "max_drawdown": 0.2,
    "max_exposure": 0.5,
    "max_position": 0.25
  },
  "strategy": "mean_reversion"
}
~~~

- Negative deviations revert before persistent drawdown.
- Trailing scale is informative in the next bar.

## Results and metric limitations

| Metric | Value | Limitation |
|---|---:|---|
| total_return | +4.76% | Marked equity change; includes unrealized holdings, excludes their eventual exit cost. |
| benchmark_return | -7.34% | 100% gross buy-and-hold, entered at the second evaluation bar open; contextual, with different risk and zero costs. |
| same_risk_benchmark_return | -0.48% | Constant 40% proposal, independently capped, rebalanced, costed and halted using identical rules; exposure paths can still differ. |
| max_drawdown | +5.63% | Peak-to-trough portfolio equity at daily closes; intrabar losses and close-to-open liquidation gaps can be worse. |
| annualized_volatility | +7.62% | Sample SD of daily portfolio returns times sqrt(365); assumes daily sampling and stable scaling. |
| sharpe_like | 0.65 | Mean daily return / sample SD times sqrt(365), zero cash risk-free rate; no serial-correlation or selection adjustment; null for zero variance. |
| win_rate | +86.67% | Profitable fully closed position episodes / closed episodes. Partial exits and unrealized holdings are excluded. |
| turnover | 8.37 | Gross traded fill notional / initial capital over this evaluation period; includes daily rebalancing. |
| number_of_trades | 15 | Completed position episodes, not individual fills; a final open episode is excluded. |
| transaction_costs | 125.60 | Fees plus adverse slippage versus opening mid price; no order-book impact, funding, taxes or minimum-lot model. |

## Equity and risk

![Equity](equity.svg)

![Drawdown](drawdown.svg)

![Exposure](exposure.svg)

Risk halt: False. Ending holdings: 0.00000000 BTC.
Ending cash: 10475.76 USDT; unrealized PnL: 0.00 USDT.
Estimated remaining exit cost (not deducted from marked return): 0.00 USDT.
Final-close proposals have no execution bar; no forced terminal exit is fabricated.

## Critic analysis

A deterministic screening verdict, not a statistical significance test or permission to trade.

- **CAUTION · FEW_TRADES**: Win rate from few completed position episodes is weak evidence. Observed=15; threshold=20.
- **CAUTION · WINDOW_INSTABILITY**: A nonpositive chronological subwindow shows regime dependence. Observed=[0.058278642128558156, -0.010113196795993318]; threshold=both fixed chronological windows positive.
- **CAUTION · CONCENTRATION**: Invested capital is concentrated in one market; this is not a diversified portfolio. Observed=1.0; threshold=0.8.
- **CAUTION · RETROSPECTIVE_SELECTION**: A retrospective split and familiar baseline parameters cannot establish untouched out-of-sample evidence. Observed=True; threshold=False.

## Fixed robustness checks

Fixed +/-20% neighboring window parameters; base/zero/double costs; chronological half-window resets. Prior bars supply feature warm-up. No best variant selection.

| Scenario | Net return | Closed episodes |
|---|---:|---:|
| zero_cost | +6.03% | 15 |
| base_cost | +4.76% | 15 |
| double_cost | +3.51% | 15 |
| lookback=16 | +2.16% | 15 |
| lookback=24 | +7.76% | 13 |
| first_half: 2025-01-01—2025-07-01 | +5.83% | 8 |
| second_half: 2025-07-02—2025-12-31 | -1.01% | 7 |

## Failure modes

- A falling market stays below its trailing mean.
- Volatility shifts invalidate z-scores.
- Small reversions disappear after costs.

The simulator omits intrabar execution, market impact, exchange lot rules, funding, taxes and live liquidity.
Single-asset and baseline-selection bias remain. No statistical significance claim is made.

## Conclusion

**Evidence is inconclusive; further falsification is required.**

AI proposes. Evidence tests. Risk constrains. Critic challenges.

This repository is a research/paper-trading prototype and is not financial advice or a claim of profitable trading performance.

Historical dataset and derived example outputs: Binance Vision, CC BY-NC-SA 4.0 and supplemental dataset terms. Code: MIT. No affiliation is implied.
