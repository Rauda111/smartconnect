"""Virtual-clock integration tests: no real waits, probes, DNS or HTTPS."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mac_hub.monitor import Measurement
from mac_hub.competition.run import live


class MovementPauseTests(unittest.TestCase):
    def run_mock(self, output, cancel_during_pause=False):
        clock = [0.]
        calls = {'measure': 0, 'request': 0}
        pauses = []
        def measure(interface, *_):
            calls['measure'] += 1
            # First window healthy; every later Wi-Fi window breaches RTT guardrail.
            window = (calls['measure']-1)//2+1
            return Measurement(interface, 'reachable', 20. if interface=='en0' and window==1 else 100. if interface=='en0' else 35., 0.)
        def request(interface, target, execute, cancel):
            calls['request'] += 1
            return dict(status='success', source='actual_https', requested_interface=interface,
                        binding_index=11 if interface=='en0' else 21,
                        bytes_received=target.max_bytes, request_duration_ms=100.)
        def wait(cancel, seconds):
            pauses.append((seconds, calls.copy()))
            clock[0] += seconds
            if seconds == 90 and cancel_during_pause:
                cancel.set()
                return True
            return False
        with patch('mac_hub.competition.run.time.monotonic', side_effect=lambda:clock[0]), patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure',side_effect=measure), patch('mac_hub.competition.run.request',side_effect=request), patch('mac_hub.competition.run.wait_for',side_effect=wait):
            live(output, cycles=8, movement_after=2, movement_pause=90)
        return calls, pauses

    def test_pause_preserves_state_without_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run';calls,pauses=self.run_mock(p)
            rows=[json.loads(x) for x in (p/'events.jsonl').read_text().splitlines()]
            done=[r for r in rows if r['event']=='completed_window']
            self.assertEqual(len(rows),16)
            self.assertEqual([r['window'] for r in done],list(range(1,9)))
            self.assertEqual(calls,{'measure':16,'request':8})
            self.assertEqual([x[0] for x in pauses],[5.,90,5.,5.,5.,5.,5.])
            self.assertEqual(pauses[1][1],{'measure':4,'request':2})
            self.assertEqual(done[2]['elapsed_seconds']-done[1]['elapsed_seconds'],90)
            # Dwell advances with real elapsed time, but pause does not qualify a window.
            self.assertEqual(done[1]['decision']['hold_count'],1)
            self.assertEqual(done[2]['decision']['hold_count'],2)
            self.assertEqual(done[2]['decision']['recommended'],'wifi')
            self.assertEqual(done[3]['decision']['recommended'],'cellular')
            self.assertEqual(done[2]['decision']['stability']['last_selection_elapsed'],0.)
            moves=[json.loads(x) for x in (p/'movement.jsonl').read_text().splitlines()]
            self.assertEqual([x['event'] for x in moves],['movement_pause_start','movement_pause_end'])
            self.assertEqual(moves[-1]['actual_duration_seconds'],90)
            m=json.loads((p/'manifest.json').read_text())
            self.assertEqual(m['completed_windows'],8)
            self.assertEqual(m['movement_after'],2)
            self.assertIn('movement.jsonl',m['output_hashes'])

    def test_cancel_during_movement_preserves_two_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run';calls,_=self.run_mock(p,True)
            self.assertEqual(calls,{'measure':4,'request':2})
            m=json.loads((p/'manifest.json').read_text())
            self.assertTrue(m['cancelled'])
            self.assertEqual(m['completed_windows'],2)
            moves=[json.loads(x) for x in (p/'movement.jsonl').read_text().splitlines()]
            self.assertTrue(moves[-1]['cancelled'])

    def test_invalid_movement_settings_do_not_create_output(self):
        for kw in [dict(movement_pause=90),dict(movement_after=0,movement_pause=90),
                   dict(movement_after=8,movement_pause=90),dict(movement_after=2),
                   dict(movement_after=2,movement_pause=float('nan')),
                   dict(movement_after=2,movement_pause=601)]:
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'run'
                with self.assertRaises(ValueError):live(p,cycles=8,**kw)
                self.assertFalse(p.exists())

if __name__=='__main__': unittest.main()
