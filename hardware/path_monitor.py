import subprocess
import time

from hardware.network_monitor import measure_network

DESTINATION = "192.168.30.10"
NETWORK = "192.168.30.0/24"
INTERFACE = "eno2"

ROUTERS = {
    "A": "192.168.10.1",
    "B": "192.168.10.2",
}


def switch_path(path):
    gateway = ROUTERS[path]

    command = [
        "ip",
        "route",
        "replace",
        NETWORK,
        "via",
        gateway,
        "dev",
        INTERFACE,
    ]

    subprocess.run(command, check=True)

    print(f"\nTesting Path {path} via {gateway}")


def test_path(path):
    switch_path(path)

    time.sleep(2)

    metrics = measure_network(DESTINATION)

    print(f"Path {path} results:")
    print(f"Available: {metrics['available']}")
    print(f"Latency: {metrics['latency_ms']}")
    print(f"Jitter: {metrics['jitter_ms']}")
    print(f"Packet loss: {metrics['packet_loss_percent']}%")

    return metrics


def main():
    print("SmartConnect End-to-End Path Monitor")
    print("-----------------------------------")

    original_gateway = None

    try:
        result = subprocess.run(
            ["ip", "route", "get", DESTINATION],
            capture_output=True,
            text=True,
            check=True,
        )

        parts = result.stdout.split()

        if "via" in parts:
            original_gateway = parts[parts.index("via") + 1]

        if original_gateway not in ROUTERS.values():
            raise RuntimeError(
                "Cannot identify the original SmartConnect gateway."
            )

        for path in ROUTERS:
            test_path(path)

    finally:
        if original_gateway is not None:
            print(f"\nRestoring original gateway: {original_gateway}")

            subprocess.run(
                [
                    "ip",
                    "route",
                    "replace",
                    NETWORK,
                    "via",
                    original_gateway,
                    "dev",
                    INTERFACE,
                ],
                check=True,
            )


if __name__ == "__main__":
    main()
