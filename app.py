
"""Streamlit prototype for SmartConnect.

This dashboard uses the same finalized simulator, RSSI baseline, and SmartConnect
decision engine used by the command-line experiments.

Important:
- Values shown here are controlled simulation outputs, not measured 5G results.
- "Compare Both" generates one raw trace and gives identical copies to both methods.
"""

from __future__ import annotations

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
    "latency": "Latency (ms)",
    "loss": "Packet Loss (%)",
    "jitter": "Jitter (ms)",
    "throughput": "Throughput (Mbps)",
    "rssi": "RSSI (dBm)",
}


def selected_metric_series(result: pd.DataFrame, metric: str) -> pd.Series:
    """Return the metric experienced on the network selected at each step."""
    wifi_col = f"wifi_{metric}"
    g5_col = f"g5_{metric}"
    return result.apply(
        lambda row: row[wifi_col] if row["selected_network"] == "WiFi" else row[g5_col],
        axis=1,
    )


def single_run_summary(result: pd.DataFrame) -> dict:
    """Summarize one simulation run. These are not repeated-seed experiment results."""
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


def display_summary_cards(title: str, result: pd.DataFrame) -> None:
    summary = single_run_summary(result)
    st.subheader(title)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Network", summary["Final network"])
    c2.metric("Handovers", summary["Handovers"])
    c3.metric("Avg Latency", f'{summary["Avg latency (ms)"]:.1f} ms')
    c4.metric("Avg Throughput", f'{summary["Avg throughput (Mbps)"]:.1f} Mbps')

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Avg Packet Loss", f'{summary["Avg loss (%)"]:.2f}%')
    c6.metric("Avg Jitter", f'{summary["Avg jitter (ms)"]:.1f} ms')
    c7.metric("Wi-Fi Use", f'{summary["Wi-Fi use (%)"]:.0f}%')
    c8.metric("5G-like Use", f'{summary["5G-like use (%)"]:.0f}%')


def metric_chart(trace: pd.DataFrame, metric: str) -> None:
    chart = trace[["time", f"wifi_{metric}", f"g5_{metric}"]].copy()
    chart = chart.rename(
        columns={
            f"wifi_{metric}": "Wi-Fi",
            f"g5_{metric}": "5G-like",
        }
    ).set_index("time")

    st.markdown(f"**{METRIC_LABELS[metric]}**")
    st.line_chart(chart, use_container_width=True)


def selected_network_chart(result: pd.DataFrame, label: str) -> None:
    timeline = pd.DataFrame(
        {
            label: result["selected_network"].map({"WiFi": 0, "5G": 1}),
        },
        index=result["time"],
    )
    timeline.index.name = "time"
    st.line_chart(timeline, use_container_width=True)
    st.caption("Selected network timeline: 0 = Wi-Fi, 1 = 5G-like.")


def handover_table(result: pd.DataFrame, smartconnect: bool) -> pd.DataFrame:
    events = result[result["handover"]].copy()
    if events.empty:
        return events

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
    return events[columns]


def smartconnect_step_panel(result: pd.DataFrame) -> None:
    st.subheader("Decision Inspector")

    step = st.slider(
        "Inspect simulation step",
        min_value=0,
        max_value=len(result) - 1,
        value=len(result) - 1,
        step=1,
    )
    row = result.iloc[step]

    c1, c2, c3 = st.columns(3)
    c1.metric("Selected Network", str(row["selected_network"]))
    c2.metric("Wi-Fi Adjusted Score", f'{float(row["wifi_adjusted_score"]):.3f}')
    c3.metric("5G-like Adjusted Score", f'{float(row["g5_adjusted_score"]):.3f}')

    c4, c5, c6 = st.columns(3)
    c4.metric("Wi-Fi Trend", str(row["wifi_trend"]))
    c5.metric("5G-like Trend", str(row["g5_trend"]))
    c6.metric("Decision Strength", str(row["decision_strength"]))

    c7, c8 = st.columns(2)
    c7.metric(
        "Wi-Fi Guardrail",
        "BREACH" if bool(row["wifi_guardrail"]) else "OK",
    )
    c8.metric(
        "5G-like Guardrail",
        "BREACH" if bool(row["g5_guardrail"]) else "OK",
    )

    st.info(str(row["decision_explanation"]))

    if bool(row["handover"]):
        st.success(
            f'Handover at t={int(row["time"])}: '
            f'{row["previous_network"]} → {row["selected_network"]}'
        )


def comparison_table(baseline: pd.DataFrame, smart: pd.DataFrame) -> pd.DataFrame:
    b = single_run_summary(baseline)
    s = single_run_summary(smart)

    rows = []
    for metric in (
        "Final network",
        "Handovers",
        "Avg latency (ms)",
        "Avg loss (%)",
        "Avg jitter (ms)",
        "Avg throughput (Mbps)",
        "Wi-Fi use (%)",
        "5G-like use (%)",
    ):
        rows.append(
            {
                "Metric": metric,
                "RSSI Baseline": b[metric],
                "SmartConnect": s[metric],
            }
        )
    return pd.DataFrame(rows)


st.set_page_config(
    page_title="SmartConnect Prototype",
    page_icon="📡",
    layout="wide",
)

st.title("📡 SmartConnect")
st.subheader("Application-Aware Smart Handover Between Wi-Fi and a 5G-like Network")

st.info(
    "This prototype uses controlled simulated Wi-Fi and 5G-like conditions. "
    "The values are simulation outputs, not measurements from a physical 5G network."
)

