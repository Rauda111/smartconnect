"""Approval-gated Mac ICMP collector using the persistent Prototype 1 policy.

Import never starts probes, HTTP, listeners, or credential prompts. Each upload
is attempted once; after a transient outage only newer observations are sent.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import getpass
import json
import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from mac_hub.competition.run import Session
from mac_hub.monitor import Measurement, measure
from experiments.webrtc_continuity.policy_channel import MAX_AGE


class BridgeError(Exception):
    """Public messages must be fixed categories, never underlying exceptions."""


class TransientBridgeError(BridgeError):
    """A bounded retry may recover transport, but must never replay an upload."""


def server_origin(value, *, allow_loopback=False):
    try:
        parts = urlsplit(value)
        port = parts.port
    except (ValueError, TypeError):
        raise BridgeError('Use an explicit HTTPS Render service origin') from None
    if (parts.username or parts.password or parts.path not in ('', '/') or
            parts.query or parts.fragment):
        raise BridgeError('Use an explicit HTTPS Render service origin')
    if (allow_loopback and parts.scheme == 'http' and parts.hostname == '127.0.0.1' and
            port is not None and 1024 <= port <= 65535):
        return f'http://127.0.0.1:{port}'
    if (parts.scheme != 'https' or port is not None or not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com', parts.hostname or '')):
        raise BridgeError('Use an explicit HTTPS Render service origin')
    return 'https://' + parts.hostname


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Writer:
    def __init__(self, server, token, *, allow_loopback=False):
        self.origin = server_origin(server, allow_loopback=allow_loopback)
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,256}', token):
            raise BridgeError('Writer credential missing or invalid')
        self.token = token
        # Avoid inherited proxies and never forward the credential on a redirect.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def __call__(self, path, payload=None, *, timeout=10.):
        if path not in ('/policy/session', '/policy') or not 0 < timeout <= 10:
            raise BridgeError('Invalid writer operation')
        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            req = Request(self.origin + path, data=body, headers={
                'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
                method='GET' if body is None else 'POST')
            with self.opener.open(req, timeout=timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError()
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except HTTPError as exc:
            if exc.code in (408, 429, 500, 502, 503, 504):
                raise TransientBridgeError('Policy transport temporarily unavailable') from None
            raise BridgeError('Policy service unauthorized or request rejected') from None
        except (URLError, TimeoutError, ConnectionError):
            raise TransientBridgeError('Policy transport temporarily unavailable') from None
        except Exception:
            raise BridgeError('Policy service response rejected') from None


def active_session(send, *, initial=False):
    result = send('/policy/session')
    if not isinstance(result, dict):
        raise BridgeError('Invalid active-session response')
    session = result.get('session_id')
    if (result.get('application') != 'video_call' or result.get('status') != 'active' or
            not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session)):
        raise BridgeError('No active approved Mac call session')
    window = result.get('policy_window')
    if type(window) is not int or not 0 <= window <= 10000:
        raise BridgeError('Invalid active-session policy sequence')
    expires = finite(result.get('expires_in_seconds'))
    if expires is None or not 0 < expires <= 360:
        raise BridgeError('Active call session expired or lease missing')
    if initial and window != 0:
        raise BridgeError('Policy already started; explicitly start a new call before restarting the collector')
    absolute = finite(result.get('absolute_expires_in_seconds', expires))
    if absolute is None or not 0 < absolute <= 360 or absolute + 1 < expires:
        raise BridgeError('Invalid absolute call lease')
    return dict(session_id=session, policy_window=window, expires_in_seconds=min(expires,absolute),
                absolute_expires_in_seconds=absolute)


def finite(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def record(session_id, window, stamp, measurements, decision):
    explanation = decision['explanation']
    reason = ('no_eligible_path' if decision['recommended'] == 'none' else
              'availability' if explanation.startswith('Availability reset:') else
              'qualified_change' if explanation.startswith('Recommend change:') else 'hold')
    clean = {}
    for name in ('wifi', 'cellular'):
        m, detail = measurements[name], decision['details'][name]
        clean[name] = dict(status=m.status if m.status in ('reachable', 'no_reply') else 'error',
                           latency_ms=finite(m.latency), loss_percent=finite(m.loss),
                           sent=m.sent, received=m.received, score=finite(detail['score']),
                           adjusted_score=finite(detail['adjusted_score']), trend=detail['trend'])
    stability = decision['stability']
    return dict(session_id=session_id, window=window, timestamp=stamp,
                application='video_call', source='measured_icmp',
                recommended=decision['recommended'], reason_code=reason,
                explanation=explanation,
                measurements=clean, stability={k: stability[k] for k in
                    ('hold_count', 'hold_required', 'dwell_seconds', 'margin')},
                coverage=decision['coverage'])


class Journal:
    """Optional exclusive-create JSONL: no credentials, addresses, raw probes or call ID."""
    def __init__(self, path):
        self.stream = None
        if path is not None:
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                self.stream = os.fdopen(fd, 'w', encoding='utf-8')
            except (OSError, TypeError, ValueError):
                raise BridgeError('Journal must be a fresh file in an existing directory') from None

    def write(self, event, **fields):
        if self.stream is not None:
            self.stream.write(json.dumps(dict(event=event, **fields), allow_nan=False) + '\n')
            self.stream.flush()

    def close(self):
        if self.stream is not None:
            self.stream.close()


def run(*, execute=False, send=None, cycles=6, count=10, pause=5.,
        duration=300., retries=3, output=None, cellular='en6', probe=measure,
        clock=time.monotonic, sleep=time.sleep,
        utc=lambda: datetime.now(timezone.utc).isoformat(), emit=print):
    # Gate before a journal, active-session GET, prompt, or probe worker exists.
    if not execute:
        raise BridgeError('Explicit --execute approval is required')
    if (type(cycles) is not int or not 1 <= cycles <= 30 or
            type(count) is not int or not 2 <= count <= 30 or
            finite(pause) is None or not 1 <= pause <= 30 or
            finite(duration) is None or not 1 <= duration <= 300 or
            type(retries) is not int or not 0 <= retries <= 3 or
            not isinstance(cellular, str) or not re.fullmatch(r'en\d+', cellular) or
            cellular == 'en0' or send is None):
        raise BridgeError('Invalid bounded collector settings')
    origin = clock()
    approval_deadline = origin + duration
    session_deadline = approval_deadline
    journal = Journal(output)
    policy = Session('video_call')
    session_id = None
    confirmed_window = attempted_window = 0
    previous_stamp = None
    accepted = discarded = 0

    def remaining():
        left = min(approval_deadline, session_deadline) - clock()
        if left <= 0:
            raise BridgeError('Approval duration or call session expired; collector stopped')
        return left

    def request(path, payload=None, *, observed_start=None):
        timeout = min(10., remaining())
        if observed_start is not None:
            freshness = MAX_AGE - (clock() - observed_start)
            if freshness <= 0:
                raise BridgeError('Observation expired before upload; collector stopped')
            timeout = min(timeout, freshness)
        if isinstance(send, Writer):
            return send(path, payload, timeout=timeout)
        return send(path, payload)

    def wait(seconds):
        if remaining() <= seconds:
            raise BridgeError('Approval duration or call session expired; collector stopped')
        sleep(seconds)

    def authorize(*, initial=False):
        nonlocal session_id, session_deadline, confirmed_window
        for attempt in range(retries + 1):
            requested_at = clock()
            try:
                info = active_session(request, initial=initial)
                break
            except TransientBridgeError:
                if attempt == retries:
                    raise BridgeError('Policy service unavailable after bounded retries') from None
                journal.write('transport_retry', operation='session', attempt=attempt + 1)
                emit('Policy transport unavailable; retrying session authorization within approved limits')
                wait(2 ** attempt)
        if session_id is not None and info['session_id'] != session_id:
            raise BridgeError('Call session changed; collector stopped')
        if not confirmed_window <= info['policy_window'] <= attempted_window:
            raise BridgeError('Policy sequence changed outside this collector; collector stopped')
        session_id = info['session_id']
        # Request start is conservative: response transit cannot extend the lease.
        session_deadline = min(approval_deadline, requested_at + info['expires_in_seconds'])
        remaining()
        confirmed_window = info['policy_window']
        return confirmed_window

    try:
        journal.write('collector_started', application='video_call', source='measured_icmp',
                      cycles=cycles, count=count, duration_seconds=duration,
                      physical_interface='unverified')
        for window in range(1, cycles + 1):
            authorize(initial=window == 1)
            # monitor.measure has a count+6 subprocess timeout. Never launch an
            # ICMP window that could knowingly run past either approved deadline.
            if remaining() <= count + 6:
                raise BridgeError('Insufficient approved time for another measurement window')
            started = clock()
            observed_at = utc()  # Freshness reflects the oldest observation, before probes.
            try:
                stamp = datetime.fromisoformat(observed_at)
                if stamp.tzinfo is None or (previous_stamp is not None and stamp <= previous_stamp):
                    raise ValueError()
            except (TypeError, ValueError):
                raise BridgeError('Measurement clock invalid or did not advance; collector stopped') from None
            previous_stamp = stamp

            def collect(interface):
                # Recheck at worker start too; no queued probe starts after expiry.
                if min(approval_deadline, session_deadline) - clock() <= count + 6:
                    raise BridgeError('Insufficient approved time for another measurement window')
                try:
                    return probe(interface, '1.1.1.1', count)
                except Exception:
                    return Measurement(interface)  # Never copy raw exceptions into output.

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {n: pool.submit(collect, interface) for n, interface in
                           (('wifi', 'en0'), ('cellular', cellular))}
                measurements = {n: f.result() for n, f in futures.items()}
            authorize()  # Recheck session after probes, including brief control-plane outages.
            age = clock() - started
            if age >= MAX_AGE:
                discarded += 1
                journal.write('observation_discarded', window=window, cause='stale_window')
                emit(f'Window {window}: discarded stale measurements; no policy upload')
            else:
                decision = policy.decide(measurements, {n: {'status': 'not_measured'}
                                                       for n in measurements}, clock() - origin)
                payload = record(session_id, window, observed_at, measurements, decision)
                journal.write('decision', **{k: v for k, v in payload.items() if k != 'session_id'},
                              recommendation_change=decision['recommendation_change'],
                              physical_interface='unverified')
                attempted_window = window
                try:
                    response = request('/policy', payload, observed_start=started)
                except TransientBridgeError:
                    # The server may have committed before a response was lost.
                    # Reconcile the sequence, never send this window a second time.
                    journal.write('upload_uncertain', window=window, cause='transport_unavailable')
                    confirmed = authorize()
                    if confirmed == window:
                        accepted += 1
                        journal.write('upload_confirmed', window=window, cause='sequence_reconciled')
                    else:
                        discarded += 1
                        journal.write('observation_discarded', window=window, cause='upload_unconfirmed')
                    emit(f'Window {window}: transport interrupted; sequence reconciled; no replay')
                else:
                    if not isinstance(response, dict) or response.get('status') != 'accepted':
                        raise BridgeError('Policy observation rejected; collector stopped')
                    confirmed_window = window
                    accepted += 1
                    journal.write('upload_confirmed', window=window, cause='accepted')
                    emit(f"Window {window}: {payload['recommended']}; {payload['reason_code']}; media path unverified")
            if window < cycles:
                wait(pause)
        journal.write('collector_completed', accepted_windows=accepted, discarded_windows=discarded)
        return dict(accepted_windows=accepted, discarded_windows=discarded)
    except BaseException:
        journal.write('collector_stopped', cause='operator_stop_or_bounded_failure')
        raise
    finally:
        journal.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='Approve bounded ICMP and authenticated policy HTTP(S) traffic')
    p.add_argument('--server', required=True, help='Explicit https://SERVICE.onrender.com origin')
    p.add_argument('--allow-loopback', action='store_true', help='Allow local http://127.0.0.1:PORT only')
    p.add_argument('--prompt-token', action='store_true', help='Read writer credential with a hidden prompt instead of the environment')
    p.add_argument('--cycles', type=int, default=6)
    p.add_argument('--count', type=int, default=10)
    p.add_argument('--pause', type=float, default=5.)
    p.add_argument('--duration', type=float, default=300., help='Approved runtime ceiling in seconds, 1..300')
    p.add_argument('--retries', type=int, default=3, help='Session transport retries, 0..3; uploads are never replayed')
    p.add_argument('--output', help='Optional fresh sanitized JSONL journal file; never overwritten')
    p.add_argument('--cellular', default='en6', help='Confirmed iPhone USB enN interface')
    a = p.parse_args(argv)
    try:
        if not a.execute:
            raise BridgeError('Explicit --execute approval is required')
        token = getpass.getpass('Policy writer token (hidden): ') if a.prompt_token else os.environ.get('SMARTCONNECT_POLICY_TOKEN')
        writer = Writer(a.server, token, allow_loopback=a.allow_loopback)
        run(execute=True, send=writer, cycles=a.cycles, count=a.count, pause=a.pause,
            cellular=a.cellular, duration=a.duration, retries=a.retries, output=a.output)
    except KeyboardInterrupt:
        print('Collector stopped by operator')
        return 130
    except Exception as exc:
        print(str(exc) if isinstance(exc, BridgeError) else 'Collector stopped: invalid settings or unavailable evidence')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
