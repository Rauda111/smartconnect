import time

from hardware.network_monitor import measure_network

ROUTERS = {
    "A": "192.168.10.1",
    "B": "192.168.10.2",
}

IMPROVEMENT_THRESHOLD = 0.20
REQUIRED_CONSECUTIVE = 3
COOLDOWN_SECONDS = 30


def calculate_score(metrics):
    if not metrics["available"]:
        return float("inf")

    return (
        metrics["latency_ms"]
        + 2 * metrics["jitter_ms"]
        + 10 * metrics["packet_loss_percent"]
    )


def main():
    current_path = "A"
    candidate_path = None
    consecutive_count = 0
    last_switch_time = time.monotonic() - COOLDOWN_SECONDS

    print("SmartConnect Stability Controller")
    print("Decision-only mode")
    print("No physical routes will be changed.")

    try:
        while True:
            scores = {}

            for path, ip in ROUTERS.items():
                metrics = measure_network(ip)
                scores[path] = calculate_score(metrics)

                print(
                    f"Path {path}: "
                    f"Score={scores[path]:.3f}, "
                    f"Available={metrics['available']}"
                )

            alternative = "B" if current_path == "A" else "A"

            current_score = scores[current_path]
            alternative_score = scores[alternative]

            if current_score == float("inf"):
                better = alternative_score < float("inf")
            else:
                better = (
                    alternative_score
                    < current_score * (1 - IMPROVEMENT_THRESHOLD)
                )

            if better:
                if candidate_path == alternative:
                    consecutive_count += 1
                else:
                    candidate_path = alternative
                    consecutive_count = 1
            else:
                candidate_path = None
                consecutive_count = 0

            elapsed = time.monotonic() - last_switch_time

            if (
                consecutive_count >= REQUIRED_CONSECUTIVE
                and elapsed >= COOLDOWN_SECONDS
            ):
                current_path = alternative
                last_switch_time = time.monotonic()
                candidate_path = None
                consecutive_count = 0

                print(
                    f"RECOMMENDED SWITCH: Path {current_path}"
                )
            else:
                print(
                    f"Recommended active path: {current_path}"
                )
                print(
                    f"Consecutive better evaluations: "
                    f"{consecutive_count}/{REQUIRED_CONSECUTIVE}"
                )

            print("Next evaluation...\n")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nStability controller stopped.")


if __name__ == "__main__":
    main()
