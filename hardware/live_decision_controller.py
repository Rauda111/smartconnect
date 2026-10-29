import time
import math

from hardware.live_path_monitor import measure_path
from hardware.end_to_end_decision import calculate_score

PATHS = {
    "A": 101,
    "B": 102,
}

IMPROVEMENT_THRESHOLD = 0.20
REQUIRED_CONSECUTIVE = 3
COOLDOWN_SECONDS = 30


def main():
    current_path = "A"
    candidate = None
    consecutive = 0
    last_switch = time.monotonic() - COOLDOWN_SECONDS

    print("SmartConnect Live Decision Controller")
    print("-------------------------------------")
    print("DECISION-ONLY MODE: No routes will be changed.")

    try:
        while True:
            scores = {}

            for path, mark in PATHS.items():
                metrics = measure_path(path, mark)
                score = calculate_score(metrics)
                scores[path] = score

                print(
                    f"Path {path}: "
                    f"Available={metrics['available']}, "
                    f"Score={score:.3f}"
                )

            alternative = "B" if current_path == "A" else "A"

            current_score = scores[current_path]
            alternative_score = scores[alternative]

            if math.isinf(current_score):
                better = math.isfinite(alternative_score)
            else:
                better = (
                    alternative_score
                    < current_score * (1 - IMPROVEMENT_THRESHOLD)
                )

            if better:
                if candidate == alternative:
                    consecutive += 1
                else:
                    candidate = alternative
                    consecutive = 1
            else:
                candidate = None
                consecutive = 0

            elapsed = time.monotonic() - last_switch

            if (
                consecutive >= REQUIRED_CONSECUTIVE
                and elapsed >= COOLDOWN_SECONDS
            ):
                print(f"RECOMMENDED SWITCH: Path {alternative}")

                current_path = alternative
                last_switch = time.monotonic()
                candidate = None
                consecutive = 0
            else:
                print(f"Recommended active path: {current_path}")
                print(
                    f"Consecutive better evaluations: "
                    f"{consecutive}/{REQUIRED_CONSECUTIVE}"
                )

            print("\nNext evaluation...\n")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nLive decision controller stopped.")


if __name__ == "__main__":
    main()
