import time

from hardware.end_to_end_decision import (
    read_measurements,
    calculate_score,
)

IMPROVEMENT_THRESHOLD = 0.20
REQUIRED_CONSECUTIVE = 3
COOLDOWN_SECONDS = 30


def main():
    current_path = "A"
    candidate_path = None
    consecutive_count = 0
    last_switch = time.monotonic() - COOLDOWN_SECONDS

    print("SmartConnect Integrated Decision Engine")
    print("---------------------------------------")
    print("OFFLINE MODE: No physical routes will be changed.")

    try:
        while True:
            measurements = read_measurements()

            if set(measurements) != {"A", "B"}:
                print("Missing path measurements.")
                break

            scores = {
                path: calculate_score(metrics)
                for path, metrics in measurements.items()
            }

            for path in ("A", "B"):
                print(f"Path {path}: Score={scores[path]:.3f}")

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

            elapsed = time.monotonic() - last_switch

            if (
                consecutive_count >= REQUIRED_CONSECUTIVE
                and elapsed >= COOLDOWN_SECONDS
            ):
                current_path = alternative
                last_switch = time.monotonic()
                candidate_path = None
                consecutive_count = 0

                print(f"RECOMMENDED SWITCH: Path {current_path}")
            else:
                print(f"Recommended active path: {current_path}")
                print(
                    f"Consecutive better evaluations: "
                    f"{consecutive_count}/{REQUIRED_CONSECUTIVE}"
                )

            print("Next evaluation...\n")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nIntegrated decision engine stopped.")


if __name__ == "__main__":
    main()
