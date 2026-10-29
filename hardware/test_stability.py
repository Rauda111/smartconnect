from unittest.mock import patch

from hardware import stability_controller


def fake_measure_network(ip):
    if ip == "192.168.10.1":
        return {
            "latency_ms": 10.0,
            "jitter_ms": 2.0,
            "packet_loss_percent": 0.0,
            "available": True,
        }

    return {
        "latency_ms": 1.0,
        "jitter_ms": 0.1,
        "packet_loss_percent": 0.0,
        "available": True,
    }


def stop_after_three_cycles(seconds):
    stop_after_three_cycles.count += 1

    if stop_after_three_cycles.count >= 3:
        raise KeyboardInterrupt


stop_after_three_cycles.count = 0

with patch.object(
    stability_controller,
    "measure_network",
    side_effect=fake_measure_network,
):
    with patch.object(
        stability_controller.time,
        "sleep",
        side_effect=stop_after_three_cycles,
    ):
        stability_controller.main()
