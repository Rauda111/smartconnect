
"""Competition-ready Streamlit prototype for SmartConnect.

Uses the finalized SmartConnect project modules:
- scenarios.py
- baseline.py
- smartconnect.py

Important:
- The dashboard shows controlled simulation outputs, not physical 5G measurements.
- In Compare Both mode, one raw trace is generated and identical copies are passed
  to the RSSI baseline and SmartConnect.
- Single-run dashboard values are demo results, not the final repeated-seed analysis.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from baseline import apply_baseline
from scenarios import generate_scenario
from smartconnect import apply_smartconnect


SCENARIO_LABELS = {
    "leaving_wifi": "Leaving Wi-Fi Coverage",
    "congested_wifi": "Congested Wi-Fi",
    "large_download": "Large Download",
    "recovery": "Recovery / Return",
}

SCENARIO_DESCRIPTIONS = {
    "leaving_wifi": (
        "Wi-Fi gradually weakens as the user moves away, while the 5G-like path "
        "remains comparatively stable."
    ),
    "congested_wifi": (
        "Wi-Fi RSSI remains strong while latency, packet loss and jitter worsen. "
        "This exposes the weakness of RSSI-only handover."
    ),
    "large_download": (
        "Both paths remain usable, but the 5G-like path provides substantially "
        "higher throughput."
    ),
    "recovery": (
        "Wi-Fi quality worsens as the user moves away and later improves as the "
        "user returns."
    ),
}

APPLICATION_LABELS = {
    "video_call": "Video Call",
    "file_download": "File Download",
}

METHOD_LABELS = {
    "compare": "Compare Both",
    "smartconnect": "SmartConnect",
    "baseline": "RSSI Baseline",
}

METRIC_LABELS = {
    "rssi": "RSSI (dBm)",
    "latency": "Latency (ms)",
    "loss": "Packet Loss (%)",
    "jitter": "Jitter (ms)",
    "throughput": "Throughput (Mbps)",
}

ROOT = Path(__file__).resolve().parent


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.75rem;
        }
        [data-testid="stMetricLabel"] {
            font-weight: 600;
        }
        .smartconnect-hero {
            padding: 1.15rem 1.25rem;
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 16px;
            margin-bottom: 1rem;
        }
        .smartconnect-kicker {
            font-size: .82rem;
            opacity: .70;
            letter-spacing: .05em;
            text-transform: uppercase;
            margin-bottom: .25rem;
        }
        .smartconnect-title {
            font-size: 2.35rem;
            font-weight: 800;
            margin: 0;
            line-height: 1.1;
        }
        .smartconnect-subtitle {
            margin-top: .35rem;
            font-size: 1.08rem;
            opacity: .82;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def selected_metric_series(result: pd.DataFrame, metric: str) -> pd.Series:
    wifi_col = f"wifi_{metric}"
    g5_col = f"g5_{metric}"
    return result.apply(
        lambda row: row[wifi_col] if row["selected_network"] == "WiFi" else row[g5_col],
        axis=1,
    )


def single_run_summary(result: pd.DataFrame) -> dict:
    return {
        "Final network": str(result["selected_network"].iloc[-1]),
        "Handovers": int(result["handover"].sum()),
        "Avg latency (ms)": float(selected_metric_series(result, "latency").mean()),
        "Avg loss (%)": float(selected_metric_series(result, "loss").mean()),
        "Avg jitter (ms)": float(selected_metric_series(result, "jitter").mean()),
        "Avg throughput (Mbps)": float(selected_metric_series(result, "throughput").mean()),
        "Wi-Fi use (%)": float((result["selected_network"] == "WiFi").mean() * 100),
        "5G-like use (%)": float((result["selected_network"] == "5G").mean() * 100),
    }


def summary_metrics(result: pd.DataFrame) -> None:
    s = single_run_summary(result)

    row1 = st.columns(4)
    row1[0].metric("Final Network", s["Final network"])
    row1[1].metric("Handovers", f'{s["Handovers"]}')
    row1[2].metric("Avg Latency", f'{s["Avg latency (ms)"]:.1f} ms')
    row1[3].metric("Avg Throughput", f'{s["Avg throughput (Mbps)"]:.1f} Mbps')

    row2 = st.columns(4)
    row2[0].metric("Avg Packet Loss", f'{s["Avg loss (%)"]:.2f}%')
    row2[1].metric("Avg Jitter", f'{s["Avg jitter (ms)"]:.1f} ms')
    row2[2].metric("Wi-Fi Use", f'{s["Wi-Fi use (%)"]:.0f}%')
    row2[3].metric("5G-like Use", f'{s["5G-like use (%)"]:.0f}%')


def comparison_dataframe(baseline: pd.DataFrame, smart: pd.DataFrame) -> pd.DataFrame:
    b = single_run_summary(baseline)
    s = single_run_summary(smart)

    return pd.DataFrame(
        [
            ["Final network", b["Final network"], s["Final network"]],
            ["Handovers", b["Handovers"], s["Handovers"]],
            ["Avg latency (ms)", f'{b["Avg latency (ms)"]:.2f}', f'{s["Avg latency (ms)"]:.2f}'],
            ["Avg packet loss (%)", f'{b["Avg loss (%)"]:.2f}', f'{s["Avg loss (%)"]:.2f}'],
            ["Avg jitter (ms)", f'{b["Avg jitter (ms)"]:.2f}', f'{s["Avg jitter (ms)"]:.2f}'],
            ["Avg throughput (Mbps)", f'{b["Avg throughput (Mbps)"]:.2f}', f'{s["Avg throughput (Mbps)"]:.2f}'],
            ["Wi-Fi use (%)", f'{b["Wi-Fi use (%)"]:.1f}', f'{s["Wi-Fi use (%)"]:.1f}'],
            ["5G-like use (%)", f'{b["5G-like use (%)"]:.1f}', f'{s["5G-like use (%)"]:.1f}'],
        ],
        columns=["Metric", "RSSI Baseline", "SmartConnect"],
    )


def improvement_metrics(baseline: pd.DataFrame, smart: pd.DataFrame) -> None:
    b = single_run_summary(baseline)
    s = single_run_summary(smart)

    latency_change = b["Avg latency (ms)"] - s["Avg latency (ms)"]
    loss_change = b["Avg loss (%)"] - s["Avg loss (%)"]
    jitter_change = b["Avg jitter (ms)"] - s["Avg jitter (ms)"]
    throughput_change = s["Avg throughput (Mbps)"] - b["Avg throughput (Mbps)"]

    st.markdown("#### Single-run outcome difference")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latency difference", f"{latency_change:+.1f} ms", help="Positive means SmartConnect experienced lower average latency.")
    c2.metric("Loss difference", f"{loss_change:+.2f} pp", help="Positive means SmartConnect experienced lower average packet loss.")
    c3.metric("Jitter difference", f"{jitter_change:+.1f} ms", help="Positive means SmartConnect experienced lower average jitter.")
    c4.metric("Throughput difference", f"{throughput_change:+.1f} Mbps", help="Positive means SmartConnect experienced higher average throughput.")
    st.caption("These are single-run demo differences for the selected seed, not the final repeated-seed evaluation.")


def metric_chart(trace: pd.DataFrame, metric: str) -> None:
    frame = trace[["time", f"wifi_{metric}", f"g5_{metric}"]].copy()
    frame = frame.rename(
        columns={
            f"wifi_{metric}": "Wi-Fi",
            f"g5_{metric}": "5G-like",
        }
    )
    long = frame.melt("time", var_name="Network", value_name="Value")

    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:Q", title="Simulation step"),
            y=alt.Y("Value:Q", title=METRIC_LABELS[metric]),
            color=alt.Color("Network:N", title=None),
            tooltip=[
                alt.Tooltip("time:Q", title="Step"),
                alt.Tooltip("Network:N"),
                alt.Tooltip("Value:Q", title=METRIC_LABELS[metric], format=".2f"),
            ],
        )
        .properties(height=270)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def selection_timeline(baseline: pd.DataFrame | None, smart: pd.DataFrame | None) -> None:
    records = []

    if baseline is not None:
        for _, row in baseline.iterrows():
            records.append(
                {
                    "time": row["time"],
                    "Method": "RSSI Baseline",
                    "Selected Network": row["selected_network"],
                }
            )

    if smart is not None:
        for _, row in smart.iterrows():
            records.append(
                {
                    "time": row["time"],
                    "Method": "SmartConnect",
                    "Selected Network": row["selected_network"],
                }
            )

    frame = pd.DataFrame(records)

    chart = (
        alt.Chart(frame)
        .mark_line(point=False, strokeWidth=2.5, interpolate="step-after")
        .encode(
            x=alt.X("time:Q", title="Simulation step"),
            y=alt.Y(
                "Selected Network:N",
                title="Selected Network",
                sort=["WiFi", "5G"],
            ),
            color=alt.Color("Method:N", title=None),
            tooltip=[
                alt.Tooltip("time:Q", title="Step"),
                alt.Tooltip("Method:N"),
                alt.Tooltip("Selected Network:N"),
            ],
        )
        .properties(height=230)
    )
    st.altair_chart(chart, use_container_width=True)


def handover_table(result: pd.DataFrame, smartconnect: bool) -> pd.DataFrame:
    events = result[result["handover"]].copy()
    if events.empty:
        return events

    if "previous_network" not in events.columns:
        # Shift the full timeline before aligning to the event rows.
        events["previous_network"] = result["selected_network"].shift().loc[events.index]

    columns = ["time", "previous_network", "selected_network"]
    if smartconnect:
        for col in (
            "decision_strength",
            "candidate_advantage",
            "hold_count",
            "decision_explanation",
        ):
            if col in events.columns:
                columns.append(col)

    table = events[columns].copy()
    if "candidate_advantage" in table:
        table["candidate_advantage"] = table["candidate_advantage"].round(3)
    return table


def score_chart(result: pd.DataFrame) -> None:
    frame = result[
        ["time", "wifi_adjusted_score", "g5_adjusted_score"]
    ].rename(
        columns={
            "wifi_adjusted_score": "Wi-Fi",
            "g5_adjusted_score": "5G-like",
        }
    )
    long = frame.melt("time", var_name="Network", value_name="Adjusted Score")

    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:Q", title="Simulation step"),
            y=alt.Y("Adjusted Score:Q", title="Adjusted QoS Score", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("Network:N", title=None),
            tooltip=[
                alt.Tooltip("time:Q", title="Step"),
                alt.Tooltip("Network:N"),
                alt.Tooltip("Adjusted Score:Q", format=".3f"),
            ],
        )
        .properties(height=280)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def decision_inspector(result: pd.DataFrame) -> None:
    st.markdown("#### Step-by-step decision inspector")

    default_step = len(result) - 1
    event_indices = result.index[result["handover"]].tolist()
    if event_indices:
        default_step = int(event_indices[0])

    step = st.slider(
        "Inspect simulation step",
        0,
        len(result) - 1,
        value=default_step,
    )
    row = result.iloc[step]

    c1, c2, c3 = st.columns(3)
    c1.metric("Selected Network", str(row["selected_network"]))
    c2.metric("Wi-Fi Score", f'{float(row["wifi_adjusted_score"]):.3f}')
    c3.metric("5G-like Score", f'{float(row["g5_adjusted_score"]):.3f}')

    c4, c5, c6 = st.columns(3)
    c4.metric("Wi-Fi Trend", str(row["wifi_trend"]))
    c5.metric("5G-like Trend", str(row["g5_trend"]))
    c6.metric("Decision Strength", str(row["decision_strength"]))

    c7, c8 = st.columns(2)
    c7.metric("Wi-Fi Guardrail", "BREACH" if bool(row["wifi_guardrail"]) else "OK")
    c8.metric("5G-like Guardrail", "BREACH" if bool(row["g5_guardrail"]) else "OK")

    st.info(str(row["decision_explanation"]))

    if bool(row["handover"]):
        st.success(
            f'Handover at step {int(row["time"])}: '
            f'{row["previous_network"]} → {row["selected_network"]}'
        )


def final_results_section() -> None:
    st.subheader("Final Repeated-Seed Evaluation")
    st.write(
        "This section is for Aaesha's finalized baseline-vs-SmartConnect analysis "
        "across repeated seeds."
    )

    likely_paths = [
        ROOT / "results" / "final_summary.csv",
        ROOT / "outputs" / "final_summary.csv",
        ROOT / "final_summary.csv",
    ]
    existing = next((p for p in likely_paths if p.exists()), None)

    if existing is not None:
        st.success(f"Loaded finalized experiment summary: {existing.name}")
        final_results = pd.read_csv(existing)
        st.dataframe(final_results, use_container_width=True, hide_index=True)
        return

    st.warning(
        "Aaesha's repeated-seed summary has not been added yet. "
        "Do not use the single-run dashboard values as the final Slide 9 evidence."
    )

    uploaded = st.file_uploader(
        "Preview Aaesha's finalized summary CSV",
        type=["csv"],
    )
    if uploaded is not None:
        final_results = pd.read_csv(uploaded)
        st.dataframe(final_results, use_container_width=True, hide_index=True)


st.set_page_config(
    page_title="SmartConnect Prototype",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

st.markdown(
    """
    <div class="smartconnect-hero">
        <div class="smartconnect-kicker">Advanced Technology Pioneers 2026</div>
        <div class="smartconnect-title">📡 SmartConnect</div>
        <div class="smartconnect-subtitle">
            Application-Aware Smart Handover Between Wi-Fi and a 5G-like Network
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Controlled simulation prototype — values are simulation outputs, not measurements "
    "from a physical 5G network."
)

