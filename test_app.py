"""Regression coverage for the Streamlit handover-event display."""

from pathlib import Path
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


class HandoverDisplayTests(unittest.TestCase):
    def test_compare_both_handover_tables(self):
        for scenario, counts in (("leaving_wifi", (3, 1)), ("recovery", (4, 2))):
            with self.subTest(scenario=scenario):
                app = AppTest.from_file(str(Path(__file__).with_name("app.py")))
                app.run(timeout=30)
                app.sidebar.selectbox[0].select(scenario)
                app.sidebar.selectbox[1].select("video_call")
                app.sidebar.selectbox[2].select("compare")
                app.sidebar.number_input[0].set_value(42)
                app.sidebar.button[0].click().run(timeout=30)
                self.assertEqual(list(app.exception), [])
                tables = app.tabs[3].dataframe
                self.assertEqual(len(tables), 2)
                state = app.session_state["run_state_v2"]
                for i, method in enumerate(("baseline", "smart")):
                    result = state[method]
                    events = result.loc[result.handover]
                    expected = events[["time", "selected_network"]].copy()
                    # Shift the complete timeline, not the filtered event rows.
                    expected.insert(1, "previous_network",
                                    result.selected_network.shift().loc[events.index])
                    if method == "smart":
                        for column in ("decision_strength", "candidate_advantage",
                                       "hold_count", "decision_explanation"):
                            expected[column] = events[column]
                        expected["candidate_advantage"] = expected.candidate_advantage.round(3)
                    self.assertEqual(len(tables[i].value), counts[i])
                    pd.testing.assert_frame_equal(tables[i].value, expected)
                # Display reconstruction must not add columns to baseline results.
                self.assertNotIn("previous_network", state["baseline"].columns)

    def test_baseline_without_handovers(self):
        app = AppTest.from_file(str(Path(__file__).with_name("app.py")))
        app.run(timeout=30)
        app.sidebar.selectbox[0].select("congested_wifi")
        app.sidebar.selectbox[2].select("baseline")
        app.sidebar.number_input[0].set_value(42)
        app.sidebar.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.tabs[3].dataframe), 0)
        self.assertTrue(any("No RSSI-baseline handovers occurred." in item.value
                            for item in app.tabs[3].markdown))


if __name__ == "__main__":
    unittest.main()
