"""Read-only dashboard session helpers. No collector or network operations."""
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from mac_hub.competition.dashboard_data import project, reason, request_table
from mac_hub.competition.run import digest

DEFAULT_LOG = Path('/tmp/smartconnect-approved-demo/events.jsonl')
SPEEDS = {'Slow · 5 seconds': 5.0, 'Normal · 2 seconds': 2.0, 'Fast · 1 second': 1.0}
TERMS = {
    'RTT': ('Response time: how long an ICMP echo takes to go out and come back. Lower usually means a quicker response.', 'ICMP round-trip time is not HTTPS completion time or video-call quality.'),
    'Packet loss': ('Missed replies: how many ICMP echo attempts received no reply. Lower is better for this observation.', 'ICMP loss can reflect filtering or reachability; it is not measured application loss.'),
    'Bounded goodput': ('Small-download speed: how quickly a fixed-size HTTPS object was delivered.', 'Delivered body bits divided by the entire fresh request time, including connection/TLS/server overhead. Not link capacity.'),
    'Network selection': ('The connection recommended for the application’s next new HTTPS request.', 'This does not move an existing session or change the system’s network routes.'),
    'Hysteresis': ('Avoiding flip-flops: a better-looking alternative normally has to stay better for three qualifying observations.', 'The existing policy also checks a score margin and observed guardrails. A failed selected path has an immediate availability exception.'),
    'Dwell': ('A normal minimum wait between selections, giving a connection time to settle.', 'The existing normal dwell is 30 seconds. The availability exception bypasses normal hold and dwell.'),
    'Calibration': ('A small test download on each connection before a File Download decision.', 'These requests are separate from the selected-outcome request. Both calibrations must be valid to use their goodput comparison.'),
    'Socket binding': ('Asking a new request to use a specific connection, then reading back that socket setting.', 'Readback confirms the socket option. It does not prove physical egress without packet evidence.'),
}


def pause(state):
    state['playing'] = False
    state['next_due'] = None


def reset(state):
    pause(state)
    state['window'] = 1
    state['technical'] = False
    state['show_terms'] = False
    state['source_id'] = None


def choose(state, window):
    pause(state)
    state['window'] = window


def play_pause(state, count, now=None):
    if state.get('technical') or state.get('window', 1) >= count:
        pause(state)
    elif state.get('playing'):
        pause(state)
    else:
        state['playing'] = True
        state['next_due'] = (monotonic() if now is None else now) + SPEEDS[state['speed']]


def tick(state, count, now=None):
    """Advance one frame only when due. Widget reruns never consume a frame."""
    if state.get('technical'):
        pause(state)
    if not state.get('playing'):
        return
    now = monotonic() if now is None else now
    if state.get('next_due') is None:
        state['next_due'] = now + SPEEDS[state['speed']]
    if now >= state['next_due']:
        state['window'] = min(count, state['window'] + 1)
        state['next_due'] = now + SPEEDS[state['speed']]
        if state['window'] == count:
            pause(state)


def inspect_details(state, terms=False):
    pause(state)
    state['technical'] = True
    state['show_terms'] = terms


def back(state):
    pause(state)
    state['technical'] = False
    state['show_terms'] = False


def read_events(path):
    """Accept only a trailing interrupted append; reject interior corruption."""
    text = Path(path).read_text()
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines)-1 and not text.endswith('\n'):
                continue
            raise ValueError('Invalid evidence')
        if not isinstance(row, dict):
            raise ValueError('Invalid record')
        rows.append(row)
    return rows


def known_logs():
    """Only the approved conventional location; never search private folders."""
    return [DEFAULT_LOG] if DEFAULT_LOG.is_file() else []


def load_live(path, now=None):
    """Return public status categories and allowlisted observations only."""
    result = dict(rows=[], requests=[], notices=[])
    if not path:
        result['notices'] = [('info', 'No active experiment — choose an existing approved collector log to view measurements.')]
        return result
    try:
        path = Path(path).expanduser()
        if not path.is_file():
            result['notices'] = [('warning', 'Missing file — the selected log is not available. Choose another approved log or return to the recorded demo.')]
            return result
        events = read_events(path)
        if any(e.get('mode') != 'live' or e.get('event') not in ('decision', 'completed_window') for e in events):
            raise ValueError('Invalid event')
        completed = [e for e in events if e.get('event') == 'completed_window']
        rows = [project(e) for e in completed]
        if any(r['window'] < 1 for r in rows) or any(a['window'] >= b['window'] for a, b in zip(rows, rows[1:])):
            raise ValueError('Invalid windows')
        for i, row in enumerate(rows):
            row['reason'] = reason(row, rows[i-1] if i else None)
        manifest_path = path.with_name('manifest.json')
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            for name, expected in manifest['output_hashes'].items():
                if Path(name).name != name or (path.parent/name).resolve().parent != path.parent.resolve() or digest(path.parent/name) != expected:
                    raise ValueError('Integrity mismatch')
            result['notices'].append(('warning', 'Finished run — the collector finished or was cancelled. These are saved measurements, not active collection.'))
            if manifest.get('run_error_type'):
                result['notices'].append(('error', 'Collector stopped with an error — partial measurements were retained.'))
        else:
            result['notices'].append(('info', 'Incomplete run — no completion manifest yet. The viewer cannot confirm whether the collector is active.'))
        if not rows:
            result['notices'].append(('info', 'Waiting for the first completed measurement. An empty or interrupted final record contains no completed window.'))
        else:
            timestamp = datetime.fromisoformat(completed[-1]['timestamp'])
            age = ((now or datetime.now(timezone.utc))-timestamp).total_seconds()
            if age > completed[-1].get('freshness_limit_seconds', 45) or age < -5:
                result['notices'].append(('error', 'Stale data — observations are old or the clock changed. Do not treat the displayed selection as current.'))
        request_path = path.with_name('requests.jsonl')
        if request_path.is_file():
            result['requests'] = request_table(read_events(request_path))
        result['rows'] = rows
        return result
    except Exception:
        # No paths, raw errors, identifiers, or exception strings cross the UI boundary.
        return dict(rows=[], requests=[], notices=[('error', 'Corrupt evidence — the log is unreadable, incomplete in the middle, or fails validation. Check it privately; no raw details are displayed.')])


def path_health(row, network):
    if row[network+'_status'] != 'reachable':
        return 'Unavailable', 'unavailable'
    if row[network+'_latency'] is None or row[network+'_loss'] is None:
        return 'Unknown metrics', 'unknown'
    if row[network+'_loss'] > 0 or row.get(network+'_breaches'):
        return 'Degraded observation', 'degraded'
    return 'Healthy observation', 'healthy'
