import unittest
import numpy as np
import pandas as pd
from scenarios import generate_scenario
from config import SCENARIOS
from baseline import apply_baseline
from smartconnect import apply_smartconnect, classify_trend, WEIGHTS

class SmartConnectTests(unittest.TestCase):
    def test_design_contract(self):
        self.assertEqual(WEIGHTS['file_download'], dict(latency=.15, loss=.15, jitter=.10, throughput=.45, rssi=.15))
        self.assertEqual([classify_trend(x) for x in (.01,0,-.01)], ['Improving','Stable','Degrading'])
        for weights in WEIGHTS.values():
            self.assertAlmostEqual(sum(weights.values()),1)

    def test_reproducibility_causality_and_rules(self):
        for seed in (0,1,7,42,43,123,2026):
            for scenario in SCENARIOS:
                for app in WEIGHTS:
                    with self.subTest(seed=seed,scenario=scenario,application=app):
                        source=generate_scenario(scenario,seed)
                        original=source.copy(deep=True)
                        result=apply_smartconnect(source,app)
                        pd.testing.assert_frame_equal(source,original)
                        pd.testing.assert_frame_equal(result[source.columns],apply_baseline(source)[source.columns])
                        pd.testing.assert_frame_equal(result,apply_smartconnect(source,app))
                        pd.testing.assert_frame_equal(result.iloc[:50],apply_smartconnect(source.iloc[:50],app))
                        self.assertTrue(result.decision_strength.isin(['Low','Medium','High']).all())
                        for prefix in ('wifi','g5'):
                            self.assertTrue(result[f'{prefix}_trend'].isin(['Improving','Stable','Degrading']).all())
                            self.assertTrue(result[f'{prefix}_score'].between(0,1).all())
                        expected=result.selected_network.ne(result.selected_network.shift())
                        expected.iloc[0]=False
                        self.assertTrue(result.handover.equals(expected))
                        events=result[result.handover]
                        self.assertTrue((events.hold_count>=3).all())
                        self.assertTrue((np.diff(np.flatnonzero(result.handover))>=8).all())
                        for _,event in events.iterrows():
                            chosen='wifi' if event.selected_network=='WiFi' else 'g5'
                            previous='wifi' if event.previous_network=='WiFi' else 'g5'
                            self.assertFalse(event[f'{chosen}_guardrail'])
                            self.assertTrue(event.candidate_advantage>=.05 or (event[f'{previous}_guardrail'] and event.candidate_advantage>0))

    def test_hold_and_guardrail(self):
        trace=generate_scenario('large_download',42)
        for prefix,values in [('wifi',dict(latency=50,loss=1,jitter=10,throughput=25,rssi=-60)),('g5',dict(latency=20,loss=.1,jitter=2,throughput=90,rssi=-65))]:
            for metric,value in values.items():
                trace[f'{prefix}_{metric}']=value
        self.assertEqual(apply_smartconnect(trace,'file_download').query('handover').time.tolist(),[2])
        trace['g5_loss']=4
        self.assertFalse(apply_smartconnect(trace,'file_download').handover.any())

    def test_cli_identical_traces(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import simulate
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(simulate,'ROOT',Path(directory)), patch.object(simulate,'save_plots',return_value=[]):
                baseline=simulate.run_simulation('congested_wifi',42,'baseline')
                smart=simulate.run_simulation('congested_wifi',42,'smartconnect','video_call')
                pd.testing.assert_frame_equal(baseline.iloc[:,:11],smart.iloc[:,:11])
                self.assertEqual(len(list((Path(directory)/'outputs').glob('*.csv'))),2)

if __name__=='__main__':
    unittest.main()
