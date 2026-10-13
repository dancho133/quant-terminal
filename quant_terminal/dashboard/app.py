"""Quant Terminal dashboard. All numerical results come from the shared experiment runner."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from quant_terminal.experiment import run_experiment
from quant_terminal.models import CostModel, ExperimentConfig, RiskConfig
from quant_terminal.reports import DISCLAIMER, METRIC_LIMITATIONS, write_artifacts

st.set_page_config(page_title="Quant Terminal", page_icon=":material/science:", layout="wide")
st.html("""<style>
.block-container {padding-top:2.0rem; padding-bottom:2rem; max-width:1550px}
h1 {letter-spacing:-.035em; font-weight:650}
[data-testid="stMetric"] {background:#151c25; padding:16px 18px; border:1px solid #283442; border-radius:6px}
[data-testid="stMetricLabel"] {font-size:.8rem; color:#9caec0}
[data-testid="stMetricValue"] {font-size:1.55rem}
[data-testid="stSidebar"] {border-right:1px solid #283442}
button[role="tab"] {font-family:monospace; letter-spacing:.03em}
</style>""")
output_root = Path(os.environ.get("QUANT_TERMINAL_OUTPUT", "artifacts"))


def display_frame(records: list[dict]) -> pd.DataFrame:
    """Render heterogeneous structured observations as JSON, not inferred Arrow structs."""
    return pd.DataFrame(
        [
            {
                key: json.dumps(value, sort_keys=True)
                if key in ("observed", "threshold", "limit")
                else value
                for key, value in row.items()
            }
            for row in records
        ]
    )


with st.sidebar:
    st.subheader("Experiment controls")
    st.caption("Edits are a draft until you run.")
    with st.form("experiment_controls"):
        strategy = st.selectbox("Strategy", ["momentum", "mean_reversion"], key="strategy")
        st.selectbox("Asset", ["BTCUSDT"], disabled=True)
        capital = st.number_input(
            "Initial capital · USDT",
            min_value=100.0,
            max_value=10_000_000.0,
            value=10000.0,
            step=1000.0,
            key="initial_capital",
        )
        evaluation = st.date_input(
            "Evaluation window",
            value=(date(2025, 1, 1), date(2025, 12, 31)),
            min_value=date(2023, 1, 1),
            max_value=date(2025, 12, 31),
        )
        max_position = st.slider("Position cap · %", 5, 100, 25, key="max_position")
        max_exposure = st.slider("Exposure cap · %", 5, 100, 50, key="max_exposure")
        max_drawdown = st.slider("Drawdown halt · %", 1, 50, 20, key="max_drawdown")
        with st.expander("Costs and baseline parameters"):
            fee = st.number_input(
                "Fee · bps per fill", min_value=0.0, max_value=100.0, value=10.0, step=1.0
            )
            slip = st.number_input(
                "Adverse slippage · bps", min_value=0.0, max_value=100.0, value=5.0, step=1.0
            )
            fast = st.number_input("Momentum fast MA", min_value=2, max_value=180, value=20)
            slow = st.number_input("Momentum slow MA", min_value=3, max_value=365, value=50)
            lookback = st.number_input(
                "Momentum / z-score lookback", min_value=2, max_value=180, value=20
            )
            entry_z = st.number_input(
                "Reversion entry z-score", min_value=-5.0, max_value=-0.05, value=-1.0, step=0.1
            )
            exit_z = st.number_input(
                "Reversion exit z-score", min_value=-0.5, max_value=3.0, value=0.0, step=0.1
            )
        submitted = st.form_submit_button(
            "Run experiment", type="primary", width="stretch", key="run_experiment"
        )
    st.divider()
    st.caption(
        "Bundled snapshot: 2023–2025\n\nPublic historical OHLCV. Runtime uses local data. No exchange account or LLM key."
    )


def complete_run(config: ExperimentConfig) -> None:
    with st.spinner("Simulating baseline, comparator and fixed robustness checks…"):
        artifact = run_experiment(config)
        folder = write_artifacts(artifact, output_root)
    st.session_state["experiment"] = artifact
    st.session_state["artifact_folder"] = str(folder)


if "experiment" not in st.session_state:
    try:
        complete_run(ExperimentConfig())
    except (ValueError, OSError, ArithmeticError) as exc:
        st.error(f"Cannot initialize experiment: {exc}")
        st.stop()
if submitted:
    try:
        if len(evaluation) != 2:
            raise ValueError("Choose both evaluation dates.")
        params = (
            {"fast": fast, "slow": slow, "lookback": lookback}
            if strategy == "momentum"
            else {"lookback": lookback, "entry_z": entry_z, "exit_z": exit_z}
        )
        complete_run(
            ExperimentConfig(
                strategy=strategy,
                initial_capital=capital,
                params=params,
                risk=RiskConfig(max_position / 100, max_exposure / 100, max_drawdown / 100),
                costs=CostModel(fee, slip),
                evaluation_start=evaluation[0].isoformat(),
                evaluation_end=evaluation[1].isoformat(),
            )
        )
    except (ValueError, OSError, ArithmeticError) as exc:
        st.error(f"Experiment failed: {exc}. Previous result is still displayed.")

artifact = st.session_state["experiment"]
cfg, data, result, critic = (
    artifact["config"],
    artifact["dataset"],
    artifact["result"],
    artifact["critic"],
)
metrics = result["metrics"]
folder = Path(st.session_state["artifact_folder"])
ledger = pd.DataFrame(result["ledger"])
ledger["Date"] = pd.to_datetime(ledger["timestamp"], utc=True)
comparison = pd.DataFrame(artifact["comparator"]["ledger"])
equity = pd.DataFrame(
    {
        "Date": ledger["Date"],
        "Strategy · net": ledger["equity"],
        "Same-risk constant-long": comparison["equity"],
        "Buy-and-hold · gross 100%": ledger["benchmark_equity"],
    }
)
drawdown = pd.DataFrame(
    {
        "Date": ledger["Date"],
        "Strategy drawdown · %": -100 * ledger["drawdown"],
        "Halt threshold": -100 * cfg["risk"]["max_drawdown"],
    }
)
exposure = pd.DataFrame(
    {
        "Date": ledger["Date"],
        "Exposure · %": 100 * ledger["exposure"],
        "Execution cap": 100 * min(cfg["risk"]["max_position"], cfg["risk"]["max_exposure"]),
    }
)

st.caption("HISTORICAL RESEARCH / SIMULATED EXECUTION")
st.title("Quant Terminal")
st.markdown("Agentic Market Research & Risk Sandbox")
st.caption(
    f"{cfg['strategy'].replace('_', ' ').upper()} · {cfg['asset']} · DAILY UTC · "
    f"{data['evaluation_start'][:10]} → {data['evaluation_end'][:10]} · RUN {artifact['experiment_id']}"
)
if critic["verdict"] == "REJECT":
    st.error(f"REJECT — {critic['conclusion']}", icon=":material/block:")
elif critic["verdict"] == "CAUTION":
    st.warning(f"CAUTION — {critic['conclusion']}", icon=":material/science:")
else:
    st.info(f"PASS — {critic['conclusion']}")
columns = st.columns(4)
columns[0].metric("Net return", f"{metrics['total_return']:+.2%}")
columns[1].metric("Same-risk comparator", f"{metrics['same_risk_benchmark_return']:+.2%}")
columns[2].metric("Max drawdown", f"{metrics['max_drawdown']:.2%}")
columns[3].metric("Closed position episodes", metrics["number_of_trades"])
overview, performance, trades, risk, research = st.tabs(
    ["Overview", "Performance", "Trades", "Risk", "Research"]
)

with overview:
    st.subheader("Evidence at a glance")
    st.caption(
        f"{data['rows']:,} validated bars → trailing features → baseline → {metrics['fill_count']} fills → independent risk → deterministic critic"
    )
    left, right = st.columns([2, 1], gap="large")
    with left:
        st.line_chart(
            equity,
            x="Date",
            y=["Strategy · net", "Same-risk constant-long", "Buy-and-hold · gross 100%"],
            color=["#5cbfb5", "#9aaac5", "#d0a56b"],
            height=300,
        )
        st.caption(
            "Marked equity in USDT. Gross buy-and-hold is context; the comparator uses identical risk and cost rules."
        )
    with right:
        st.markdown("**Why the critic challenged this run**")
        reasons = critic["reasons"]
        for reason in reasons[:4]:
            st.markdown(f"- {reason}")
        if not reasons:
            st.write("No declared screening threshold was triggered.")
        st.caption(
            f"Initial capital: {cfg['initial_capital']:,.2f} USDT · fees {cfg['costs']['fee_bps']:g} bps · slippage {cfg['costs']['slippage_bps']:g} bps"
        )
    st.caption("AI proposes. Evidence tests. Risk constrains. Critic challenges.")
    st.info(
        "Deterministic research pipeline. Agent interfaces are available for future integration; no LLM agents or live orders are connected."
    )

with performance:
    st.subheader("Performance and its limits")
    st.line_chart(equity, x="Date", height=340, color=["#5cbfb5", "#9aaac5", "#d0a56b"])
    st.line_chart(drawdown, x="Date", height=230, color=["#d17b7b", "#c9a56d"])
    more = st.columns(4)
    more[0].metric("Annualized volatility", f"{metrics['annualized_volatility']:.2%}")
    more[1].metric(
        "Sharpe-like · rf=0",
        "N/A" if metrics["sharpe_like"] is None else f"{metrics['sharpe_like']:.2f}",
    )
    more[2].metric(
        "Closed-episode win rate",
        "N/A" if metrics["win_rate"] is None else f"{metrics['win_rate']:.1%}",
    )
    more[3].metric("Gross turnover / initial capital", f"{metrics['turnover']:.2f}×")
    st.dataframe(
        pd.DataFrame(
            [{"Metric": name, "Limitation": text} for name, text in METRIC_LIMITATIONS.items()]
        ),
        hide_index=True,
        width="stretch",
    )

with trades:
    st.subheader("Simulated fill ledger")
    st.caption(
        "Every fill is authorized at the next open. Partial rebalance PnL uses average cost basis including entry fees."
    )
    stat = st.columns(3)
    stat[0].metric("Fills", metrics["fill_count"])
    stat[1].metric("Fees · USDT", f"{metrics['fees']:.2f}")
    stat[2].metric("Adverse slippage · USDT", f"{metrics['slippage_cost']:.2f}")
    if result["fills"]:
        st.dataframe(pd.DataFrame(result["fills"]), hide_index=True, width="stretch")
    else:
        st.info("No fills in this window.")
    st.markdown("**Fully closed position episodes**")
    st.dataframe(pd.DataFrame(result["round_trips"]), hide_index=True, width="stretch")
    st.markdown("**Ending holdings and outstanding proposal**")
    st.json(
        {"ending_position": result["ending_position"], "pending_order": result["pending_order"]},
        expanded=False,
    )
    st.caption(
        "Final holdings remain marked. No last-bar exit is invented; future liquidation costs are estimated separately."
    )
    st.download_button(
        "Download trades CSV",
        (folder / "trades.csv").read_bytes(),
        file_name=f"{artifact['experiment_id']}-trades.csv",
        mime="text/csv",
        on_click="ignore",
    )

with risk:
    st.subheader("Independent risk authority")
    cap = st.columns(4)
    cap[0].metric("Position cap", f"{cfg['risk']['max_position']:.0%}")
    cap[1].metric("Maximum exposure", f"{cfg['risk']['max_exposure']:.0%}")
    cap[2].metric("Drawdown halt", f"{cfg['risk']['max_drawdown']:.0%}")
    cap[3].metric("State", "HALTED" if result["risk"]["halted"] else "ACTIVE")
    st.line_chart(exposure, x="Date", height=280, color=["#78a8cc", "#c9a56d"])
    st.caption(
        "Caps authorize post-cost exposure at opens. Prices can push close exposure above a cap; adjustments occur at the next open. Drawdown limits are not guaranteed loss bounds."
    )
    events = display_frame(result["risk"]["events"])
    show_approvals = st.checkbox("Include order approvals", value=False)
    if not events.empty and not show_approvals:
        events = events[events["action"] != "APPROVE"]
    st.dataframe(events, hide_index=True, width="stretch")
    st.caption(
        "CAP preserves requested and allowed weights. REJECT blocks a prohibited proposal. A functioning rejection does not by itself reject the hypothesis."
    )

with research:
    st.subheader("Hypothesis and falsification")
    st.write(artifact["strategy"]["hypothesis"])
    first, second = st.columns(2)
    with first:
        st.markdown("**Assumptions**")
        for assumption in artifact["strategy"]["assumptions"]:
            st.markdown(f"- {assumption}")
    with second:
        st.markdown("**Failure modes**")
        for failure in artifact["strategy"]["failure_modes"]:
            st.markdown(f"- {failure}")
    st.markdown("**Deterministic reviewer**")
    st.dataframe(display_frame(critic["checks"]), hide_index=True, width="stretch")
    st.caption(critic["interpretation"])
    st.markdown("**Fixed robustness reruns**")
    st.caption(artifact["robustness"]["method"])
    scenarios = [
        {
            "Scenario": s["name"],
            "Return": s["total_return"],
            "Closed episodes": s["number_of_trades"],
        }
        for s in artifact["robustness"]["cost_scenarios"]
    ]
    scenarios += [
        {
            "Scenario": f"{s['changed_parameter']}={s['params'][s['changed_parameter']]}",
            "Return": s["total_return"],
            "Closed episodes": s["number_of_trades"],
        }
        for s in artifact["robustness"]["parameter_variants"]
    ]
    scenarios += [
        {
            "Scenario": f"{s['name']} · {s['start']} to {s['end']}",
            "Return": s["total_return"],
            "Closed episodes": s["number_of_trades"],
        }
        for s in artifact["robustness"]["time_windows"]
    ]
    st.dataframe(
        pd.DataFrame(scenarios),
        hide_index=True,
        width="stretch",
        column_config={"Return": st.column_config.NumberColumn(format="percent")},
    )
    st.warning(
        "Retrospective split, one market and known baseline parameters. No statistical significance, untouched holdout or live execution claim."
    )
    with st.expander("Source, configuration and reproducibility"):
        st.json({"config": cfg, "dataset": data, "engine": artifact["engine"]})
    export = st.columns(3)
    export[0].download_button(
        "Download experiment JSON",
        json.dumps(artifact, indent=2, allow_nan=False),
        file_name=f"{artifact['experiment_id']}.json",
        mime="application/json",
        on_click="ignore",
    )
    export[1].download_button(
        "Download self-contained HTML",
        (folder / "report.html").read_bytes(),
        file_name=f"{artifact['experiment_id']}.html",
        mime="text/html",
        on_click="ignore",
    )
    export[2].download_button(
        "Download Markdown report",
        (folder / "report.md").read_bytes(),
        file_name=f"{artifact['experiment_id']}.md",
        mime="text/markdown",
        on_click="ignore",
    )
st.divider()
st.caption(DISCLAIMER)