with st.sidebar:
    st.header("Simulation Controls")

    scenario = st.selectbox(
        "Scenario",
        options=list(SCENARIO_LABELS),
        format_func=lambda x: SCENARIO_LABELS[x],
        index=1,
    )

    application = st.selectbox(
        "Application",
        options=list(APPLICATION_LABELS),
        format_func=lambda x: APPLICATION_LABELS[x],
    )

    method = st.selectbox(
        "Method",
        options=list(METHOD_LABELS),
        format_func=lambda x: METHOD_LABELS[x],
    )

    seed = st.number_input(
        "Random Seed",
        min_value=0,
        value=42,
        step=1,
    )

    run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "Recommended demo: Congested Wi-Fi + Video Call + Compare Both."
    )

if "run_state" not in st.session_state:
    st.session_state.run_state = None

if run_clicked:
    # IMPORTANT: generate the underlying network trace exactly once.
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

    st.session_state.run_state = {
        "scenario": scenario,
        "application": application,
        "method": method,
        "seed": int(seed),
        "raw_trace": raw_trace,
        "baseline": baseline_result,
        "smart": smart_result,
    }

state = st.session_state.run_state

if state is None:
    st.markdown(
        """
        ### Ready to demonstrate SmartConnect
        Choose a scenario, application, and method in the sidebar, then press
        **Run Simulation**.

        For the clearest competition demonstration, use **Congested Wi-Fi**,
        **Video Call**, and **Compare Both**. The RSSI-only baseline should remain
        on the strong Wi-Fi signal while SmartConnect can react to deteriorating QoS.
        """
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

overview_tab, metrics_tab, decision_tab, events_tab, results_tab = st.tabs(
    [
        "Overview",
        "Network Metrics",
        "Decision Details",
        "Handover Events",
        "Final Results",
    ]
)

with overview_tab:
    if method == "baseline":
        display_summary_cards("RSSI Baseline — Single Run", baseline_result)
        selected_network_chart(baseline_result, "RSSI Baseline")

    elif method == "smartconnect":
        display_summary_cards("SmartConnect — Single Run", smart_result)
        selected_network_chart(smart_result, "SmartConnect")

    else:
        left, right = st.columns(2)
        with left:
            display_summary_cards("RSSI Baseline — Single Run", baseline_result)
        with right:
            display_summary_cards("SmartConnect — Single Run", smart_result)

        st.subheader("Single-Run Comparison")
        st.dataframe(
            comparison_table(baseline_result, smart_result),
            use_container_width=True,
            hide_index=True,
        )

        comparison_timeline = pd.DataFrame(
            {
                "RSSI Baseline": baseline_result["selected_network"].map(
                    {"WiFi": 0, "5G": 1}
                ),
                "SmartConnect": smart_result["selected_network"].map(
                    {"WiFi": 0, "5G": 1}
                ),
            },
            index=raw_trace["time"],
        )
        comparison_timeline.index.name = "time"
        st.line_chart(comparison_timeline, use_container_width=True)
        st.caption("Selected network timeline: 0 = Wi-Fi, 1 = 5G-like.")

with metrics_tab:
    st.subheader("Underlying Network Conditions")
    st.caption(
        "Both methods receive the same raw trace for the selected scenario and seed."
    )

    metric_chart(raw_trace, "rssi")
    metric_chart(raw_trace, "latency")
    metric_chart(raw_trace, "loss")
    metric_chart(raw_trace, "jitter")
    metric_chart(raw_trace, "throughput")

with decision_tab:
    if smart_result is None:
        st.warning(
            "Decision details are available when SmartConnect or Compare Both is selected."
        )
    else:
        smartconnect_step_panel(smart_result)

        st.subheader("SmartConnect Score Evolution")
        score_data = smart_result[
            ["time", "wifi_adjusted_score", "g5_adjusted_score"]
        ].copy()
        score_data = score_data.rename(
            columns={
                "wifi_adjusted_score": "Wi-Fi Adjusted Score",
                "g5_adjusted_score": "5G-like Adjusted Score",
            }
        ).set_index("time")
        st.line_chart(score_data, use_container_width=True)

with events_tab:
    if baseline_result is not None:
        st.subheader("RSSI Baseline Handover Events")
        baseline_events = handover_table(baseline_result, smartconnect=False)
        if baseline_events.empty:
            st.write("No baseline handovers occurred.")
        else:
            st.dataframe(
                baseline_events,
                use_container_width=True,
                hide_index=True,
            )

    if smart_result is not None:
        st.subheader("SmartConnect Handover Events")
        smart_events = handover_table(smart_result, smartconnect=True)
        if smart_events.empty:
            st.write("No SmartConnect handovers occurred.")
        else:
            st.dataframe(
                smart_events,
                use_container_width=True,
                hide_index=True,
            )

with results_tab:
    st.subheader("Final Baseline vs SmartConnect Experiment Results")
    st.write(
        "This section is reserved for Aaesha's finalized repeated-seed analysis "
        "(means, standard deviations, comparison graphs, and tables)."
    )

    st.warning(
        "Do not replace this section with manually invented values. "
        "Only add results produced by the finalized experiment/analysis code."
    )

    uploaded_results = st.file_uploader(
        "Optional: preview Aaesha's finalized summary CSV",
        type=["csv"],
    )

    if uploaded_results is not None:
        final_results = pd.read_csv(uploaded_results)
        st.dataframe(final_results, use_container_width=True, hide_index=True)
        st.caption(
            "Preview of the uploaded finalized experiment summary. "
            "Confirm the file is generated from the approved repeated-seed analysis."
        )
