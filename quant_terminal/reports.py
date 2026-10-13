"""Human-readable reports and standalone plots rendered from a canonical experiment."""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

DISCLAIMER = "This repository is a research/paper-trading prototype and is not financial advice or a claim of profitable trading performance."
BINANCE_TERMS = "Historical dataset and derived example outputs: Binance Vision, CC BY-NC-SA 4.0 and supplemental dataset terms. Code: MIT. No affiliation is implied."
METRIC_LIMITATIONS = {
    "total_return": "Marked equity change; includes unrealized holdings, excludes their eventual exit cost.",
    "benchmark_return": "100% gross buy-and-hold, entered at the second evaluation bar open; contextual, with different risk and zero costs.",
    "same_risk_benchmark_return": "Constant 40% proposal, independently capped, rebalanced, costed and halted using identical rules; exposure paths can still differ.",
    "max_drawdown": "Peak-to-trough portfolio equity at daily closes; intrabar losses and close-to-open liquidation gaps can be worse.",
    "annualized_volatility": "Sample SD of daily portfolio returns times sqrt(365); assumes daily sampling and stable scaling.",
    "sharpe_like": "Mean daily return / sample SD times sqrt(365), zero cash risk-free rate; no serial-correlation or selection adjustment; null for zero variance.",
    "win_rate": "Profitable fully closed position episodes / closed episodes. Partial exits and unrealized holdings are excluded.",
    "turnover": "Gross traded fill notional / initial capital over this evaluation period; includes daily rebalancing.",
    "number_of_trades": "Completed position episodes, not individual fills; a final open episode is excluded.",
    "transaction_costs": "Fees plus adverse slippage versus opening mid price; no order-book impact, funding, taxes or minimum-lot model.",
}


def _percent(value: float) -> str:
    return f"{value:+.2%}"


def metric_display(name: str, value: Any) -> str:
    if value is None:
        return "N/A"
    if name in ("number_of_trades", "fill_count", "evaluation_bars"):
        return str(value)
    if name in (
        "total_return",
        "benchmark_return",
        "same_risk_benchmark_return",
        "max_drawdown",
        "annualized_volatility",
        "win_rate",
        "max_exposure",
        "average_exposure",
    ):
        return _percent(value)
    if name in ("turnover", "sharpe_like"):
        return f"{value:.2f}"
    return f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)


def chart_svg(artifact: dict[str, Any], kind: str) -> str:
    result = artifact["result"]
    rows = result["ledger"]
    comparator = artifact["comparator"]["ledger"]
    dates = [r["timestamp"][:10] for r in rows]
    x = list(range(len(rows)))
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": artifact["experiment_id"],
            "font.family": "DejaVu Sans",
        }
    )
    with plt.rc_context(
        {
            "figure.facecolor": "#10171f",
            "axes.facecolor": "#10171f",
            "text.color": "#dce6ef",
            "axes.labelcolor": "#a3b5c4",
            "xtick.color": "#a3b5c4",
            "ytick.color": "#a3b5c4",
            "axes.edgecolor": "#293846",
        }
    ):
        fig, ax = plt.subplots(figsize=(11, 3.5), constrained_layout=True)
        if kind == "equity":
            ax.plot(
                x,
                [r["equity"] for r in rows],
                color="#5cbfb5",
                linewidth=1.8,
                label="Strategy, after costs",
            )
            ax.plot(
                x,
                [r["equity"] for r in comparator],
                color="#9aaac5",
                linewidth=1.3,
                linestyle="--",
                label="Same-risk constant-long",
            )
            ax.plot(
                x,
                [r["benchmark_equity"] for r in rows],
                color="#d0a56b",
                linewidth=1,
                alpha=0.8,
                label="100% gross buy-and-hold",
            )
            ax.set_ylabel("Marked equity (USDT)")
        elif kind == "drawdown":
            values = [-100 * r["drawdown"] for r in rows]
            ax.fill_between(x, values, 0, color="#d17b7b", alpha=0.28)
            ax.plot(x, values, color="#d17b7b", linewidth=1.3, label="Close-sampled drawdown")
            ax.axhline(
                -100 * artifact["config"]["risk"]["max_drawdown"],
                color="#c9a56d",
                linestyle=":",
                linewidth=1,
                label="Halt threshold",
            )
            ax.set_ylabel("Drawdown (%)")
        elif kind == "exposure":
            ax.plot(
                x,
                [100 * r["exposure"] for r in rows],
                color="#78a8cc",
                linewidth=1.3,
                label="Close exposure",
            )
            cap = min(
                artifact["config"]["risk"]["max_position"],
                artifact["config"]["risk"]["max_exposure"],
            )
            ax.axhline(100 * cap, color="#c9a56d", linestyle=":", label="Next-fill cap")
            ax.set_ylabel("Portfolio exposure (%)")
        else:
            raise ValueError(f"Unknown chart: {kind}")
        ticks = sorted({0, *(round(i * (len(x) - 1) / 4) for i in range(1, 5))})
        ax.set_xticks(ticks, [dates[i] for i in ticks])
        ax.tick_params(labelsize=9)
        ax.grid(axis="y", color="#293846", linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="best", frameon=False, fontsize=8)
        stream = io.StringIO()
        fig.savefig(stream, format="svg", metadata={"Date": None})
        plt.close(fig)
    svg = stream.getvalue()
    return svg[svg.index("<svg") :]