with st.sidebar:
    st.header("Simulation Controls")

    scenario = st.selectbox(
        "Scenario",
        list(SCENARIO_LABELS),
        format_func=lambda x: SCENARIO_LABELS[x],
        index=1,
    )

    application = st.selectbox(
        "Application",
        list(APPLICATION_LABELS),
        format_func=lambda x: APPLICATION_LABELS[x],
    )

    method = st.selectbox(
        "Method",
        list(METHOD_LABELS),
        format_func=lambda x: METHOD_LABELS[x],
    )

    seed = st.number_input(
        "Random Seed",
        min_value=0,
        value=42,
        step=1,
    )

    run_clicked = st.button(
        "Run Simulation",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    st.caption("Recommended demo: Congested Wi-Fi + Video Call + Compare Both.")

if "run_state_v2" not in st.session_state:
    st.session_state.run_state_v2 = None

if run_clicked:
    raw_trace = generate_scenario(scenario, seed=int(seed))

    baseline_result = None
    smart_result = None

    if method in ("baseline", "compare"):
        baseline_result = apply_baseline(raw_trace.copy(deep=True))

    if method in ("smartconnect", "compare"):
        smart_result = apply_smartconnect(
            raw_trace.copy(deep=True),
            application=application,
        )

    st.session_state.run_state_v2 = {
        "scenario": scenario,
        "application": application,
        "method": method,
        "seed": int(seed),
        "raw_trace": raw_trace,
        "baseline": baseline_result,
        "smart": smart_result,
    }

state = st.session_state.run_state_v2

if state is None:
    st.subheader("Ready to demonstrate SmartConnect")
    st.write(
        "Choose a scenario, application, and method in the sidebar, then press "
        "**Run Simulation**."
    )
    st.markdown(
        "**Best competition demo:** Congested Wi-Fi + Video Call + Compare Both. "
        "The RSSI baseline remains on strong Wi-Fi while SmartConnect can respond "
        "to deteriorating QoS."
    )
    st.stop()

scenario = state["scenario"]
application = state["application"]
method = state["method"]
seed = state["seed"]
raw_trace = state["raw_trace"]
baseline_result = state["baseline"]
smart_result = state["smart"]

st.caption(
    f'{SCENARIO_LABELS[scenario]} • {APPLICATION_LABELS[application]} • '
    f'{METHOD_LABELS[method]} • seed {seed}'
)
st.write(SCENARIO_DESCRIPTIONS[scenario])

overview_tab, metrics_tab, decision_tab, events_tab, results_tab = st.tabs(
    ["Overview", "Network Metrics", "Decision Details", "Handover Events", "Final Results"]
)

with overview_tab:
    if method == "baseline":
        st.subheader("RSSI Baseline — Single Run")
        summary_metrics(baseline_result)
        st.markdown("#### Selected-network timeline")
        selection_timeline(baseline_result, None)

    elif method == "smartconnect":
        st.subheader("SmartConnect — Single Run")
        summary_metrics(smart_result)
        st.markdown("#### Selected-network timeline")
        selection_timeline(None, smart_result)

    else:
        b = single_run_summary(baseline_result)
        s = single_run_summary(smart_result)

        st.markdown("### Baseline vs SmartConnect — Single Run")

        top = st.columns(6)
        top[0].metric("Baseline Final", b["Final network"])
        top[1].metric("SmartConnect Final", s["Final network"])
        top[2].metric("Baseline Handovers", b["Handovers"])
        top[3].metric("SmartConnect Handovers", s["Handovers"])
        top[4].metric("Baseline Wi-Fi Use", f'{b["Wi-Fi use (%)"]:.0f}%')
        top[5].metric("SmartConnect Wi-Fi Use", f'{s["Wi-Fi use (%)"]:.0f}%')

        improvement_metrics(baseline_result, smart_result)

        st.markdown("#### Selected-network timeline")
        selection_timeline(baseline_result, smart_result)

        st.markdown("#### Single-run comparison table")
        st.dataframe(
            comparison_dataframe(baseline_result, smart_result),
            use_container_width=True,
            hide_index=True,
        )

with metrics_tab:
    st.subheader("Underlying Network Conditions")
    st.caption(
        "Both methods receive the exact same raw network trace for this scenario and seed."
    )

    metric_chart(raw_trace, "rssi")
    metric_chart(raw_trace, "latency")
    metric_chart(raw_trace, "loss")
    metric_chart(raw_trace, "jitter")
    metric_chart(raw_trace, "throughput")

with decision_tab:
    if smart_result is None:
        st.warning(
            "Select SmartConnect or Compare Both to inspect the decision engine."
        )
    else:
        decision_inspector(smart_result)
        st.markdown("#### Adjusted QoS score evolution")
        score_chart(smart_result)

with events_tab:
    if baseline_result is not None:
        st.subheader("RSSI Baseline Handover Events")
        events = handover_table(baseline_result, smartconnect=False)
        if events.empty:
            st.write("No RSSI-baseline handovers occurred.")
        else:
            st.dataframe(events, use_container_width=True, hide_index=True)

    if smart_result is not None:
        st.subheader("SmartConnect Handover Events")
        events = handover_table(smart_result, smartconnect=True)
        if events.empty:
            st.write("No SmartConnect handovers occurred.")
        else:
            st.dataframe(events, use_container_width=True, hide_index=True)

with results_tab:
    final_results_section()
