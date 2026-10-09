"""Synthetic network traces: simulation assumptions, not measured real-world results.

Deterministic scenario trends plus small Gaussian noise model plausible conditions.
RSSI is an illustrative comparable signal metric for both paths; this is not a
calibrated comparison of actual Wi-Fi RSSI with cellular RSRP.
Time denotes a simulation step, not a measured wall-clock interval.
"""

import numpy as np
import pandas as pd

from config import SIMULATION_DURATION, RANDOM_SEED


def _clip(values, low, high):
    """Keep assumed simulated values within reasonable limits."""
    return np.clip(values, low, high)


def generate_scenario(name, seed=RANDOM_SEED):
    """
    Generate assumed Wi-Fi and 5G-like conditions, not real measurements.

    Uses a local RNG: identical name/seed and dependency versions produce
    identical traces, independent of global RNG state and algorithm decisions.
    Units: RSSI dBm, latency/jitter ms, loss percent, throughput Mbps.

    The same generated trace can later be given to:
    1. Strongest Signal First baseline
    2. SmartConnect

    This allows a fair comparison under identical conditions.
    """

    rng = np.random.default_rng(seed)
    t = np.arange(SIMULATION_DURATION)

    # ---------------------------------------------------------
    # SCENARIO 1: Leaving Wi-Fi coverage
    # ---------------------------------------------------------
    if name == "leaving_wifi":

        # Wi-Fi gradually deteriorates as the user moves away.
        wifi_rssi = -45 - 0.40 * t + rng.normal(0, 1.2, len(t))
        wifi_latency = 20 + 0.55 * t + rng.normal(0, 2.0, len(t))
        wifi_loss = 0.1 + 0.045 * t + rng.normal(0, 0.15, len(t))
        wifi_jitter = 4 + 0.22 * t + rng.normal(0, 1.0, len(t))
        wifi_throughput = 80 - 0.60 * t + rng.normal(0, 3.0, len(t))

        # 5G-like path stays comparatively stable.
        g5_rssi = -68 + rng.normal(0, 1.5, len(t))
        g5_latency = 35 + rng.normal(0, 3.0, len(t))
        g5_loss = 0.5 + rng.normal(0, 0.15, len(t))
        g5_jitter = 8 + rng.normal(0, 1.2, len(t))
        g5_throughput = 55 + rng.normal(0, 4.0, len(t))

    # ---------------------------------------------------------
    # SCENARIO 2: Congested Wi-Fi
    # ---------------------------------------------------------
    elif name == "congested_wifi":

        # RSSI remains strong, but QoS deteriorates after t = 30.
        # This is one of the most important SmartConnect scenarios.
        wifi_rssi = -52 + rng.normal(0, 1.2, len(t))

        congestion = np.maximum(t - 30, 0)

        wifi_latency = (
            22
            + 1.0 * congestion
            + rng.normal(0, 3.0, len(t))
        )

        wifi_loss = (
            0.15
            + 0.07 * congestion
            + rng.normal(0, 0.15, len(t))
        )

        wifi_jitter = (
            5
            + 0.35 * congestion
            + rng.normal(0, 1.2, len(t))
        )

        wifi_throughput = (
            75
            - 0.75 * congestion
            + rng.normal(0, 3.0, len(t))
        )

        g5_rssi = -69 + rng.normal(0, 1.5, len(t))
        g5_latency = 36 + rng.normal(0, 3.0, len(t))
        g5_loss = 0.5 + rng.normal(0, 0.12, len(t))
        g5_jitter = 8 + rng.normal(0, 1.0, len(t))
        g5_throughput = 52 + rng.normal(0, 4.0, len(t))

    # ---------------------------------------------------------
    # SCENARIO 3: Large file download
    # ---------------------------------------------------------
    elif name == "large_download":

        # Both networks are usable.
        # Wi-Fi has better latency but the 5G-like path has
        # considerably better throughput.
        wifi_rssi = -58 + rng.normal(0, 1.5, len(t))
        wifi_latency = 25 + rng.normal(0, 2.5, len(t))
        wifi_loss = 0.4 + rng.normal(0, 0.12, len(t))
        wifi_jitter = 6 + rng.normal(0, 1.0, len(t))
        wifi_throughput = 35 + rng.normal(0, 3.0, len(t))

        g5_rssi = -66 + rng.normal(0, 1.5, len(t))
        g5_latency = 38 + rng.normal(0, 3.0, len(t))
        g5_loss = 0.5 + rng.normal(0, 0.12, len(t))
        g5_jitter = 8 + rng.normal(0, 1.0, len(t))
        g5_throughput = 70 + rng.normal(0, 4.0, len(t))

    # ---------------------------------------------------------
    # SCENARIO 4: Recovery / Return
    # ---------------------------------------------------------
    elif name == "recovery":

        # The user moves away from Wi-Fi, reaches the weakest point,
        # then moves back toward the Wi-Fi access point.
        distance_effect = np.concatenate([
            np.linspace(0, 35, len(t) // 2),
            np.linspace(35, 0, len(t) - len(t) // 2)
        ])

        wifi_rssi = (
            -45
            - distance_effect
            + rng.normal(0, 1.2, len(t))
        )

        wifi_latency = (
            20
            + 1.4 * distance_effect
            + rng.normal(0, 3.0, len(t))
        )

        wifi_loss = (
            0.1
            + 0.11 * distance_effect
            + rng.normal(0, 0.15, len(t))
        )

        wifi_jitter = (
            4
            + 0.45 * distance_effect
            + rng.normal(0, 1.0, len(t))
        )

        wifi_throughput = (
            80
            - 1.5 * distance_effect
            + rng.normal(0, 3.0, len(t))
        )

        g5_rssi = -68 + rng.normal(0, 1.5, len(t))
        g5_latency = 35 + rng.normal(0, 3.0, len(t))
        g5_loss = 0.5 + rng.normal(0, 0.12, len(t))
        g5_jitter = 8 + rng.normal(0, 1.0, len(t))
        g5_throughput = 55 + rng.normal(0, 4.0, len(t))

    else:
        raise ValueError(
            f"Unknown scenario '{name}'. "
            "Use leaving_wifi, congested_wifi, large_download, or recovery."
        )

    # ---------------------------------------------------------
    # Keep values inside valid simulation ranges
    # ---------------------------------------------------------

    wifi_rssi = _clip(wifi_rssi, -95, -30)
    g5_rssi = _clip(g5_rssi, -95, -30)

    wifi_latency = _clip(wifi_latency, 1, 300)
    g5_latency = _clip(g5_latency, 1, 300)

    wifi_loss = _clip(wifi_loss, 0, 15)
    g5_loss = _clip(g5_loss, 0, 15)

    wifi_jitter = _clip(wifi_jitter, 0, 100)
    g5_jitter = _clip(g5_jitter, 0, 100)

    wifi_throughput = _clip(wifi_throughput, 1, 150)
    g5_throughput = _clip(g5_throughput, 1, 150)

    # ---------------------------------------------------------
    # Create the final network trace
    # ---------------------------------------------------------

    data = pd.DataFrame({
        "time": t,

        "wifi_rssi": wifi_rssi,
        "wifi_latency": wifi_latency,
        "wifi_loss": wifi_loss,
        "wifi_jitter": wifi_jitter,
        "wifi_throughput": wifi_throughput,

        "g5_rssi": g5_rssi,
        "g5_latency": g5_latency,
        "g5_loss": g5_loss,
        "g5_jitter": g5_jitter,
        "g5_throughput": g5_throughput
    })

    return data
