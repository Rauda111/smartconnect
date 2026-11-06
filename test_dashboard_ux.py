"""Offline UX contracts: native controls, clocked replay, privacy and log states."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from mac_hub.competition import dashboard_ui as ui
from mac_hub.competition.dashboard_data import recorded
from mac_hub.competition.run import replay_rows

APP = str(Path(__file__).parent/'mac_hub/competition/dashboard.py')


def start():
    return AppTest.from_file(APP).run(timeout=30)


class ReplayStateTests(unittest.TestCase):
    def test_due_time_pause_speed_restart_and_finish(self):
        for speed, seconds in ui.SPEEDS.items():
            state=dict(window=1,speed=speed,technical=False)
            ui.play_pause(state,8,now=10)
            ui.tick(state,8,now=10+seconds-.01)
            self.assertEqual(state['window'],1)
            ui.tick(state,8,now=10+seconds)
            self.assertEqual(state['window'],2)
            ui.tick(state,8,now=10+seconds)
            self.assertEqual(state['window'],2) # extra render does not consume a frame
            ui.pause(state);ui.tick(state,8,now=100)
            self.assertEqual(state['window'],2)
            ui.choose(state,7);ui.play_pause(state,8,now=100)
            ui.tick(state,8,now=100+seconds)
            self.assertEqual(state['window'],8)
            self.assertFalse(state['playing'])
            ui.play_pause(state,8,now=200)
            self.assertFalse(state['playing'])
            ui.reset(state)
            self.assertEqual(state['window'],1)

    def test_technical_inspection_locks_replay(self):
        state=dict(window=3,speed='Normal · 2 seconds',playing=True,next_due=1)
        ui.inspect_details(state,True)
        ui.tick(state,8,now=100)
        ui.play_pause(state,8,now=100)
        self.assertEqual(state['window'],3)
        self.assertFalse(state['playing'])
        ui.back(state)
        self.assertFalse(state['technical'])
        self.assertFalse(state['playing'])


class UIContracts(unittest.TestCase):
    def setUp(self):
        self.patches=[patch('socket.getaddrinfo',side_effect=AssertionError('No DNS')),
                      patch('mac_hub.competition.run.request',side_effect=AssertionError('No HTTPS')),
                      patch('mac_hub.competition.run.measure',side_effect=AssertionError('No probes'))]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in self.patches])

    def test_previous_next_each_timeline_window_and_boundaries(self):
        app=start()
        self.assertTrue(app.button(key='previous').disabled)
        for window in range(1,9):
            app.button(key='timeline_'+str(window)).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['window'],window)
            self.assertFalse(app.session_state['playing'])
            self.assertEqual(app.button(key='timeline_'+str(window)).proto.type,'primary')
        self.assertTrue(app.button(key='next').disabled)
        self.assertTrue(app.button(key='play_pause').disabled)
        self.assertTrue(any('Finished' in x.value for x in app.caption))
        app.button(key='previous').click().run()
        self.assertEqual(app.session_state['window'],7)
        app.button(key='restart').click().run()
        self.assertEqual(app.session_state['window'],1)
        self.assertTrue(app.button(key='restart').disabled)
        app.button(key='next').click().run()
        self.assertEqual(app.session_state['window'],2)

    def test_play_pause_speed_manual_selection_and_details(self):
        with patch.object(ui,'monotonic',return_value=0) as clock:
            app=start()
            app.button(key='play_pause').click().run()
            self.assertTrue(app.session_state['playing'])
            clock.return_value=1.9;app.run()
            self.assertEqual(app.session_state['window'],1)
            clock.return_value=2;app.run()
            self.assertEqual(app.session_state['window'],2)
            app.button(key='play_pause').click().run()
            self.assertFalse(app.session_state['playing'])
            app.selectbox(key='speed').set_value('Fast · 1 second').run()
            app.button(key='play_pause').click().run()
            clock.return_value=3;app.run()
            self.assertEqual(app.session_state['window'],3)
            app.button(key='timeline_7').click().run()
            self.assertFalse(app.session_state['playing'])
            self.assertEqual(app.session_state['window'],7)
            app.button(key='play_pause').click().run()
            app.toggle(key='technical').set_value(True).run()
            self.assertFalse(app.session_state['playing'])
            self.assertTrue(app.button(key='play_pause').disabled)
            clock.return_value=99;app.run()
            self.assertEqual(app.session_state['window'],7)
            self.assertTrue(all(not e.proto.expanded for e in app.expander))
            app.button(key='back_overview').click().run()
            self.assertFalse(app.toggle(key='technical').value)
            self.assertFalse(app.session_state['playing'])
            self.assertEqual(len(app.dataframe),0)

    def test_explanations_guided_tour_and_mode_changes(self):
        app=start()
        app.button(key='explain_terms').click().run()
        self.assertTrue(app.toggle(key='technical').value)
        for term in ui.TERMS:
            app.selectbox(key='term').set_value(term).run()
            self.assertTrue(any(ui.TERMS[term][0] in x.value for x in app.markdown))
        app.button(key='back_overview').click().run()
        app.toggle(key='guided').set_value(True).run()
        for stage in ('Monitor','Decide','Act','Verify'):
            app.radio(key='tour_stage').set_value(stage).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.session_state['playing'])
        app.radio(key='mode').set_value('Historical policy replay').run()
        self.assertEqual(app.slider[0].max,18)
        app.slider[0].set_value(18).run()
        self.assertTrue(any('No HTTPS outcomes' in x.value for x in app.info))
        app.selectbox(key='profile').set_value('file_download').run()
        self.assertEqual(app.session_state['window'],1)
        app.radio(key='mode').set_value('Live monitoring').run()
        self.assertTrue(any('No active experiment — choose an existing approved collector log to view measurements.'==x.value for x in app.info))
        self.assertEqual(len(app.metric),0)
        app.button(key='open_recorded').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio(key='mode').value,'Recorded real experiment')
        self.assertEqual(app.session_state['window'],1)

    def test_changing_speed_or_mode_pauses_without_skipping(self):
        with patch.object(ui, 'monotonic', return_value=0):
            app=start()
            for speed in ui.SPEEDS:
                app.button(key='play_pause').click().run()
                app.selectbox(key='speed').set_value(speed).run()
                self.assertFalse(app.session_state['playing'])
                self.assertEqual(app.session_state['window'],1)
            app.button(key='play_pause').click().run()
            app.radio(key='mode').set_value('Historical policy replay').run()
            self.assertFalse(app.session_state['playing'])
            self.assertEqual(app.session_state['window'],1)
            self.assertFalse(app.exception)

    def test_missing_corrupt_recording_is_friendly(self):
        with patch('mac_hub.competition.dashboard_data.recorded',side_effect=FileNotFoundError('PRIVATE')):
            app=start()
            self.assertFalse(app.exception)
            self.assertTrue(any('Evidence unavailable or corrupt' in x.value for x in app.error))
            self.assertNotIn('PRIVATE',' '.join(x.value for x in app.error))

    def test_live_selection_refresh_and_no_private_path_in_public_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private-events.jsonl'
            app=start()
            app.radio(key='mode').set_value('Live monitoring').run()
            app.selectbox(key='log_choice').set_value('Enter an existing log path privately').run()
            app.text_input(key='private_log').set_value(str(path)).run()
            self.assertTrue(any('Missing file' in x.value for x in app.warning))
            self.assertEqual(app.text_input(key='private_log').proto.type,1)
            raw=list(replay_rows())[:2]
            now=datetime.now(timezone.utc)
            for r in raw:r.update(mode='live',event='completed_window',timestamp=now.isoformat())
            path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
            app.button(key='refresh_log').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['window'],2)
            self.assertTrue(app.button(key='play_pause').disabled)
            app.button(key='previous').click().run()
            raw.append(dict(raw[-1],window=3))
            path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
            app.button(key='refresh_log').click().run()
            self.assertEqual(app.session_state['window'],1) # inspection never jumps to newest
            public=' '.join(x.value for kind in [app.markdown,app.caption,app.error,app.warning,app.info] for x in kind)
            self.assertNotIn(folder,public)
            path.write_text('{broken\n')
            app.button(key='refresh_log').click().run()
            self.assertTrue(any('Corrupt evidence' in x.value for x in app.error))


class LiveCategories(unittest.TestCase):
    def test_empty_partial_corrupt_stale_and_completed(self):
        self.assertIn('No active experiment',ui.load_live(None)['notices'][0][1])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events.jsonl'
            self.assertIn('Missing file',ui.load_live(path)['notices'][0][1])
            for text in ('','{"unfinished":'):
                path.write_text(text)
                result=ui.load_live(path)
                self.assertEqual(result['rows'],[])
                self.assertTrue(any('Incomplete run' in m for _,m in result['notices']))
            for text in ('bad\n','[]\n'):
                path.write_text(text)
                self.assertIn('Corrupt evidence',ui.load_live(path)['notices'][0][1])
            r=list(replay_rows())[0];now=datetime.now(timezone.utc)
            r.update(mode='live',event='completed_window',timestamp=now.isoformat())
            path.write_text(json.dumps(r)+'\n')
            self.assertFalse(any('Stale data' in m for _,m in ui.load_live(path,now=now)['notices']))
            self.assertTrue(any('Stale data' in m for _,m in ui.load_live(path,now=now+timedelta(seconds=46))['notices']))
            manifest=path.with_name('manifest.json')
            manifest.write_text(json.dumps(dict(output_hashes={},run_error_type='PRIVATE')))
            result=ui.load_live(path,now=now)
            self.assertTrue(any('Finished run' in m for _,m in result['notices']))
            self.assertTrue(any('Collector stopped' in m for _,m in result['notices']))
            manifest.write_text(json.dumps(dict(output_hashes={'../PRIVATE':'bad'})))
            self.assertIn('Corrupt evidence',ui.load_live(path)['notices'][0][1])
            for invalid in (None, [], {'output_hashes':None}):
                manifest.write_text(json.dumps(invalid))
                self.assertIn('Corrupt evidence',ui.load_live(path)['notices'][0][1])

    def test_known_location_only_and_observation_health(self):
        with patch.object(ui.DEFAULT_LOG.__class__,'is_file',return_value=True):
            self.assertEqual(ui.known_logs(),[ui.DEFAULT_LOG])
        rows,_=recorded()
        self.assertEqual(ui.path_health(rows[0],'wifi')[1],'healthy')
        self.assertEqual(ui.path_health(rows[5],'wifi')[1],'degraded')
        self.assertEqual(ui.path_health(rows[6],'wifi')[1],'unavailable')
        self.assertEqual(ui.path_health(dict(rows[0],wifi_latency=None),'wifi')[1],'unknown')

if __name__=='__main__':unittest.main()
