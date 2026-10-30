"""Phase 2 invariants and independently hand-calculated metric checks."""
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from mac_hub.experiments.scenarios import generate, NAMES
from mac_hub.experiments.evaluate import replay, metrics, responses, validate, changes
from mac_hub.experiments.run import aggregate, paired, build


class ExperimentTests(unittest.TestCase):
    def test_seeded_scenarios(self):
        for name in NAMES:
            a,events=generate(name,7)
            b,_=generate(name,7)
            self.assertEqual(a,b)
            self.assertNotEqual(a,generate(name,8)[0])
            f=pd.DataFrame(a)
            validate(f)
            self.assertEqual(f.elapsed_seconds.tolist(),list(range(0,450,5)))
            self.assertEqual(set(f.source),{'synthetic'})
            self.assertFalse(any('throughput' in c or 'jitter' in c or 'rssi' in c for c in f))
            self.assertTrue(all(0 <= row['onset_seconds'] <= 445 for row in events))
        with self.assertRaises(ValueError):
            generate('bad')

    def test_fairness_causality_and_behavior(self):
        for name in NAMES:
            source=pd.DataFrame(generate(name)[0])
            original=source.copy(deep=True)
            for app in ('video_call','file_download'):
                result=replay(source,app)
                pd.testing.assert_frame_equal(source,original)
                pd.testing.assert_frame_equal(result[source.columns],source)
                pd.testing.assert_frame_equal(replay(source.iloc[:40],app),result.iloc[:40])
                expected=['wifi' if r.wifi_status=='reachable' else 'cellular' if r.cellular_status=='reachable' else 'none' for _,r in source.iterrows()]
                self.assertEqual(result.wifi_first.tolist(),expected)
                if name=='stable':
                    self.assertEqual(metrics(result,'smartconnect',app)['recommended_handovers'],0)
                if name in ('deteriorating_wifi','congested_wifi'):
                    self.assertEqual(result.iloc[-1].smartconnect,'cellular')
                if name in ('wifi_recovery','cellular_degradation'):
                    self.assertEqual(result.iloc[-1].smartconnect,'wifi')
                if name=='network_unavailability':
                    self.assertTrue(result.iloc[35:50].smartconnect.eq('none').all())

    def test_missing_and_invalid_inputs(self):
        f=pd.DataFrame(generate('stable')[0]).iloc[:3].copy()
        f.loc[:,'wifi_latency']=float('nan')
        result=replay(f,'video_call')
        self.assertTrue(result.wifi_first.eq('wifi').all())
        self.assertTrue(result.smartconnect.eq('cellular').all())
        self.assertEqual(metrics(result,'wifi_first','video_call')['latency_observed_windows'],0)
        self.assertEqual(metrics(result,'wifi_first','video_call')['guardrail_unknown_windows'],3)
        for column,value in [('elapsed_seconds',0),('timestamp','not a date'),('wifi_loss',101),('wifi_latency',float('inf')),('wifi_status','bad')]:
            bad=f.copy()
            bad[column]=value
            with self.subTest(column=column),self.assertRaises(ValueError):
                replay(bad,'video_call')

    def test_independent_metrics(self):
        f=pd.DataFrame(generate('stable')[0]).iloc[:6].copy()
        f['smartconnect']=['wifi','cellular','wifi','none','cellular','wifi']
        f['wifi_latency']=[10,20,30,40,50,60]
        f['cellular_latency']=100
        f['wifi_loss']=0
        f['cellular_loss']=4
        f['wifi_rtt_variation']=float('nan')
        f['cellular_rtt_variation']=8
        m=metrics(f,'smartconnect','video_call')
        self.assertEqual(m['recommended_handovers'],3)
        self.assertEqual(m['outage_entries'],1)
        self.assertEqual(m['reattachments'],1)
        self.assertEqual(m['no_path_windows'],1)
        self.assertEqual(m['latency_mean'],60) # (10+100+30+100+60)/5
        self.assertAlmostEqual(m['loss_mean'],1.6)
        self.assertEqual(m['rtt_variation_observed_windows'],2)
        self.assertEqual(m['rtt_variation_mean'],8)
        self.assertEqual(m['observed_guardrail_violation_windows'],2)
        self.assertEqual(m['guardrail_unknown_windows'],6)
        self.assertEqual(m['fully_assessed_guardrail_windows'],0)
        self.assertEqual(m['reversals_within_30s'],1)
        self.assertEqual(changes(['none','wifi','none','cellular']),[])

    def test_response_timing_and_censoring(self):
        f=pd.DataFrame(dict(elapsed_seconds=[0,7,19,40],smartconnect=['wifi','wifi','cellular','wifi']))
        events=[dict(onset_seconds=8,expected_path='cellular',event='degrade'),dict(onset_seconds=25,expected_path='none',event='outage')]
        r=responses(f,'smartconnect',events)
        self.assertEqual(r[0]['response_seconds'],11)
        self.assertIsNone(r[1]['response_seconds'])
        self.assertFalse(r[1]['observed_response'])
        r=responses(f,'smartconnect',[dict(onset_seconds=5,expected_path='wifi',event='recovery')])
        self.assertTrue(r[0]['already_on_target'])
        self.assertEqual(r[0]['response_seconds'],2)
        # Actual elapsed times govern dwell despite irregular window spacing.
        f=pd.DataFrame(generate('stable')[0]).iloc[:5].copy()
        f['wifi_latency']=50
        f['cellular_latency']=10
        f['elapsed_seconds']=[0,1,2,29,30]
        out=replay(f,'video_call')
        self.assertEqual(out.smartconnect.tolist(),['wifi']*4+['cellular'])

    def test_aggregation_pairing(self):
        rows=[]
        for seed,base,smart in [(0,10,6),(1,20,18)]:
            for method,v in [('wifi_first',base),('smartconnect',smart)]:
                rows.append(dict(scenario='stable',source='synthetic',seed=seed,application='video_call',method=method,
                                 **{k:v for k in ('latency_mean','loss_mean','rtt_variation_mean','recommended_handovers','observed_guardrail_violation_windows','no_path_windows','quiet_region_changes','reversals_within_30s')}))
        f=pd.DataFrame(rows)
        a=aggregate(f)
        r=a[(a.method=='wifi_first')&(a.metric=='latency_mean')].iloc[0]
        self.assertEqual(r['mean'],15)
        self.assertAlmostEqual(r.sample_sd,50**.5)
        self.assertEqual(paired(f).query("metric == 'latency_mean'").smartconnect_minus_wifi_first.tolist(),[-4,-2])

    def test_profile_guardrails_are_distinct(self):
        f=pd.DataFrame(generate('stable')[0]).iloc[:12].copy()
        f['wifi_latency']=90
        f['wifi_loss']=4
        f['cellular_latency']=40
        f['cellular_loss']=2.5
        self.assertTrue(replay(f,'video_call').smartconnect.eq('none').all())
        self.assertTrue(replay(f,'file_download').smartconnect.eq('cellular').all())

    def test_artifacts_reproducibility_audit_and_dashboard(self):
        from unittest.mock import patch
        from mac_hub.experiments.audit import audit
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.experiments.visuals.plots'):
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            build(a,[0],include_smoke=True)
            build(b,[0],include_smoke=True)
            for path in a.glob('*.csv'):
                self.assertEqual(path.read_bytes(),(b/path.name).read_bytes())
            self.assertEqual(audit(a),28)
            self.assertTrue(pd.read_csv(a/'per_run.csv').query("source == 'measured_icmp'").windows.eq(1).all())
            with self.assertRaises(FileExistsError):
                build(a,[0])
            app=AppTest.from_file(str(Path('mac_hub/dashboard.py').resolve())).run(timeout=30)
            # The live path remains the first input; experiment directory is second.
            next(e for e in app.text_input if e.label == 'Experiment results directory').set_value(str(a)).run(timeout=30)
            self.assertFalse(list(app.exception))
            self.assertTrue(any('Phase 2 experiments' == tab.label for tab in app.tabs))
            app.selectbox[0].select('measured_0_live_smoke_20261030').run(timeout=30)
            self.assertFalse(list(app.exception))
            (a/'per_run.csv').write_text('tampered')
            with self.assertRaises(ValueError):
                audit(a)

    def test_alternating_candidate_does_not_satisfy_hold(self):
        f=pd.DataFrame(generate('stable')[0]).iloc[:18].copy()
        f['wifi_latency']=40
        f['wifi_loss']=0
        f['cellular_loss']=0
        f['cellular_latency']=[10 if i%2 else 80 for i in range(len(f))]
        self.assertTrue(replay(f,'video_call').smartconnect.eq('wifi').all())

    def test_independent_audit_rejects_rehashed_wrong_statistics(self):
        import hashlib
        import json
        from unittest.mock import patch
        from mac_hub.experiments.audit import audit
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.experiments.visuals.plots'):
            folder=Path(tmp)/'evidence'
            build(folder,[0],include_smoke=True)
            self.assertEqual(audit(folder),28)
            cases=[('per_run.csv','latency_mean',float('nan')),
                   ('aggregate.csv','mean',999),
                   ('paired_differences.csv','smartconnect_minus_wifi_first',999),
                   ('paired_summary.csv','n',999),
                   ('event_responses.csv','response_seconds',999),
                   ('response_summary.csv','mean_response_seconds',999)]
            for filename,column,value in cases:
                path=folder/filename
                original=path.read_bytes()
                manifest_path=folder/'manifest.json'
                original_manifest=manifest_path.read_bytes()
                with self.subTest(filename=filename):
                    frame=pd.read_csv(path)
                    frame.loc[0,column]=value
                    frame.to_csv(path,index=False)
                    manifest=json.loads(original_manifest)
                    manifest['output_sha256'][filename]=hashlib.sha256(path.read_bytes()).hexdigest()
                    manifest_path.write_text(json.dumps(manifest))
                    with self.assertRaises((ValueError,AssertionError)):
                        audit(folder)
                path.write_bytes(original)
                manifest_path.write_bytes(original_manifest)
            path=folder/'REPORT.md'
            path.write_text(path.read_text().replace('Six synthetic scenarios','Five synthetic scenarios'))
            manifest=json.loads((folder/'manifest.json').read_text())
            manifest['output_sha256']['REPORT.md']=hashlib.sha256(path.read_bytes()).hexdigest()
            (folder/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                audit(folder)

    def test_missingness_and_profile_scores(self):
        import math
        from mac_hub.engine import Engine
        from mac_hub.monitor import Measurement
        from mac_hub.experiments.independent import same, moments
        measurements={'wifi':Measurement('en0','reachable',25,1),
                      'cellular':Measurement('en6','reachable',40,0)}
        video=Engine('video_call').step(measurements,0)
        download=Engine('file_download').step(measurements,0)
        for path in ('wifi','cellular'):
            self.assertAlmostEqual(video['details'][path]['score'],download['details'][path]['score'])
        self.assertAlmostEqual(video['coverage'],.6)
        self.assertAlmostEqual(download['coverage'],.3)
        self.assertFalse(same('0',None))
        self.assertFalse(same('',0))
        self.assertIsNone(moments([None])['mean'])
        self.assertIsNone(moments([2])['sample_sd'])
        f=replay(pd.DataFrame(generate('stable')[0]).iloc[:3],'video_call')
        f['wifi_rtt_variation']=float('nan')
        result=metrics(f,'wifi_first','video_call')
        self.assertTrue(math.isnan(result['rtt_variation_mean']))
        self.assertEqual(result['rtt_variation_observed_windows'],0)

    def test_event_interval_boundary_and_cellular_hold(self):
        f=pd.DataFrame(dict(elapsed_seconds=[0,5,10,15],smartconnect=['wifi','wifi','cellular','wifi']))
        events=[dict(onset_seconds=5,expected_path='cellular',event='first'),
                dict(onset_seconds=10,expected_path='wifi',event='second')]
        values=responses(f,'smartconnect',events)
        self.assertIsNone(values[0]['response_seconds']) # target arrives at next event: excluded
        self.assertEqual(values[1]['response_seconds'],5)
        for seed in range(10):
            for app in ('video_call','file_download'):
                f=replay(pd.DataFrame(generate('cellular_degradation',seed)[0]),app)
                self.assertEqual(f.loc[f.elapsed_seconds.isin([100,105]),'smartconnect'].tolist(),['cellular','cellular'])
                self.assertEqual(f.loc[f.elapsed_seconds==110,'smartconnect'].item(),'wifi')
                self.assertEqual(f.iloc[changes(f.smartconnect)].elapsed_seconds.tolist(),[30.,110.])
                self.assertEqual(metrics(f,'smartconnect',app)['observed_guardrail_violation_windows'],2)
