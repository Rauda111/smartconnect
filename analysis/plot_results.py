#!/usr/bin/env python3
"""Plot only the final, repeated-seed SmartConnect experiment summary.

Input is the analysis script's tidy mean_sd.csv, containing scenario,
application, method, metric, unit, n, mean and std. The std column must be
the sample standard deviation across the ten run-level observations. This
script does not generate traces, change simulation logic, or compute new
result values. Every chart directly compares the two methods on the same
scenario/application and on seeds 0 through 9.

Example:
    python plot_results.py --results-dir /absolute/path/final_testing
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "smartconnect-final-mpl"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


SCENARIOS = ("leaving_wifi", "congested_wifi", "large_download", "recovery")
APPLICATIONS = ("video_call", "file_download")
METHODS = ("baseline", "smartconnect")
SCENARIO_NAMES = {
    "leaving_wifi": "Leaving Wi-Fi",
    "congested_wifi": "Congested Wi-Fi",
    "large_download": "Large Download",
    "recovery": "Recovery",
}
APPLICATION_NAMES = {"video_call": "Video Call", "file_download": "File Download"}
METHOD_NAMES = {"baseline": "RSSI-only Baseline", "smartconnect": "SmartConnect"}
COLORS = {"baseline": "#3C638A", "smartconnect": "#008579"}
CAPTION = (
    "Controlled simulation results using realistic assumed Wi-Fi and 5G-like network conditions."
)
REPEATS_NOTE = "Seeds 0–9 · n = 10 runs per method · mean ± 1 sample standard deviation"
METRICS = {
    "handovers": {
        "title": "Handover Count",
        "axis": "Handovers per run",
        "short": "Handover count",
        "digits": 2,
        "note": "Handover counts summarize network switches over the complete simulated trace.",
    },
    "latency_ms": {
        "title": "Selected-Network Latency",
        "axis": "Mean latency (ms)",
        "short": "Latency (ms)",
        "digits": 2,
        "note": "Each run contributes its average selected-network latency across all simulated steps.",
    },
    "loss_pct": {
        "title": "Selected-Network Packet Loss",
        "axis": "Mean packet loss (%)",
        "short": "Packet loss (%)",
        "digits": 3,
        "note": "Each run contributes its average selected-network packet loss across all simulated steps.",
    },
    "jitter_ms": {
        "title": "Selected-Network Jitter",
        "axis": "Mean jitter (ms)",
        "short": "Jitter (ms)",
        "digits": 2,
        "note": "Each run contributes its average selected-network jitter across all simulated steps.",
    },
    "throughput_mbps": {
        "title": "Selected-Network Available Path Capacity",
        "axis": "Mean available path capacity (Mbps)",
        "short": "Available path capacity (Mbps)",
        "digits": 2,
        "note": "Throughput represents assumed available path capacity, not achieved application goodput.",
    },
    "qoe_any_pct": {
        "title": "QoE Guardrail Violations",
        "axis": "Steps with any violation (%)",
        "short": "Any QoE violation (% steps)",
        "digits": 2,
        "note": "A step counts once if its selected network violates any guardrail for the stated application.",
    },
    "wifi_pct": {
        "title": "Wi-Fi Selection Share",
        "axis": "Simulated steps on Wi-Fi (%)",
        "short": "Wi-Fi share (% steps)",
        "digits": 2,
        "note": "Occupancy is the share of abstract simulated steps, not elapsed seconds; 5G-like share = 100% − Wi-Fi share.",
    },
}
DASHBOARD_METRICS = (
    "handovers", "latency_ms", "loss_pct", "jitter_ms", "throughput_mbps", "qoe_any_pct"
)


def configure_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 12,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#9DAFB9",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "text.color": "#1D3444",
        "axes.labelcolor": "#1D3444",
        "xtick.color": "#1D3444",
        "ytick.color": "#1D3444",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
    })


def load_summary(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    required = {"scenario", "application", "method", "metric", "unit", "n", "mean", "std"}
    if missing := required.difference(data.columns):
        raise ValueError(f"Summary is missing columns: {sorted(missing)}")
    keys = ["scenario", "application", "method", "metric"]
    if data.duplicated(keys).any():
        raise ValueError("Summary has duplicate scenario/application/method/metric rows.")
    for column in ("n", "mean", "std"):
        data[column] = pd.to_numeric(data[column], errors="raise")
    chosen = data.loc[
        data["scenario"].isin(SCENARIOS)
        & data["application"].isin(APPLICATIONS)
        & data["method"].isin(METHODS)
        & data["metric"].isin(METRICS)
    ].copy()
    if not np.isfinite(chosen[["n", "mean", "std"]].to_numpy(dtype=float)).all():
        raise ValueError("Required summary rows contain nonfinite values.")
    if not chosen["n"].eq(10).all():
        raise ValueError("Each required summary group must contain exactly ten seed-level observations.")
    if chosen["std"].lt(0).any():
        raise ValueError("Sample standard deviations must be nonnegative.")
    expected = {
        (scenario, application, method, metric)
        for scenario in SCENARIOS
        for application in APPLICATIONS
        for method in METHODS
        for metric in METRICS
    }
    actual = set(chosen[keys].itertuples(index=False, name=None))
    if missing_rows := expected.difference(actual):
        raise ValueError(f"Missing required final summary groups: {sorted(missing_rows)}")
    if chosen["mean"].lt(0).any():
        raise ValueError("These plotted physical metrics and counts require nonnegative means.")
    for metric in ("wifi_pct", "qoe_any_pct"):
        if chosen.loc[chosen["metric"].eq(metric), "mean"].gt(100).any():
            raise ValueError(f"{metric} is a percentage of simulated steps and must not exceed 100.")
    return chosen.set_index(keys).sort_index()


def observation(summary: pd.DataFrame, scenario: str, application: str,
                method: str, metric: str) -> tuple[float, float]:
    row = summary.loc[(scenario, application, method, metric)]
    return float(row["mean"]), float(row["std"])


def format_value(value: float, digits: int) -> str:
    return f"{value:.{digits}f}"


def apply_axis_style(ax: plt.Axes, means: np.ndarray, stds: np.ndarray,
                     metric: str, upper_padding: float = 0.25) -> float:
    """Keep the zero reference and show the complete, unmodified SD extent."""
    high = max(float(np.max(means + stds)), 1e-6)
    low = min(0.0, float(np.min(means - stds)))
    # Negative lower SD extents are statistical variation, not physical negative
    # outcomes. Never alter the input SD to force a nonnegative whisker.
    lower = low * 1.1 if low < 0 else 0.0
    upper = high * (1.0 + upper_padding)
    if metric == "handovers":
        upper = max(upper, 1.0)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=3))
    elif metric in ("qoe_any_pct", "wifi_pct") and high < 1e-5:
        upper = 1.0
    ax.set_ylim(lower, upper)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color="#E3E9ED", linewidth=0.75)
    ax.xaxis.grid(False)
    ax.axhline(0, color="#9DAFB9", linewidth=0.8)
    ax.tick_params(axis="both", length=0, pad=7)
    return upper - lower


def add_footer(fig: plt.Figure, *, extra_note: str) -> None:
    fig.text(0.03, 0.105, REPEATS_NOTE, fontsize=11, color="#415A6B")
    fig.text(0.03, 0.071, extra_note, fontsize=10, color="#415A6B")
    fig.text(0.03, 0.034, CAPTION, fontsize=10, color="#415A6B")


def save_figure(fig: plt.Figure, destination: Path, *, pdf: bool = False) -> list[Path]:
    extensions = ["png", "svg"] + (["pdf"] if pdf else [])
    outputs = []
    for extension in extensions:
        path = destination.with_suffix(f".{extension}")
        fig.savefig(path, dpi=300, metadata={"Title": destination.stem.replace("_", " ")})
        outputs.append(path)
    plt.close(fig)
    return outputs


def metric_figure(summary: pd.DataFrame, metric: str, directory: Path) -> list[Path]:
    meta = METRICS[metric]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 7.6), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.975, top=0.76, bottom=0.23, wspace=0.15)
    fig.suptitle(f"RSSI-only Baseline vs SmartConnect\n{meta['title']}",
                 x=0.5, y=0.955, fontsize=19, fontweight="bold", linespacing=1.45)
    fig.legend(handles=[Patch(facecolor=COLORS[m], label=METHOD_NAMES[m]) for m in METHODS],
               loc="upper center", bbox_to_anchor=(0.5, 0.835), ncol=2, frameon=False)
    all_means, all_stds = [], []
    panels = []
    for ax, application in zip(axes, APPLICATIONS):
        positions = np.arange(len(SCENARIOS))
        panel_means, panel_stds, containers = [], [], []
        for index, method in enumerate(METHODS):
            values = [observation(summary, s, application, method, metric) for s in SCENARIOS]
            means, stds = np.asarray(values).T
            offset = (-0.19, 0.19)[index]
            bars = ax.bar(positions + offset, means, width=0.34,
                          color=COLORS[method], edgecolor="white", linewidth=0.5,
                          yerr=stds, error_kw={"ecolor": "#1D3444", "capsize": 4,
                                             "elinewidth": 1.15, "capthick": 1.15})
            containers.append((bars, means, stds))
            panel_means.extend(means)
            panel_stds.extend(stds)
        panel_means = np.asarray(panel_means)
        panel_stds = np.asarray(panel_stds)
        all_means.extend(panel_means)
        all_stds.extend(panel_stds)
        panels.append((ax, containers))
        ax.set_title(APPLICATION_NAMES[application], fontsize=15, pad=17, fontweight="bold")
        ax.set_xticks(positions, [SCENARIO_NAMES[s].replace(" ", "\n", 1) for s in SCENARIOS])
        ax.set_xlim(-0.6, 3.6)
    all_means = np.asarray(all_means)
    all_stds = np.asarray(all_stds)
    for ax, containers in panels:
        extent = apply_axis_style(ax, all_means, all_stds, metric)
        for bars, means, stds in containers:
            for bar, mean, std in zip(bars, means, stds):
                ax.text(bar.get_x() + bar.get_width() / 2, mean + std + extent * 0.023,
                        format_value(mean, meta["digits"]), ha="center", va="bottom",
                        fontsize=9.5, color="#1D3444")
    axes[0].set_ylabel(meta["axis"], labelpad=10)
    add_footer(fig, extra_note=meta["note"])
    return save_figure(fig, directory / f"comparison_{metric}")


def dashboard_figure(summary: pd.DataFrame, scenario: str,
                     application: str, directory: Path) -> list[Path]:
    fig, axes = plt.subplots(2, 3, figsize=(14.2, 9.0))
    fig.subplots_adjust(left=0.08, right=0.975, top=0.765, bottom=0.20, wspace=0.32, hspace=0.65)
    fig.suptitle(
        f"{SCENARIO_NAMES[scenario]} · {APPLICATION_NAMES[application]}\n"
        "RSSI-only Baseline vs SmartConnect",
        x=0.5, y=0.956, fontsize=20, fontweight="bold", linespacing=1.45,
    )
    fig.legend(handles=[Patch(facecolor=COLORS[m], label=METHOD_NAMES[m]) for m in METHODS],
               loc="upper center", bbox_to_anchor=(0.5, 0.845), ncol=2, frameon=False)
    for ax, metric in zip(axes.flat, DASHBOARD_METRICS):
        values = [observation(summary, scenario, application, method, metric) for method in METHODS]
        means, stds = np.asarray(values).T
        bars = ax.bar((0, 1), means, width=0.5,
                      color=[COLORS[method] for method in METHODS], edgecolor="white", linewidth=0.5,
                      yerr=stds, error_kw={"ecolor": "#1D3444", "capsize": 5,
                                         "elinewidth": 1.2, "capthick": 1.2})
        extent = apply_axis_style(ax, means, stds, metric, upper_padding=0.32)
        meta = METRICS[metric]
        ax.set_title(meta["short"], fontweight="bold", pad=13, fontsize=13)
        ax.set_xticks((0, 1), ("RSSI-only\nBaseline", "SmartConnect"))
        ax.set_xlim(-0.6, 1.6)
        for bar, mean, std in zip(bars, means, stds):
            value_text = f"{format_value(mean, meta['digits'])} ± {format_value(std, meta['digits'])}"
            ax.text(bar.get_x() + bar.get_width() / 2, mean + std + extent * 0.027,
                    value_text, ha="center", va="bottom", fontsize=10, color="#1D3444")
    fig.text(0.03, 0.118, REPEATS_NOTE, fontsize=11, color="#415A6B")
    fig.text(0.03, 0.086,
             "Capacity is the assumed available path capacity, not achieved goodput. QoE violations count abstract simulated steps.",
             fontsize=10, color="#415A6B")
    fig.text(0.03, 0.044, CAPTION, fontsize=10, color="#415A6B")
    return save_figure(fig, directory / f"dashboard_{scenario}_{application}", pdf=True)


def table_figure(summary: pd.DataFrame, scenario: str, directory: Path) -> list[Path]:
    """One slide-copyable scenario table comparing both applications."""
    fig, axes = plt.subplots(1, 2, figsize=(14.2, 8.2))
    fig.subplots_adjust(left=0.025, right=0.975, top=0.745, bottom=0.225, wspace=0.08)
    fig.suptitle(
        f"{SCENARIO_NAMES[scenario]} · Comparison Table\nRSSI-only Baseline vs SmartConnect",
        x=0.5, y=0.948, fontsize=20, fontweight="bold", linespacing=1.45,
    )
    for ax, application in zip(axes, APPLICATIONS):
        ax.set_axis_off()
        ax.set_title(APPLICATION_NAMES[application], fontsize=16, fontweight="bold", pad=20)
        rows = []
        for metric, meta in METRICS.items():
            row = [meta["short"]]
            for method in METHODS:
                mean, std = observation(summary, scenario, application, method, metric)
                row.append(f"{format_value(mean, meta['digits'])} ± {format_value(std, meta['digits'])}")
            rows.append(row)
        table = ax.table(
            cellText=rows,
            colLabels=("Metric", "RSSI-only Baseline", "SmartConnect"),
            colWidths=(0.46, 0.28, 0.26),
            cellLoc="center",
            bbox=[0.0, 0.0, 1.0, 1.0],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10.5)
        for (row_index, column_index), cell in table.get_celld().items():
            cell.set_edgecolor("#DDE6EC")
            cell.set_linewidth(0.65)
            cell.PAD = 0.06
            if row_index == 0:
                cell.set_text_props(weight="bold", color="white", fontsize=10)
                cell.set_facecolor(("#415A6B", COLORS["baseline"], COLORS["smartconnect"])[column_index])
                cell.set_height(cell.get_height() * 1.15)
            else:
                cell.set_facecolor("#F0F5F7" if row_index % 2 == 0 else "white")
                if column_index == 0:
                    cell.set_text_props(ha="left", color="#1D3444")
                    cell.PAD = 0.055
                else:
                    cell.set_text_props(color="#1D3444")
    fig.text(0.03, 0.132, REPEATS_NOTE, fontsize=11, color="#415A6B")
    fig.text(0.03, 0.092,
             "Capacity is assumed available path capacity, not achieved goodput. Occupancy and QoE refer to abstract simulated steps.",
             fontsize=10, color="#415A6B")
    fig.text(0.03, 0.050, CAPTION, fontsize=10, color="#415A6B")
    return save_figure(fig, directory / f"table_{scenario}", pdf=True)


def make_contact_sheet(png_paths: list[Path], preview_path: Path) -> None:
    """Create a local QA preview from final repeated-seed charts only."""
    columns, tile_width, image_height, label_height = 3, 620, 415, 45
    rows = math.ceil(len(png_paths) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * (image_height + label_height)), "#E6EBEF")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for index, path in enumerate(png_paths):
        with Image.open(path) as chart:
            chart = chart.convert("RGB")
            chart.thumbnail((tile_width - 12, image_height - 12), Image.Resampling.LANCZOS)
            x = (index % columns) * tile_width + (tile_width - chart.width) // 2
            y = (index // columns) * (image_height + label_height) + (image_height - chart.height) // 2
            sheet.paste(chart, (x, y))
        label_x = (index % columns) * tile_width + 10
        label_y = (index // columns) * (image_height + label_height) + image_height + 5
        draw.text((label_x, label_y), path.stem, fill="#1D3444", font=font)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(preview_path, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", type=Path, required=True, help="Directory containing final experiment tables.")
    parser.add_argument("--summary", type=Path, help="Explicit tidy mean_sd.csv input, overriding results-dir discovery.")
    parser.add_argument("--preview-path", type=Path,
                        default=Path.cwd() / "work" / "final_figure_contact_sheet.jpg",
                        help="QA contact sheet path (default: work/final_figure_contact_sheet.jpg).")
    args = parser.parse_args()
    root = args.results_dir.expanduser().resolve()
    if args.summary:
        summary_path = args.summary.expanduser().resolve()
    else:
        candidates = [root / "tables" / "mean_sd.csv", root / "mean_sd.csv"]
        found = [candidate for candidate in candidates if candidate.is_file()]
        if len(found) != 1:
            parser.error("Expected one mean_sd.csv at results-dir/tables or results-dir; specify --summary if needed.")
        summary_path = found[0]
    if not summary_path.is_file():
        parser.error(f"Final summary does not exist: {summary_path}")
    summary = load_summary(summary_path)
    configure_style()
    directory = root / "figures"
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for metric in METRICS:
        outputs.extend(metric_figure(summary, metric, directory))
    for scenario in SCENARIOS:
        for application in APPLICATIONS:
            outputs.extend(dashboard_figure(summary, scenario, application, directory))
    for scenario in SCENARIOS:
        outputs.extend(table_figure(summary, scenario, directory))
    manifest_path = directory / "figure_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["figure", "format", "relative_path", "source_summary", "caption"])
        writer.writeheader()
        for path in outputs:
            writer.writerow({
                "figure": path.stem,
                "format": path.suffix.lstrip("."),
                "relative_path": str(path.relative_to(root)),
                "source_summary": str(summary_path.relative_to(root)) if summary_path.is_relative_to(root) else str(summary_path),
                "caption": CAPTION,
            })
    png_paths = [path for path in outputs if path.suffix == ".png"]
    make_contact_sheet(png_paths, args.preview_path.expanduser().resolve())
    print(f"Created {len(png_paths)} final comparison figures ({len(outputs)} PNG/SVG/PDF files).")
    print(f"Source: {summary_path}")
    print(f"Figure manifest: {manifest_path}")
    print(f"QA contact sheet: {args.preview_path.expanduser().resolve()}")


if __name__ == "__main__":
    main()
