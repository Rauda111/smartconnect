import subprocess
import re
import statistics
import time

ROUTERS = {
    "Path A (Router 1)": "192.168.10.1",
    "Path B (Router 2)": "192.168.10.2",
}


def measure_network(ip):
    command = ["ping", "-n", "-c", "10", "-W", "1", ip]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=20
    )

    output = result.stdout

    times = [
        float(value)
        for value in re.findall(
            r"time[=<]([\d.]+)\s*ms",
            output
        )
    ]

    packet_stats = re.search(
        r"(\d+) packets transmitted,\s*(\d+) received",
        output
    )

    if packet_stats:
        sent = int(packet_stats.group(1))
        received = int(packet_stats.group(2))
    else:
        sent = 10
        received = len(times)

    packet_loss = (
        (sent - received) / sent * 100
        if sent else 100.0
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
        "latency_ms": latency,
        "jitter_ms": jitter,
        "packet_loss_percent": packet_loss,
        "available": received > 0
    }


def main():
    print("SmartConnect Real Network Monitor")
    print("---------------------------------")

    try:
        while True:
            for path, ip in ROUTERS.items():
                metrics = measure_network(ip)

                print(f"\n{path}")
                print(f"IP: {ip}")
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

            print("\nNext measurement cycle...")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    main()
