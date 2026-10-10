#!/usr/bin/env python3
"""Validate and analyze freshly generated SmartConnect CSVs without changing them.

Run only after the finalized repository passes all nine unit tests and all 120
CLI runs finish. This program never generates simulation data or executes either
selection algorithm. Every result is calculated from preserved native CSVs.

Example:
    python analyze_results.py --repo work/smartconnect \
        --raw-dir outputs/final_testing/raw_csv \
        --output-dir outputs/final_testing
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import io
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_COMMIT = "ac860776ba1d168cfa2e1dea8a496c9fa086d7d9"
SCENARIOS = ("leaving_wifi", "congested_wifi", "large_download", "recovery")
APPLICATIONS = ("video_call", "file_download")
SEEDS = tuple(range(10))
VARIANTS = ("baseline", "smartconnect_video_call", "smartconnect_file_download")
TRACE_METRICS = ("rssi", "latency", "loss", "jitter", "throughput")
TRACE_COLUMNS = ("time",) + tuple(
    f"{prefix}_{metric}" for prefix in ("wifi", "g5") for metric in TRACE_METRICS
)
SOURCE_FILES = ("simulate.py", "config.py", "baseline.py", "smartconnect.py", "scenarios.py")
CAPTION = "Controlled simulation results using realistic assumed Wi-Fi and 5G-like network conditions."
METRIC_UNITS = {
    "latency_ms": "ms", "loss_pct": "%", "jitter_ms": "ms",
    "throughput_mbps": "Mbps", "handovers": "count", "wifi_steps": "steps",
    "g5_steps": "steps", "wifi_pct": "%", "g5_pct": "%",
    "qoe_any_steps": "steps", "qoe_any_pct": "%",
    "qoe_latency_pct": "%", "qoe_loss_pct": "%",
    "qoe_jitter_pct": "%", "qoe_throughput_pct": "%",
}
METRIC_LABELS = {
    "latency_ms": "Selected-network latency", "loss_pct": "Selected-network packet loss",
    "jitter_ms": "Selected-network jitter", "throughput_mbps": "Selected-network throughput",
    "handovers": "Handovers", "wifi_steps": "Wi-Fi occupancy", "g5_steps": "5G-like occupancy",
    "wifi_pct": "Wi-Fi occupancy", "g5_pct": "5G-like occupancy",
    "qoe_any_steps": "Any application guardrail breach",
    "qoe_any_pct": "Any application guardrail breach",
    "qoe_latency_pct": "Latency guardrail breach",
    "qoe_loss_pct": "Packet-loss guardrail breach",
    "qoe_jitter_pct": "Jitter guardrail breach",
    "qoe_throughput_pct": "Throughput guardrail breach",
}
WIDE_COLUMNS = ["scenario", "seed", "application", "method", "raw_csv", "n_steps", *METRIC_UNITS]
EVENT_COLUMNS = [
    "scenario", "seed", "application", "method", "raw_csv", "event_number", "step",
    "source_network", "target_network", "gap_since_previous_handover", "decision_explanation",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_settings(repo: Path) -> dict:
    """Read declared constants/defaults as syntax, without importing source modules."""
    constants = {}
    trees = {}
    hashes = {}
    for filename in SOURCE_FILES:
        payload = (repo / filename).read_bytes()
        hashes[filename] = sha256_bytes(payload)
        tree = ast.parse(payload.decode("utf-8"), filename=filename)
        trees[filename] = tree
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("LIMITS", "SCENARIOS", "SIMULATION_DURATION"):
                        constants[target.id] = ast.literal_eval(node.value)
    function = next(
        node for node in trees["smartconnect.py"].body
        if isinstance(node, ast.FunctionDef) and node.name == "apply_smartconnect"
    )
    arguments = [node.arg for node in function.args.args]
    defaults = dict(zip(arguments[-len(function.args.defaults):], function.args.defaults))
    dwell_steps = ast.literal_eval(defaults["dwell_steps"])
    hold_steps = ast.literal_eval(defaults["hold_steps"])
    expected_limits = {
        "video_call": {"latency": 60, "loss": 2, "jitter": 20},
        "file_download": {"loss": 3, "throughput": 20},
    }
    require(constants["LIMITS"] == expected_limits, "Source guardrails differ from finalized analysis contract")
    require(tuple(constants["SCENARIOS"]) == SCENARIOS, "Source scenario list differs from analysis contract")
    require(constants["SIMULATION_DURATION"] == 100, "Expected 100 simulation steps")
    require(dwell_steps == 8 and hold_steps == 3, "Expected finalized dwell/hold defaults")
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    require(commit == EXPECTED_COMMIT, f"Expected finalized commit {EXPECTED_COMMIT}; got {commit}")
    subprocess.run(["git", "-C", str(repo), "diff", "--exit-code", "HEAD", "--", *SOURCE_FILES], check=True, capture_output=True)
    return {
        "commit": commit, "file_sha256": hashes, "limits": constants["LIMITS"],
        "duration_steps": constants["SIMULATION_DURATION"], "dwell_steps": dwell_steps,
        "hold_steps": hold_steps,
    }


def bool_values(series: pd.Series, description: str) -> np.ndarray:
    if pd.api.types.is_bool_dtype(series):
        require(not series.isna().any(), f"Missing boolean: {description}")
        return series.to_numpy(dtype=bool)
    mapping = {"True": True, "False": False}
    require(series.astype(str).isin(mapping).all(), f"Invalid boolean: {description}")
    return series.astype(str).map(mapping).to_numpy(dtype=bool)


def breach_masks(trace: pd.DataFrame, application: str, limits: dict, prefix: str | None = None) -> dict:
    masks = {}
    for metric, limit in limits[application].items():
        if prefix is None:
            selected_wifi = trace["selected_network"].to_numpy() == "WiFi"
            values = np.where(selected_wifi, trace[f"wifi_{metric}"], trace[f"g5_{metric}"])
        else:
            values = trace[f"{prefix}_{metric}"].to_numpy(dtype=float)
        masks[metric] = values < limit if metric == "throughput" else values > limit
    return masks


def read_run(path: Path, scenario: str, seed: int, variant: str, settings: dict) -> dict:
    payload = path.read_bytes()
    trace = pd.read_csv(io.BytesIO(payload), float_precision="round_trip")
    required = [*TRACE_COLUMNS, "selected_network", "handover"]
    require(all(column in trace for column in required), f"Missing columns in {path.name}")
    require(len(trace) == 100, f"Expected 100 rows in {path.name}, got {len(trace)}")
    require(np.array_equal(trace["time"].to_numpy(), np.arange(100)), f"Time must be 0..99 in {path.name}")
    require(not trace[required].isna().any().any(), f"Missing trace/decision values in {path.name}")
    for column in TRACE_COLUMNS:
        require(pd.api.types.is_numeric_dtype(trace[column]), f"Non-numeric {column} in {path.name}")
    numeric = trace.select_dtypes(include=["number"]).to_numpy(dtype=float)
    require(np.isfinite(numeric).all(), f"Non-finite numeric values in {path.name}")
    require(trace["selected_network"].isin(("WiFi", "5G")).all(), f"Unknown selected network in {path.name}")
    selected = trace["selected_network"].to_numpy()
    expected_handovers = np.r_[False, selected[1:] != selected[:-1]]
    handovers = bool_values(trace["handover"], f"{path.name}:handover")
    require(np.array_equal(handovers, expected_handovers), f"Handover flags differ from transitions in {path.name}")
    application = "" if variant == "baseline" else variant.removeprefix("smartconnect_")
    method = "baseline" if variant == "baseline" else "smartconnect"
    if method == "smartconnect":
        for prefix in ("wifi", "g5"):
            column = f"{prefix}_guardrail"
            require(column in trace, f"Missing {column} in {path.name}")
            expected = np.logical_or.reduce(list(breach_masks(trace, application, settings["limits"], prefix).values()))
            require(np.array_equal(bool_values(trace[column], f"{path.name}:{column}"), expected),
                    f"Source guardrail flags fail evaluation in {path.name}")
        require("previous_network" in trace, f"Missing previous_network in {path.name}")
        expected_previous = np.concatenate([np.array(["WiFi"]), selected[:-1]])
        require(np.array_equal(trace["previous_network"].to_numpy(), expected_previous),
                f"Previous-network records disagree with selections in {path.name}")
    elif method == "baseline":
        expected_baseline = np.where(trace["wifi_rssi"] >= trace["g5_rssi"], "WiFi", "5G")
        require(np.array_equal(selected, expected_baseline), f"Baseline output differs from RSSI selection in {path.name}")
    canonical_trace = trace[list(TRACE_COLUMNS)].to_numpy(dtype="<f8")
    return {
        "trace": trace, "scenario": scenario, "seed": seed, "variant": variant,
        "application": application, "method": method, "raw_csv": path.name,
        "sha256": sha256_bytes(payload), "trace_sha256": sha256_bytes(canonical_trace.tobytes(order="C")),
        "trace_values": canonical_trace, "handover_flags": handovers,
    }


def run_metrics(run: dict, application: str | None, limits: dict) -> dict:
    trace = run["trace"]
    wifi = trace["selected_network"].to_numpy() == "WiFi"
    n_steps = len(trace)
    row = {
        "scenario": run["scenario"], "seed": run["seed"],
        "application": application or "", "method": run["method"], "raw_csv": run["raw_csv"],
        "n_steps": n_steps,
    }
    for source_metric, result_metric in (
        ("latency", "latency_ms"), ("loss", "loss_pct"),
        ("jitter", "jitter_ms"), ("throughput", "throughput_mbps"),
    ):
        values = np.where(wifi, trace[f"wifi_{source_metric}"], trace[f"g5_{source_metric}"])
        row[result_metric] = float(np.mean(values))
    row.update({
        "handovers": int(np.sum(run["handover_flags"])),
        "wifi_steps": int(np.sum(wifi)), "g5_steps": int(np.sum(~wifi)),
        "wifi_pct": float(100 * np.mean(wifi)), "g5_pct": float(100 * np.mean(~wifi)),
        "qoe_any_steps": None, "qoe_any_pct": None,
        "qoe_latency_pct": None, "qoe_loss_pct": None, "qoe_jitter_pct": None,
        "qoe_throughput_pct": None,
    })
    if application is not None:
        masks = breach_masks(trace, application, limits)
        any_bad = np.logical_or.reduce(list(masks.values()))
        row["qoe_any_steps"] = int(np.sum(any_bad))
        row["qoe_any_pct"] = float(100 * np.mean(any_bad))
        for metric, mask in masks.items():
            row[f"qoe_{metric}_pct"] = float(100 * np.mean(mask))
    return row


def switching_metrics(run: dict, dwell_steps: int) -> tuple[list, dict]:
    trace = run["trace"]
    selected = trace["selected_network"].to_numpy()
    indices = np.flatnonzero(run["handover_flags"])
    identity = {key: run[key] for key in ("scenario", "seed", "application", "method", "raw_csv")}
    events = []
    for event_number, index in enumerate(indices, start=1):
        events.append({
            **identity, "event_number": event_number, "step": int(trace.iloc[index]["time"]),
            "source_network": selected[index - 1], "target_network": selected[index],
            "gap_since_previous_handover": int(index - indices[event_number - 2]) if event_number > 1 else None,
            "decision_explanation": trace.iloc[index].get("decision_explanation", "Strongest Signal First RSSI selection"),
        })
    gaps = np.diff(indices)
    reversals = sum(
        int(b["step"] - a["step"] < dwell_steps and
            a["source_network"] == b["target_network"] and a["target_network"] == b["source_network"])
        for a, b in zip(events, events[1:])
    )
    g5_indices = np.flatnonzero(selected == "5G")
    returns = [event["step"] for event in events if event["target_network"] == "WiFi"]
    row = {
        **identity, "initial_network": selected[0], "final_network": selected[-1],
        "handovers": len(events), "first5g_step": int(g5_indices[0]) if len(g5_indices) else None,
        "lastreturn_to_wifi": returns[-1] if returns else None,
        "minimum_gap": int(np.min(gaps)) if len(gaps) else None,
        "reversal_pairs_under8": reversals,
    }
    return events, row


def aggregate(application_rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.DataFrame(application_rows, columns=WIDE_COLUMNS)
    summaries = []
    comparisons = []
    for scenario in SCENARIOS:
        for application in APPLICATIONS:
            app_frame = frame[(frame.scenario == scenario) & (frame.application == application)]
            for metric, unit in METRIC_UNITS.items():
                if app_frame[metric].isna().all():
                    continue
                paired = {}
                for method in ("baseline", "smartconnect"):
                    subset = app_frame[app_frame.method == method].sort_values("seed")
                    require(tuple(subset.seed) == SEEDS, f"Missing/duplicate paired seeds: {scenario}/{application}/{method}")
                    values = subset[metric].to_numpy(dtype=float)
                    require(np.isfinite(values).all(), f"Incomplete evaluated metric: {scenario}/{application}/{metric}")
                    paired[method] = values
                    summaries.append({
                        "scenario": scenario, "application": application, "method": method,
                        "metric": metric, "unit": unit, "n": len(values),
                        "mean": float(np.mean(values)), "std": float(np.std(values, ddof=1)),
                    })
                delta = paired["smartconnect"] - paired["baseline"]
                comparisons.append({
                    "scenario": scenario, "application": application, "metric": metric, "unit": unit, "n": len(delta),
                    "baseline_mean": float(np.mean(paired["baseline"])),
                    "baseline_std": float(np.std(paired["baseline"], ddof=1)),
                    "smartconnect_mean": float(np.mean(paired["smartconnect"])),
                    "smartconnect_std": float(np.std(paired["smartconnect"], ddof=1)),
                    "mean_delta": float(np.mean(delta)), "std_delta": float(np.std(delta, ddof=1)),
                })
    return pd.DataFrame(summaries), pd.DataFrame(comparisons)


def summary_html(summaries: pd.DataFrame, settings: dict) -> str:
    lookup = {
        (row.scenario, row.application, row.method, row.metric): row
        for row in summaries.itertuples(index=False)
    }
    def cell(scenario: str, application: str, method: str, metric: str) -> str:
        row = lookup.get((scenario, application, method, metric))
        if row is None:
            return '<td class="na">Not defined for this profile</td>'
        return f'<td>{row.mean:.2f} <span class="sd">± {row.std:.2f}</span></td>'

    sections = []
    for scenario in SCENARIOS:
        rows = []
        for metric, unit in METRIC_UNITS.items():
            label = html.escape(f"{METRIC_LABELS[metric]} ({unit})")
            cells = "".join(cell(scenario, application, method, metric)
                            for application in APPLICATIONS for method in ("baseline", "smartconnect"))
            rows.append(f'<tr><th scope="row">{label}</th>{cells}</tr>')
        sections.append(f'''<section class="scenario"><h2>{html.escape(scenario.replace("_", " ").title())}</h2>
<table><thead><tr><th rowspan="2">Metric and unit</th><th colspan="2">Video call</th><th colspan="2">File download</th></tr>
<tr><th>RSSI-only Baseline</th><th>SmartConnect</th><th>RSSI-only Baseline</th><th>SmartConnect</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></section>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Final SmartConnect comparison tables</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f6f8fb;color:#17243b;font-family:Arial,sans-serif;font-size:15px}}
main{{max-width:1240px;margin:36px auto;padding:0 28px}}h1{{font-size:26px;margin:0 0 12px}}h2{{font-size:21px;margin:0 0 16px}}
p{{line-height:1.5;margin:8px 0}}.caption{{font-weight:bold}}.methodology{{color:#42536a;font-size:14px}}
.scenario{{background:white;padding:24px;margin:24px 0;border:1px solid #dbe2ec;border-radius:8px;break-inside:avoid}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13px}}thead th{{background:#203954;color:white;padding:10px 8px;text-align:center}}
thead th:first-child{{width:31%}}tbody th{{text-align:left;font-weight:normal}}tbody td{{text-align:right;font-variant-numeric:tabular-nums}}
tbody th,tbody td{{padding:9px 8px;border-bottom:1px solid #e2e7ef}}tbody tr:nth-child(even){{background:#f6f8fb}}
.sd{{color:#617087}}.na{{font-size:11px;color:#718098;text-align:center}}footer{{font-size:13px;color:#42536a;margin:18px 0}}
@media print{{@page{{size:A4 landscape;margin:12mm}}body{{background:white}}main{{margin:0;padding:0;max-width:none}}
.scenario{{border:0;border-radius:0;margin:15px 0;padding:0;break-inside:avoid}}.scenario~.scenario{{break-before:page}}
table{{font-size:12px}}tbody th,tbody td{{padding:7px 6px}}thead th{{padding:8px 6px}}}}
</style></head><body><main><h1>RSSI-only Baseline vs SmartConnect</h1>
<p class="caption">{CAPTION}</p>
<p class="methodology">Every value is mean ± sample standard deviation across seeds 0–9 (n = 10 per comparison).
All three configurations use identical traces within each scenario and seed. Each run contains 100 equal simulation steps.
Baseline runs are reused for the two application evaluations. Time is reported in steps; these simulations do not assign seconds.</p>
{"".join(sections)}
<footer>Prototype application guardrails from the finalized source: video call, latency &gt; 60 ms, packet loss &gt; 2%, or jitter &gt; 20 ms;
file download, packet loss &gt; 3% or throughput &lt; 20 Mbps. A value exactly at its limit passes.
“Any” counts the union of breaches, once per step. Undefined per-profile guardrails are marked explicitly.
Handovers exclude initial attachment. Guardrails are assumed prototype thresholds, not validated service guarantees.
Source commit: {html.escape(settings["commit"])}.</footer></main></body></html>'''


def analyze(repo: Path, raw_dir: Path, output_dir: Path) -> dict:
    settings = source_settings(repo)
    expected_names = {
        f"{scenario}_seed{seed}_{variant}.csv"
        for scenario in SCENARIOS for seed in SEEDS for variant in VARIANTS
    }
    actual_names = {path.name for path in raw_dir.glob("*.csv")}
    require(actual_names == expected_names,
            f"Require exactly 120 raw CSVs; missing={sorted(expected_names-actual_names)}, extra={sorted(actual_names-expected_names)}")
    runs = {}
    trace_reports = []
    for scenario in SCENARIOS:
        for seed in SEEDS:
            group = {}
            for variant in VARIANTS:
                path = raw_dir / f"{scenario}_seed{seed}_{variant}.csv"
                run = read_run(path, scenario, seed, variant, settings)
                runs[(scenario, seed, variant)] = group[variant] = run
            baseline = group["baseline"]["trace_values"]
            require(all(np.array_equal(baseline, run["trace_values"]) for run in group.values()),
                    f"Exogenous trace mismatch for {scenario}, seed {seed}")
            trace_reports.append({
                "scenario": scenario, "seed": seed, "rows": 100, "trace_columns_count": len(TRACE_COLUMNS),
                **{f"{variant}_trace_sha256": run["trace_sha256"] for variant, run in group.items()},
                "exact_match": True,
            })
    per_run = []
    per_application = []
    all_events = []
    switching = []
    raw_hashes = []
    for run in runs.values():
        per_run.append(run_metrics(run, run["application"] or None, settings["limits"]))
        evaluated_apps = APPLICATIONS if run["method"] == "baseline" else (run["application"],)
        for application in evaluated_apps:
            per_application.append(run_metrics(run, application, settings["limits"]))
        events, behavior = switching_metrics(run, settings["dwell_steps"])
        all_events.extend(events)
        switching.append(behavior)
        raw_hashes.append({"file": run["raw_csv"], "sha256": run["sha256"], "rows": len(run["trace"])})
    require(len(per_run) == 120 and len(per_application) == 160, "Unexpected metric row counts")
    summaries, comparisons = aggregate(per_application)
    require(len(trace_reports) == 40 and len(summaries) == 216 and len(comparisons) == 108,
            "Unexpected paired trace or summary count")
    # All validation and calculations succeed before any derived result is written.
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(per_run, columns=WIDE_COLUMNS).to_csv(tables_dir / "per_run_metrics.csv", index=False)
    pd.DataFrame(per_application, columns=WIDE_COLUMNS).to_csv(tables_dir / "per_application_metrics.csv", index=False)
    summaries.to_csv(tables_dir / "mean_sd.csv", index=False)
    comparisons.to_csv(tables_dir / "paired_differences.csv", index=False)
    pd.DataFrame(all_events, columns=EVENT_COLUMNS).to_csv(tables_dir / "events.csv", index=False)
    pd.DataFrame(switching).to_csv(tables_dir / "switching_behavior.csv", index=False)
    pd.DataFrame(trace_reports).to_csv(tables_dir / "trace_match_report.csv", index=False)
    (output_dir / "summary_tables.html").write_text(summary_html(summaries, settings), encoding="utf-8")
    manifest = {
        "complete": True, "caption": CAPTION, "source": settings,
        "analysis_code_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "dependencies": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "design": {"scenarios": list(SCENARIOS), "seeds": list(SEEDS), "applications": list(APPLICATIONS),
                   "raw_runs": len(runs), "paired_scenario_seed_groups": len(trace_reports), "steps_per_run": 100},
        "aggregation": {"method": "arithmetic mean of each run's selected-network samples; arithmetic mean across ten seeds",
                        "standard_deviation": "sample standard deviation across ten per-run metrics, ddof=1",
                        "paired_difference": "SmartConnect minus Baseline for each matching scenario/application/seed",
                        "baseline_reuse": "Each baseline CSV is evaluated for both profiles; it remains ten runs per scenario"},
        "guardrails": {
            "source": "smartconnect.py LIMITS and guardrail_breaches",
            "profiles": {application: {
                metric: {"threshold": limit, "operator": "<" if metric == "throughput" else ">",
                         "unit": {"latency": "ms", "loss": "%", "jitter": "ms", "throughput": "Mbps"}[metric]}
                for metric, limit in profile.items()
            } for application, profile in settings["limits"].items()},
            "any_breach": "Union of selected-network profile breaches, counted once per step",
            "threshold_equality": "passes", "status": "assumed prototype guardrails, not validated service guarantees",
            "unevaluated_fields": "Blank for undefined per-profile guardrails; baseline raw-run row has no app-specific QoE evaluation",
        },
        "switching_definitions": {
            "handovers": "Changes between consecutive selected networks; initial attachment excluded",
            "first5g_step": "First step selected on 5G-like, including initial attachment if applicable; blank if never selected",
            "lastreturn_to_wifi": "Last handover from 5G-like to Wi-Fi; blank if no return",
            "minimum_gap": "Smallest step difference between adjacent handovers; blank when fewer than two",
            "reversal_pairs_under8": "Adjacent opposite-direction handover pairs separated by strictly fewer than source default dwell_steps=8",
            "interpretation": "Reversal count is descriptive and does not establish that a switch was unnecessary",
        },
        "occupancy": "Equal simulation-step counts and percentages; no seconds or physical elapsed duration are defined",
        "verification": {"expected_raw_files": 120, "verified_raw_files": 120, "rows_each": 100,
                         "time_values": "0..99", "numeric_values_finite": True, "handover_flags_match_transitions": True,
                         "source_guardrail_flags_match": True, "baseline_rssi_choices_match": True,
                         "paired_traces_exactly_equal": True, "paired_groups": 40,
                         "trace_columns": list(TRACE_COLUMNS), "csv_float_reader": "pandas float_precision=round_trip",
                         "trace_hash_encoding": "11 columns in declared order, 100 rows, little-endian float64, C order",
                         "source_commit_verified": True, "source_files_unmodified_against_commit": True},
        "outputs": {"per_run_metrics_rows": 120, "per_application_metrics_rows": 160,
                    "mean_sd_rows": len(summaries), "paired_differences_rows": len(comparisons),
                    "events_rows": len(all_events), "switching_behavior_rows": len(switching),
                    "trace_match_report_rows": len(trace_reports)},
        "raw_csv_sha256": raw_hashes,
    }
    # Recheck preserved bytes before declaring the analysis complete.
    for record in raw_hashes:
        require(sha256_bytes((raw_dir / record["file"]).read_bytes()) == record["sha256"],
                f"Raw CSV changed during analysis: {record['file']}")
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Finalized unmodified Git repository")
    parser.add_argument("--raw-dir", type=Path, required=True, help="Directory of exactly 120 fresh native result CSVs")
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination for tables, HTML and analysis manifest")
    args = parser.parse_args()
    manifest = analyze(args.repo.resolve(), args.raw_dir.resolve(), args.output_dir.resolve())
    print(json.dumps({"complete": manifest["complete"], "verified_runs": 120,
                      "matched_trace_groups": 40, "outputs": manifest["outputs"]}, indent=2))


if __name__ == "__main__":
    main()