def _escape(value: Any) -> str:
    return html.escape(str(value))


def _rows_table(headers: list[str], rows: list[list[Any]]) -> str:
    e = _escape
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{e(c)}</th>" for c in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def dataset_terms(artifact: dict[str, Any]) -> str:
    provenance = artifact["dataset"]["provenance"]
    if (
        provenance.get("kind") == "historical_public_snapshot"
        and provenance.get("source") == "Binance Vision spot archives"
    ):
        return BINANCE_TERMS
    if provenance.get("kind") == "synthetic":
        return "Synthetic fixture, not historical market evidence. Source and data licensing are supplied by the fixture author. Program code: MIT."
    if provenance.get("license"):
        return f"Provider-declared dataset terms (unverified): {provenance['license']}. Program code: MIT."
    return "User-provided dataset. Source and licensing terms are unverified; no market-data provider attribution or redistribution permission is inferred. Program code: MIT."


def markdown_report(artifact: dict[str, Any]) -> str:
    cfg, data = artifact["config"], artifact["dataset"]
    strategy, result, critic = artifact["strategy"], artifact["result"], artifact["critic"]
    metrics = result["metrics"]
    lines = [
        "# Quant Terminal — Research report",
        "",
        "Agentic Market Research & Risk Sandbox",
        "",
        f"**Experiment:** {artifact['experiment_id']}  ",
        f"**Strategy:** {strategy['name']} · **Asset:** {cfg['asset']}  ",
        f"**Evaluation:** {data['evaluation_start'][:10]} — {data['evaluation_end'][:10]}  ",
        f"**Critic:** {critic['verdict']}",
        "",
        "## Hypothesis",
        "",
        strategy["hypothesis"],
        "",
        "## Dataset",
        "",
        f"{data['rows']} daily bars: {data['start'][:10]} — {data['end'][:10]}.",
        f"Source: {data['provenance'].get('source', data['provenance'].get('description', 'Provided data'))}.",
        f"Normalized OHLCV SHA-256: {data['sha256']}.",
        f"Feature context before evaluation: {data['prior_context_bars']} bars.",
        "The evaluation window is a retrospective split, not proven untouched out-of-sample evidence.",
        "",
        "## Parameters and assumptions",
        "",
        "~~~json",
        json.dumps(cfg, indent=2, sort_keys=True),
        "~~~",
        "",
        *(f"- {s}" for s in strategy["assumptions"]),
        "",
        "## Results and metric limitations",
        "",
        "| Metric | Value | Limitation |",
        "|---|---:|---|",
        *(
            f"| {key} | {metric_display(key, metrics[key])} | {limitation} |"
            for key, limitation in METRIC_LIMITATIONS.items()
        ),
        "",
        "## Equity and risk",
        "",
        "![Equity](equity.svg)",
        "",
        "![Drawdown](drawdown.svg)",
        "",
        "![Exposure](exposure.svg)",
        "",
        f"Risk halt: {result['risk']['halted']}. Ending holdings: {result['ending_position']['units']:.8f} BTC.",
        f"Ending cash: {result['ending_position']['cash']:.2f} USDT; unrealized PnL: {result['ending_position']['unrealized_pnl']:.2f} USDT.",
        f"Estimated remaining exit cost (not deducted from marked return): {result['ending_position']['estimated_exit_cost']:.2f} USDT.",
        "Final-close proposals have no execution bar; no forced terminal exit is fabricated.",
        "",
        "## Critic analysis",
        "",
        critic["interpretation"],
        "",
        *(
            f"- **{c['severity']} · {c['code']}**: {c['reason']} Observed={c['observed']}; threshold={c['threshold']}."
            for c in critic["checks"]
            if c["flagged"]
        ),
        "",
        "## Fixed robustness checks",
        "",
        artifact["robustness"]["method"],
        "",
        "| Scenario | Net return | Closed episodes |",
        "|---|---:|---:|",
        *(
            f"| {s['name']} | {_percent(s['total_return'])} | {s['number_of_trades']} |"
            for s in artifact["robustness"]["cost_scenarios"]
        ),
        *(
            f"| {s['changed_parameter']}={s['params'][s['changed_parameter']]} | {_percent(s['total_return'])} | {s['number_of_trades']} |"
            for s in artifact["robustness"]["parameter_variants"]
        ),
        *(
            f"| {s['name']}: {s['start']}—{s['end']} | {_percent(s['total_return'])} | {s['number_of_trades']} |"
            for s in artifact["robustness"]["time_windows"]
        ),
        "",
        "## Failure modes",
        "",
        *(f"- {s}" for s in strategy["failure_modes"]),
        "",
        "The simulator omits intrabar execution, market impact, exchange lot rules, funding, taxes and live liquidity.",
        "Single-asset and baseline-selection bias remain. No statistical significance claim is made.",
        "",
        "## Conclusion",
        "",
        f"**{critic['conclusion']}**",
        "",
        "AI proposes. Evidence tests. Risk constrains. Critic challenges.",
        "",
        DISCLAIMER,
        "",
        dataset_terms(artifact),
        "",
    ]
    return "\n".join(lines)


