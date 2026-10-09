"""Run the RSSI baseline and save simulated-data verification artifacts."""

import argparse
import os
from pathlib import Path
import tempfile

# A writable cache and noninteractive backend also support headless execution.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "smartconnect-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from baseline import apply_baseline
from config import RANDOM_SEED, SCENARIOS
from scenarios import generate_scenario

ROOT = Path(__file__).resolve().parent
METRICS = {
    "rssi": ("RSSI", "dBm"),
    "latency": ("Latency", "ms"),
    "loss": ("Packet loss", "%"),
    "jitter": ("Jitter", "ms"),
    "throughput": ("Throughput", "Mbps"),
}


def save_plots(trace, scenario, seed, directory):
    """Save one comparison per metric; curves verify assumptions, not measurements."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for metric, (label, unit) in METRICS.items():
        fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
        ax.plot(trace["time"], trace[f"wifi_{metric}"], label="Wi-Fi", color="#1764ab")
        ax.plot(trace["time"], trace[f"g5_{metric}"], label="5G-like", color="#c45508")
        ax.set(title=f"{scenario.replace('_', ' ').title()} — {label}\n"
                     f"Simulated-data verification • seed {seed} • not measured results",
               xlabel="Time step", ylabel=f"{label} ({unit})")
        ax.grid(alpha=0.25)
        ax.legend()
        path = directory / f"{scenario}_seed{seed}_{metric}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths


def run_simulation(scenario, seed=RANDOM_SEED):
    trace = generate_scenario(scenario, seed=seed)
    result = apply_baseline(trace)
    output_dir = ROOT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{scenario}_seed{seed}_baseline.csv"
    result.to_csv(csv_path, index=False)
    plot_paths = save_plots(trace, scenario, seed, ROOT / "plots")
    counts = result["selected_network"].value_counts()
    events = result.loc[result["handover"], "time"].tolist()
    print(f"{scenario} | seed={seed} | {len(result)} simulated time steps")
    print(f"Selected: WiFi={counts.get('WiFi', 0)}, 5G={counts.get('5G', 0)}; "
          f"handovers={len(events)} at time steps {events}")
    print(f"CSV: {csv_path}")
    print(f"Verification plots: {len(plot_paths)} PNG files in {ROOT / 'plots'}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED,
                        help=f"Nonnegative random seed (default: {RANDOM_SEED})")
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be nonnegative")
    run_simulation(args.scenario, args.seed)


if __name__ == "__main__":
    main()
