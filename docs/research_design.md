# Research design and failure boundaries

## Separate proposals, authorization and accounting

A strategy sees trailing features and current weight. It proposes a target, never a fill. The independent RiskManager constrains that target, computes quantities against post-cost marked equity and authorizes each order. The simulator owns the ledger, cost basis and execution chronology. A future AI adapter inherits exactly this boundary; it cannot change limits or obtain execution credentials.

Fees are charged on actual slipped notional. For a buy, the target-sizing equation is
`(units + q) * open = target * (equity - q * (buy_cost_per_unit - open))`.
For a sell, use `(units - q) * open = target * (equity - q * (open - sell_proceeds_per_unit))`.
This avoids capping pre-cost equity while executing an oversized post-cost position.

Daily target rebalancing is explicit. Fractional BTC and unrestricted fill liquidity are simplifications. Exposure is authorized at the open, then may drift with prices. Drawdown is sampled at the close. A breach latches the halt and queues a next-open exit; adverse gaps and transaction costs can take realized losses beyond the threshold.

## Independent critic

The critic receives results plus fixed robustness evidence. Its rules cannot be replaced by strategy prose or favorable PnL. It distinguishes functioning rejection of a prohibited order from failure of the stated research hypothesis.

Thresholds are visible, heuristic and not calibrated probabilities. Few closed episodes and single-market concentration limit inference. PASS only means those specific checks passed. REJECT is a useful research outcome.

## Look-ahead bias

The close of bar t is available only after that bar finishes. Features use trailing slices; no backfill or centered windows. A decision made after that close can execute only at open t+1. The final close has no future execution bar: existing holdings remain marked, a pending trade is unfilled, and remaining exit cost is estimated outside reported return.

Tests alter later bars and require earlier features, fills and ledger entries to remain identical. This catches direct numerical leakage, not every possible dataset-origin problem.

## Overfitting and selection

Two familiar baselines are declared in code. The default 2023-2024 context / 2025 evaluation split is retrospective, not certified untouched out-of-sample research. Fixed +/-20% window neighbors and chronological half-window resets expose fragility; they do not select a best parameter.

Repeated developer inspection, strategy choice, asset choice and sample choice are all sources of selection bias. No p-value, statistical-significance label or profitability claim is produced. A prospective registered protocol and walk-forward testing are still required.

## Costs and benchmark interpretation

Fees and adverse slippage apply to every fill, including rebalances and risk liquidation. The engine reruns at zero, base and twice base costs. These are controlled stress scenarios, not fitted estimates of live liquidity.

Gross 100%-invested buy-and-hold is context with different exposure. The constant-long comparator uses the same capital, 40% proposal, risk limits, fill chronology and costs. Its realized exposure path and halt timing can still differ from a selective strategy.

## Why backtests can lie

OHLCV omits spreads, order-book depth, intrabar sequencing and rejected exchange fills. A fixed daily slippage cannot model size-dependent impact. This model ignores funding, taxes, lot rules, settlement, USDT depegging and live operational failures. Close-sampled risk understates intraday excursions.

Marked final equity includes unrealized holdings; closed-episode win rate excludes them. Volatility and the Sharpe-like ratio assume daily scaling and zero cash yield. Serial correlation, multiple trials and short samples invalidate naive confidence claims.

The provided data has recorded source checksums; integrity does not prove exchange data completeness or fitness for execution. The market-data terms are separate from the code license.

## Before any live deployment

An actual production path would require appropriately licensed point-in-time data, independently reconciled execution/accounting, realistic liquidity and cost measurements, portfolio risk, prospective evaluation, and extended observable paper/shadow operation. Operational work includes stale-data rejection, idempotent order handling, reconciliation against a broker, a separate kill switch, credentials isolated from agents and explicit human deployment control.

None of that live execution infrastructure exists here. The repository is an engineering research demonstration.