def html_report(artifact: dict[str, Any], charts: dict[str, str] | None = None) -> str:
    charts = charts or {
        kind: chart_svg(artifact, kind) for kind in ("equity", "drawdown", "exposure")
    }
    e = _escape
    cfg, data, result, critic = (
        artifact["config"],
        artifact["dataset"],
        artifact["result"],
        artifact["critic"],
    )
    metrics = result["metrics"]
    cards = "".join(
        f"<article><span>{e(label)}</span><strong>{e(metric_display(key, metrics[key]))}</strong></article>"
        for label, key in (
            ("NET RETURN", "total_return"),
            ("SAME-RISK COMPARATOR", "same_risk_benchmark_return"),
            ("MAX DRAWDOWN", "max_drawdown"),
            ("CLOSED EPISODES", "number_of_trades"),
        )
    )
    metrics_table = _rows_table(
        ["Metric", "Value", "Interpretation / limit"],
        [
            [key, metric_display(key, metrics[key]), limitation]
            for key, limitation in METRIC_LIMITATIONS.items()
        ],
    )
    checks_table = _rows_table(
        ["Check", "Status", "Observed", "Threshold", "Reason"],
        [
            [
                c["code"],
                c["severity"] if c["flagged"] else "CLEAR",
                c["observed"],
                c["threshold"],
                c["reason"],
            ]
            for c in critic["checks"]
        ],
    )
    robustness = artifact["robustness"]
    scenarios = _rows_table(
        ["Scenario", "Net return", "Closed episodes"],
        [
            [s["name"], _percent(s["total_return"]), s["number_of_trades"]]
            for s in robustness["cost_scenarios"]
        ]
        + [
            [
                f"{s['changed_parameter']}={s['params'][s['changed_parameter']]}",
                _percent(s["total_return"]),
                s["number_of_trades"],
            ]
            for s in robustness["parameter_variants"]
        ]
        + [
            [
                f"{s['name']} ({s['start']} to {s['end']})",
                _percent(s["total_return"]),
                s["number_of_trades"],
            ]
            for s in robustness["time_windows"]
        ],
    )
    fills_table = _rows_table(
        ["Timestamp", "Side", "BTC", "Fill price", "Fee", "Slippage", "Realized PnL"],
        [
            [
                f["timestamp"][:10],
                f["side"],
                f"{f['quantity']:.8f}",
                f"{f['price']:.2f}",
                f"{f['fee']:.4f}",
                f"{f['slippage_cost']:.4f}",
                "—" if f["realized_pnl"] is None else f"{f['realized_pnl']:.4f}",
            ]
            for f in result["fills"]
        ],
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quant Terminal · {e(artifact["experiment_id"])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#0d1117;color:#e3eaf2;font:15px/1.6 system-ui,sans-serif}}
main{{max-width:1200px;margin:auto;padding:42px 28px}}h1{{font-size:36px;letter-spacing:-1px;margin:5px 0}}
h2{{font-size:22px;margin-top:38px}}p,li{{color:#b7c5d3}}.eyebrow{{color:#5cbfb5;font:12px monospace;letter-spacing:2px}}
.meta{{font:13px monospace;color:#a0b2c4}}.verdict{{border-left:3px solid #ce9f66;background:#151c25;padding:16px 22px;margin:24px 0}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}article{{background:#151c25;border:1px solid #293846;padding:20px;border-radius:7px}}
article span{{display:block;font:11px monospace;color:#9dafc0;letter-spacing:1px}}article strong{{font-size:25px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #293846;vertical-align:top}}
th{{color:#5cbfb5}}.scroll{{overflow:auto}}svg{{width:100%;height:auto;display:block}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#151c25;padding:20px;font-size:12px}}
details{{margin:18px 0}}summary{{cursor:pointer;color:#b7d4d1}}footer{{margin-top:40px;border-top:1px solid #293846;padding-top:20px;font-size:12px;color:#8b9dad}}
@media(max-width:700px){{.cards{{grid-template-columns:repeat(2,1fr)}}main{{padding:24px 16px}}h1{{font-size:28px}}}}
</style></head><body><main><span class="eyebrow">RESEARCH / SIMULATED EXECUTION</span><h1>Quant Terminal</h1>
<p>Agentic Market Research &amp; Risk Sandbox</p><p class="meta">{e(cfg["strategy"])} · {e(cfg["asset"])} · {e(data["evaluation_start"][:10])} → {e(data["evaluation_end"][:10])}<br>
Experiment {e(artifact["experiment_id"])} · numerical engine {e(artifact["engine"]["sha256"][:16])}</p>
<div class="verdict"><strong>{e(critic["verdict"])} · {e(critic["conclusion"])}</strong><p>{e(critic["interpretation"])}</p></div>
<div class="cards">{cards}</div><h2>Hypothesis</h2><p>{e(artifact["strategy"]["hypothesis"])}</p>
<h2>Dataset and methodology</h2><p>{e(data["rows"])} daily bars, {e(data["start"][:10])} to {e(data["end"][:10])}. {e(data["provenance"].get("source", "Provided dataset"))}.
{e(data["prior_context_bars"])} earlier context bars. Signals use close t; fills use open t+1. Daily target rebalancing, fractional BTC, no leverage.</p>
<p>Evaluation is a retrospective chronological split. No parameter winner is selected; this is not proof of untouched out-of-sample performance.</p>
<details><summary>Configuration, source and exact data identity</summary><pre>{e(json.dumps({"config": cfg, "dataset": data, "engine": artifact["engine"]}, indent=2))}</pre></details>
<h2>Performance</h2>{charts["equity"]}<h2>Drawdown</h2>{charts["drawdown"]}<h2>Exposure</h2>{charts["exposure"]}
<div class="scroll">{metrics_table}</div><h2>Independent risk</h2>
<p>Halted: {e(result["risk"]["halted"])}. Open holdings: {result["ending_position"]["units"]:.8f} BTC.
Unrealized PnL: {result["ending_position"]["unrealized_pnl"]:.2f} USDT. Remaining exit-cost estimate: {result["ending_position"]["estimated_exit_cost"]:.2f} USDT, outside marked return.</p>
<p>Close-sampled thresholds may overshoot through gaps. A halt blocks entries and schedules the next available opening exit. Final-close orders remain unfilled.</p>
<details><summary>Ending position, outstanding proposal and all risk events</summary><pre>{e(json.dumps({"ending_position": result["ending_position"], "pending_order": result["pending_order"], "risk": result["risk"]}, indent=2))}</pre></details>
<h2>Critic checks</h2><div class="scroll">{checks_table}</div><h2>Robustness</h2><p>{e(robustness["method"])}</p><div class="scroll">{scenarios}</div>
<details><summary>Trade ledger · {metrics["fill_count"]} fills</summary><div class="scroll">{fills_table}</div></details>
<h2>Assumptions and failure modes</h2><ul>{"".join("<li>" + e(s) + "</li>" for s in artifact["strategy"]["assumptions"] + artifact["strategy"]["failure_modes"])}</ul>
<p>No intrabar fills, live liquidity, order-book impact, funding, taxes or lot-size model. Single-asset concentration and retrospective selection remain unresolved.
Agent integration protocols exist; no LLM agent is connected.</p><h2>Conclusion</h2><strong>{e(critic["conclusion"])}</strong>
<footer><p>AI proposes. Evidence tests. Risk constrains. Critic challenges.</p><p>{e(DISCLAIMER)}</p><p>{e(dataset_terms(artifact))}</p></footer></main></body></html>"""


def trades_csv(artifact: dict[str, Any]) -> str:
    fields = [
        "timestamp",
        "signal_timestamp",
        "side",
        "quantity",
        "reference_price",
        "price",
        "fee",
        "slippage_cost",
        "realized_pnl",
        "requested_target",
        "allowed_target",
        "reason",
        "cash_after",
        "units_after",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(artifact["result"]["fills"])
    return output.getvalue()


def write_artifacts(artifact: dict[str, Any], output: Path) -> Path:
    folder = output / artifact["experiment_id"]
    folder.mkdir(parents=True, exist_ok=True)
    charts = {kind: chart_svg(artifact, kind) for kind in ("equity", "drawdown", "exposure")}
    files = {
        "experiment.json": json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        "report.md": markdown_report(artifact),
        "report.html": html_report(artifact, charts),
        "trades.csv": trades_csv(artifact),
        **{f"{kind}.svg": svg for kind, svg in charts.items()},
    }
    for name, content in files.items():
        destination = folder / name
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(destination)
    return folder
