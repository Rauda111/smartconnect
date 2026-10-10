"""Application-aware decisions for synthetic network traces.

All thresholds are prototype assumptions, not validated service guarantees.
Hold and dwell durations are measured in simulation steps, not seconds.
"""

import numpy as np

# Each profile's weights sum to 1.
WEIGHTS = {
    "video_call": {
        "latency": 0.30, "loss": 0.30, "jitter": 0.20,
        "throughput": 0.10, "rssi": 0.10,
    },
    "file_download": {
        "latency": 0.15, "loss": 0.15, "jitter": 0.10,
        "throughput": 0.45, "rssi": 0.15,
    },
}

# Fixed normalization bounds: do not fit them to future trace values.
BOUNDS = {
    "rssi": (-95, -30),
    "latency": (1, 150),
    "loss": (0, 5),
    "jitter": (0, 50),
    "throughput": (0, 100),
}

# Prototype QoE guardrails. Packet loss is percent, not a fraction.
LIMITS = {
    "video_call": {"latency": 60, "loss": 2, "jitter": 20},
    "file_download": {"loss": 3, "throughput": 20},
}


def normalize(metrics):
    """Convert metrics to [0, 1], where higher always means better."""
    values = {}
    for metric, (low, high) in BOUNDS.items():
        value = float(metrics[metric])
        if not np.isfinite(value):
            raise ValueError(f"Non-finite metric: {metric}")
        scaled = np.clip((value - low) / (high - low), 0, 1)
        if metric in ("latency", "loss", "jitter"):
            scaled = 1 - scaled
        values[metric] = float(scaled)
    return values


def qos_score(metrics, application):
    values = normalize(metrics)
    return sum(
        WEIGHTS[application][metric] * values[metric]
        for metric in values
    )


def guardrail_breaches(metrics, application):
    breaches = []
    for metric, limit in LIMITS[application].items():
        value = metrics[metric]
        bad = value < limit if metric == "throughput" else value > limit
        if bad:
            breaches.append(metric)
    return breaches


def classify_trend(slope, threshold=0.002):
    """Score change per sample; threshold is a prototype noise deadband."""
    if slope > threshold:
        return "Improving"
    if slope < -threshold:
        return "Degrading"
    return "Stable"


def apply_smartconnect(
    trace, application="video_call", safety_margin=0.05,
    hold_steps=3, dwell_steps=8, trend_window=5,
    trend_weight=0.5, trend_threshold=0.002,
):
    """Return a new DataFrame; preserve input and use only past/current data."""
    if application not in WEIGHTS:
        raise ValueError("Use 'video_call' or 'file_download'.")
    if hold_steps < 1 or dwell_steps < 0 or trend_window < 2:
        raise ValueError("Invalid hold, dwell, or trend window.")
    if safety_margin < 0 or trend_weight < 0 or trend_threshold < 0:
        raise ValueError("Margin and trend weight must be nonnegative.")

    required = ["time"] + [
        f"{prefix}_{metric}"
        for prefix in ("wifi", "g5") for metric in BOUNDS
    ]
    if any(column not in trace for column in required):
        raise ValueError("Trace is missing required metric columns.")
    if not np.isfinite(trace[required].to_numpy(dtype=float)).all():
        raise ValueError("Trace contains non-finite values.")
    if not trace["time"].is_monotonic_increasing or trace["time"].duplicated().any():
        raise ValueError("Time must be strictly increasing.")

    current = "WiFi"
    pending = None
    streak = 0
    last_switch = -dwell_steps
    history = {"WiFi": [], "5G": []}
    records = []

    for step, (_, row) in enumerate(trace.iterrows()):
        metrics = {
            network: {
                metric: float(row[f"{prefix}_{metric}"])
                for metric in BOUNDS
            }
            for network, prefix in (("WiFi", "wifi"), ("5G", "g5"))
        }

        scores, adjusted, slopes, breaches = {}, {}, {}, {}
        for network in ("WiFi", "5G"):
            scores[network] = qos_score(metrics[network], application)
            history[network].append(scores[network])
            window = history[network][-trend_window:]
            slopes[network] = (
                float(np.polyfit(np.arange(len(window)), window, 1)[0])
                if len(window) >= 2 else 0.0
            )
            adjusted[network] = float(np.clip(
                scores[network] + trend_weight * slopes[network], 0, 1
            ))
            breaches[network] = guardrail_breaches(
                metrics[network], application
            )

        previous = current
        candidate = "5G" if current == "WiFi" else "WiFi"
        advantage = adjusted[candidate] - adjusted[current]

        # Guardrail rescue requires a usable, better-scoring alternative.
        rescue = (
            bool(breaches[current]) and not breaches[candidate]
            and advantage > 0
        )
        superior = (
            not breaches[candidate]
            and (advantage >= safety_margin or rescue)
        )

        if superior:
            streak = streak + 1 if pending == candidate else 1
            pending = candidate
        else:
            streak = 0
            pending = None

        held_steps = streak
        dwell_ok = step - last_switch >= dwell_steps
        switched = superior and held_steps >= hold_steps and dwell_ok

        if switched:
            current = candidate
            last_switch = step
            reason = (
                f"Switch to {current}: "
                + ("current path breaches QoE guardrail; " if rescue else "")
                + f"advantage {advantage:.3f}, "
                + f"held for {held_steps} steps; dwell satisfied."
            )
            pending = None
            streak = 0
        elif superior and not dwell_ok:
            reason = "Stay: minimum dwell period is still active."
        elif superior:
            reason = (
                f"Stay: candidate advantage sustained for "
                f"{held_steps}/{hold_steps} required steps."
            )
        elif breaches[candidate]:
            reason = "Stay: alternative breaches application guardrails."
        else:
            reason = "Stay: alternative has insufficient score advantage."

        # This is a heuristic label, not statistical confidence.
        strength = (
            "High" if superior and advantage >= 2 * safety_margin
            else "Medium" if superior else "Low"
        )

        records.append({
            "selected_network": current,
            "previous_network": previous,
            "handover": bool(switched),
            "wifi_score": scores["WiFi"],
            "g5_score": scores["5G"],
            "wifi_adjusted_score": adjusted["WiFi"],
            "g5_adjusted_score": adjusted["5G"],
            "wifi_trend_slope": slopes["WiFi"],
            "g5_trend_slope": slopes["5G"],
            "wifi_trend": classify_trend(slopes["WiFi"], trend_threshold),
            "g5_trend": classify_trend(slopes["5G"], trend_threshold),
            "wifi_guardrail": bool(breaches["WiFi"]),
            "g5_guardrail": bool(breaches["5G"]),
            "candidate_network": candidate,
            "candidate_advantage": advantage,
            "hold_count": held_steps,
            "decision_strength": strength,
            "decision_explanation": reason,
        })

    result = trace.copy(deep=True)
    if records:
        for column in records[0]:
            result[column] = [record[column] for record in records]
    return result
