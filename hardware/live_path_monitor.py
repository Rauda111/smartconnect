import subprocess
import re
import statistics
import time

DESTINATION = "192.168.30.10"

PATHS = {
    "A": 101,
    "B": 102,
}


def measure_path(path, mark):
    command = [
        "ping",
        "-n",
        "-m",
        str(mark),
        "-c",
        "5",
        "-W",
        "1",
        DESTINATION,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
    )

    output = result.stdout + result.stderr

    if (
        result.returncode != 0
        or "failed to set mark" in output.lower()
    ):
        return {
            "available": False,
            "latency_ms": None,
            "jitter_ms": None,
            "packet_loss_percent": 100.0,
        }
    times = [
        float(value)
        for value in re.findall(
            r"time=([\d.]+)\s*ms",
            output,
        )
    ]

    packet_stats = re.search(
        r"(\d+) packets transmitted,\s*(\d+) received",
        output,
    )

    if packet_stats:
        sent = int(packet_stats.group(1))
        received = int(packet_stats.group(2))
    else:
        sent = 5
        received = len(times)

    loss = (
        (sent - received) / sent * 100
        if sent > 0
        else 100.0
    )

    if times:
        latency = statistics.mean(times)

        if len(times) > 1:
            jitter = statistics.mean(
                abs(times[i] - times[i - 1])
                for i in range(1, len(times))
            )
        else:
            jitter = 0.0
    else:
        latency = None
        jitter = None

    return {
        "available": received > 0,
        "latency_ms": latency,
        "jitter_ms": jitter,
        "packet_loss_percent": loss,
    }


def main():
    print("SmartConnect Live Dual-Path Monitor")
    print("-----------------------------------")
    print("Monitoring only: no route changes.")

    try:
        while True:
            for path, mark in PATHS.items():
                metrics = measure_path(path, mark)

                print(f"\nPath {path}")
                print(f"Available: {metrics['available']}")

                if metrics["latency_ms"] is not None:
                    print(
                        f"Latency: "
                        f"{metrics['latency_ms']:.3f} ms"
                    )

                    print(
                        f"Jitter: "
                        f"{metrics['jitter_ms']:.3f} ms"
                    )
                else:
                    print("Latency: unavailable")
                    print("Jitter: unavailable")

                print(
                    f"Packet loss: "
                    f"{metrics['packet_loss_percent']:.1f}%"
                )

            print("\nNext measurement cycle...\n")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nLive monitoring stopped.")


if __name__ == "__main__":
    main()
