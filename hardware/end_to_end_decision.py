import re
from pathlib import Path

RESULT_FILE = Path("results/path_test_01.txt")


def read_measurements():
    text = RESULT_FILE.read_text()

    pattern = (
        r"Path ([AB]) results:\s*"
        r"Available:\s*(True|False)\s*"
        r"Latency:\s*([\d.]+|None)\s*"
        r"Jitter:\s*([\d.]+|None)\s*"
        r"Packet loss:\s*([\d.]+)%"
    )

    measurements = {}

    for match in re.finditer(pattern, text):
        path, available, latency, jitter, loss = match.groups()

        measurements[path] = {
            "available": available == "True",
            "latency_ms": (
                float(latency) if latency != "None" else None
            ),
            "jitter_ms": (
                float(jitter) if jitter != "None" else None
            ),
            "packet_loss_percent": float(loss),
        }

    return measurements


def calculate_score(metrics):
    if not metrics["available"]:
        return float("inf")

    return (
        metrics["latency_ms"]
        + 2 * metrics["jitter_ms"]
        + 10 * metrics["packet_loss_percent"]
    )


def main():
    print("SmartConnect End-to-End Decision Engine")
    print("---------------------------------------")
    print("Offline analysis: no routes will be changed.")

    measurements = read_measurements()

    if set(measurements) != {"A", "B"}:
        print("Error: Missing measurements for Path A or B.")
        return

    scores = {}

    for path, metrics in measurements.items():
        score = calculate_score(metrics)
        scores[path] = score

        print(f"\nPath {path}")
        print(f"Latency: {metrics['latency_ms']} ms")
        print(f"Jitter: {metrics['jitter_ms']} ms")
        print(f"Packet loss: {metrics['packet_loss_percent']}%")
        print(f"Score: {score:.3f}")

    if all(score == float("inf") for score in scores.values()):
        print("\nNo available path.")
    else:
        best_path = min(scores, key=scores.get)
        print(f"\nBest measured path: {best_path}")

    print("\nNo physical routes were changed.")


if __name__ == "__main__":
    main()
