"""Deterministic research rejection checks. A verdict is not an investment endorsement."""

from __future__ import annotations

from typing import Any

THRESHOLDS = {
    "minimum_closed_trades": 20,
    "suspicious_sharpe": 3.0,
    "suspicious_return": 1.0,
    "annualized_turnover": 12.0,
    "cost_drag": 0.05,
    "parameter_return_spread": 0.10,
    "asset_concentration": 0.80,
}


def review(result: dict[str, Any], robustness: dict[str, Any]) -> dict[str, Any]:
    metrics = result["metrics"]
    checks: list[dict[str, Any]] = []

    def check(
        code: str, severity: str, flagged: bool, observed: Any, threshold: Any, reason: str
    ) -> None:
        checks.append(
            {
                "code": code,
                "severity": severity,
                "flagged": bool(flagged),
                "observed": observed,
                "threshold": threshold,
                "reason": reason,
            }
        )

    check(
        "FEW_TRADES",
        "CAUTION",
        metrics["number_of_trades"] < THRESHOLDS["minimum_closed_trades"],
        metrics["number_of_trades"],
        THRESHOLDS["minimum_closed_trades"],
        "Win rate from few completed position episodes is weak evidence.",
    )
    sharpe = metrics["sharpe_like"]
    check(
        "SUSPICIOUS_PERFORMANCE",
        "CAUTION",
        (sharpe is not None and sharpe > THRESHOLDS["suspicious_sharpe"])
        or metrics["total_return"] > THRESHOLDS["suspicious_return"],
        {"sharpe_like": sharpe, "total_return": metrics["total_return"]},
        {"sharpe": THRESHOLDS["suspicious_sharpe"], "return": THRESHOLDS["suspicious_return"]},
        "Large risk-adjusted or absolute returns require independent audit.",
    )
    check(
        "DRAWDOWN_HALT",
        "REJECT",
        result["risk"]["halted"],
        metrics["max_drawdown"],
        result["risk"]["limits"]["max_drawdown"],
        "The declared portfolio drawdown limit halted this simulation; gaps can overshoot it.",
    )
    check(
        "NEGATIVE_RETURN",
        "REJECT",
        metrics["total_return"] < 0,
        metrics["total_return"],
        0,
        "Evaluation-period marked return is negative after modeled costs.",
    )
    matched = metrics["same_risk_benchmark_return"]
    check(
        "BENCHMARK_UNDERPERFORMANCE",
        "REJECT",
        metrics["total_return"] <= matched,
        metrics["total_return"] - matched,
        0,
        "The declared improvement hypothesis failed against the identical-risk constant-long comparator.",
    )
    annual_turnover = (
        metrics["turnover"] * metrics.get("periods_per_year", 365) / metrics["evaluation_bars"]
    )
    check(
        "EXCESSIVE_TURNOVER",
        "CAUTION",
        annual_turnover > THRESHOLDS["annualized_turnover"],
        annual_turnover,
        THRESHOLDS["annualized_turnover"],
        "Annualized gross traded notional can magnify unmodeled execution costs.",
    )
    costs = {s["name"]: s["total_return"] for s in robustness["cost_scenarios"]}
    drag = costs["zero_cost"] - costs["base_cost"]
    check(
        "COST_DRAG",
        "CAUTION",
        drag > THRESHOLDS["cost_drag"],
        drag,
        THRESHOLDS["cost_drag"],
        "The base-cost result loses more than the declared return margin versus zero costs.",
    )
    check(
        "COST_FRAGILITY",
        "REJECT",
        costs["base_cost"] > 0 and costs["double_cost"] <= 0,
        costs["double_cost"],
        0,
        "Positive base return disappears when fees and slippage are doubled.",
    )
    check(
        "WEAK_AFTER_COSTS",
        "REJECT",
        costs["zero_cost"] > 0 and costs["base_cost"] <= 0,
        costs["base_cost"],
        0,
        "A gross-positive result disappears after base transaction costs.",
    )
    variants = [
        metrics["total_return"],
        *(s["total_return"] for s in robustness["parameter_variants"]),
    ]
    spread = max(variants) - min(variants)
    check(
        "PARAMETER_SENSITIVITY",
        "CAUTION",
        spread > THRESHOLDS["parameter_return_spread"],
        spread,
        THRESHOLDS["parameter_return_spread"],
        "Fixed neighboring parameters change return substantially; no best variant is selected.",
    )
    windows = [s["total_return"] for s in robustness["time_windows"]]
    check(
        "WINDOW_INSTABILITY",
        "CAUTION",
        any(v <= 0 for v in windows),
        windows,
        "both fixed chronological windows positive",
        "A nonpositive chronological subwindow shows regime dependence.",
    )
    check(
        "WINDOW_SAMPLE",
        "CAUTION",
        len(windows) < 2,
        len(windows),
        2,
        "The evaluation window is too short for two separate chronological reruns.",
    )
    concentration = metrics.get("asset_concentration", 1.0)
    check(
        "CONCENTRATION",
        "CAUTION",
        concentration > THRESHOLDS["asset_concentration"],
        concentration,
        THRESHOLDS["asset_concentration"],
        "Invested capital is concentrated in one market; this is not a diversified portfolio.",
    )
    check(
        "RETROSPECTIVE_SELECTION",
        "CAUTION",
        robustness.get("retrospective_selection", True),
        robustness.get("retrospective_selection", True),
        False,
        "A retrospective split and familiar baseline parameters cannot establish untouched out-of-sample evidence.",
    )
    flagged = [c for c in checks if c["flagged"]]
    verdict = (
        "REJECT"
        if any(c["severity"] == "REJECT" for c in flagged)
        else "CAUTION"
        if flagged
        else "PASS"
    )
    conclusion = {
        "REJECT": "Hypothesis rejected.",
        "CAUTION": "Evidence is inconclusive; further falsification is required.",
        "PASS": "The declared checks passed; profitability and live suitability remain unproven.",
    }[verdict]
    return {
        "verdict": verdict,
        "conclusion": conclusion,
        "checks": checks,
        "reasons": [c["reason"] for c in flagged],
        "thresholds": THRESHOLDS,
        "interpretation": "A deterministic screening verdict, not a statistical significance test or permission to trade.",
    }
