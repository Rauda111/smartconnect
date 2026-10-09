"""Student 1 verification: run with venv/bin/python -m unittest -v."""

import unittest
import numpy as np
import pandas as pd

from baseline import apply_baseline, select_network
from config import NETWORKS, RANDOM_SEED, SCENARIOS, SIMULATION_DURATION
from scenarios import generate_scenario


class SimulationTests(unittest.TestCase):
    def test_configuration(self):
        self.assertEqual(SIMULATION_DURATION, 100)
        self.assertEqual(RANDOM_SEED, 42)
        self.assertEqual(SCENARIOS, ["leaving_wifi", "congested_wifi", "large_download", "recovery"])
        self.assertEqual(NETWORKS, ["WiFi", "5G"])

    def test_bounds_and_reproducibility(self):
        bounds = {"rssi": (-95, -30), "latency": (1, 300), "loss": (0, 15),
                  "jitter": (0, 100), "throughput": (1, 150)}
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                trace = generate_scenario(scenario)
                pd.testing.assert_frame_equal(trace, generate_scenario(scenario, 42), check_exact=True)
                # Local RNG must be independent of other scenarios and global state.
                generate_scenario("recovery", 123)
                np.random.default_rng(999).normal(size=100)
                pd.testing.assert_frame_equal(trace, generate_scenario(scenario, 42), check_exact=True)
                self.assertEqual(trace.shape, (100, 11))
                self.assertEqual(trace.time.tolist(), list(range(100)))
                self.assertTrue(np.isfinite(trace.to_numpy()).all())
                self.assertFalse(trace.equals(generate_scenario(scenario, 43)))
                for prefix in ("wifi", "g5"):
                    for metric, (low, high) in bounds.items():
                        self.assertTrue(trace[f"{prefix}_{metric}"].between(low, high).all())

    def test_scenario_behavior_across_seeds(self):
        # Window means distinguish the scenario trend from individual noisy samples.
        for seed in (0, 1, 7, 42, 43, 123, 2026):
            for scenario in SCENARIOS:
                with self.subTest(seed=seed, scenario=scenario):
                    trace = generate_scenario(scenario, seed)
                    start = trace.iloc[:20].mean()
                    end = trace.iloc[-20:].mean()
                    for metric, tolerance in {"rssi": 3, "latency": 4, "loss": .2,
                                              "jitter": 2, "throughput": 5}.items():
                        self.assertLess(abs(end[f"g5_{metric}"] - start[f"g5_{metric}"]), tolerance)
                    if scenario == "leaving_wifi":
                        self.assertLess(end.wifi_rssi, start.wifi_rssi - 25)
                        self.assertGreater(end.wifi_latency, start.wifi_latency + 35)
                        self.assertGreater(end.wifi_loss, start.wifi_loss + 2)
                        self.assertGreater(end.wifi_jitter, start.wifi_jitter + 12)
                        self.assertLess(end.wifi_throughput, start.wifi_throughput - 35)
                        selected = apply_baseline(trace).selected_network
                        self.assertEqual(selected.iloc[0], "WiFi")
                        self.assertEqual(selected.iloc[-1], "5G")
                    elif scenario == "congested_wifi":
                        self.assertTrue((trace.wifi_rssi > -60).all())
                        self.assertLess(abs(end.wifi_rssi - start.wifi_rssi), 2)
                        self.assertGreater(end.wifi_latency, start.wifi_latency + 45)
                        self.assertGreater(end.wifi_loss, start.wifi_loss + 3)
                        self.assertGreater(end.wifi_jitter, start.wifi_jitter + 15)
                        self.assertLess(end.wifi_throughput, start.wifi_throughput - 35)
                        self.assertTrue((apply_baseline(trace).selected_network == "WiFi").all())
                    elif scenario == "large_download":
                        self.assertTrue((trace.wifi_rssi > trace.g5_rssi).all())
                        self.assertGreater((trace.wifi_latency < trace.g5_latency).mean(), .95)
                        self.assertGreater(trace.g5_throughput.mean(), 1.8 * trace.wifi_throughput.mean())
                        self.assertTrue((trace[["wifi_loss", "g5_loss"]] < 2).all().all())
                    else:
                        middle = trace.iloc[40:60].mean()
                        for edge in (start, end):
                            self.assertGreater(edge.wifi_rssi, middle.wifi_rssi + 20)
                            self.assertLess(edge.wifi_latency, middle.wifi_latency - 25)
                            self.assertLess(edge.wifi_loss, middle.wifi_loss - 2)
                            self.assertLess(edge.wifi_jitter, middle.wifi_jitter - 8)
                            self.assertGreater(edge.wifi_throughput, middle.wifi_throughput + 25)
                        selected = apply_baseline(trace).selected_network
                        self.assertEqual(selected.iloc[0], "WiFi")
                        self.assertEqual(selected.iloc[50], "5G")
                        self.assertEqual(selected.iloc[-1], "WiFi")

    def test_baseline_and_handovers(self):
        self.assertEqual(select_network(-50, -70), "WiFi")
        self.assertEqual(select_network(-80, -65), "5G")
        self.assertEqual(select_network(-65, -65), "WiFi")
        trace = pd.DataFrame({"wifi_rssi": [-50, -80, -80, -60], "g5_rssi": [-70] * 4})
        result = apply_baseline(trace)
        self.assertEqual(result.selected_network.tolist(), ["WiFi", "5G", "5G", "WiFi"])
        self.assertEqual(result.handover.tolist(), [False, True, False, True])
        self.assertEqual(list(trace.columns), ["wifi_rssi", "g5_rssi"])
        for scenario in SCENARIOS:
            source = generate_scenario(scenario)
            original = source.copy(deep=True)
            result = apply_baseline(source)
            pd.testing.assert_frame_equal(source, original, check_exact=True)
            pd.testing.assert_frame_equal(result[source.columns], source, check_exact=True)
            expected = np.where(source.wifi_rssi >= source.g5_rssi, "WiFi", "5G")
            np.testing.assert_array_equal(result.selected_network, expected)
            self.assertFalse(result.handover.iloc[0])
            self.assertEqual(int(result.handover.sum()), int(np.sum(expected[1:] != expected[:-1])))

    def test_unknown_scenario(self):
        with self.assertRaises(ValueError):
            generate_scenario("unknown")


if __name__ == "__main__":
    unittest.main()
