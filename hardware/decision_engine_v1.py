import time

from hardware.network_monitor import measure_network

ROUTERS = {
    "A": "192.168.10.1",
    "B": "192.168.10.2",
}


def calculate_score(metrics):
    if not metrics["available"]:
        return float("inf")

    latency = metrics["latency_ms"]
    jitter = metrics["jitter_ms"]
    loss = metrics["packet_loss_percent"]

    return latency + (2 * jitter) + (10 * loss)


def main():
    print("SmartConnect Decision Engine")
    print("----------------------------")
    print("Decision-only mode: no routes will be changed.")

    try:
        while True:
            scores = {}

            for path, ip in ROUTERS.items():
                metrics = measure_network(ip)
                score = calculate_score(metrics)

                scores[path] = score

                print(f"\nPath {path}")
                print(f"Gateway: {ip}")
                print(f"Available: {metrics['available']}")
                print(f"Score: {score:.3f}")

            if all(score == float("inf") for score in scores.values()):
                print("\nNo available network path.")
            else:
                best_path = min(scores, key=scores.get)

                print(f"\nRecommended Path: {best_path}")

            print("\nNext evaluation in 5 seconds...")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nDecision engine stopped.")


if __name__ == "__main__":
    main()
