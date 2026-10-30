"""Apple ping probes bound to an interface; no fallback to default routing."""
from dataclasses import dataclass, asdict
import ipaddress
import os
import platform
import re
import statistics
import subprocess
import time


@dataclass
class Measurement:
    interface: str
    status: str = 'error'
    latency: float | None = None
    loss: float | None = None
    rtt_variation: float | None = None
    sent: int = 0
    received: int = 0
    adjacent_pairs: int = 0
    duration_seconds: float = 0
    error: str = ''
    raw_output: str = ''
    rssi: float | None = None
    jitter: float | None = None
    throughput: float | None = None

    def dict(self):
        return asdict(self)


def parse_ping(output, interface):
    m = Measurement(interface, raw_output=output)
    summary = re.search(r'(\d+) packets transmitted,\s*(\d+) (?:packets )?received', output)
    if not summary:
        m.error = 'No valid ping summary; measurement unavailable'
        return m
    m.sent, m.received = map(int, summary.groups())
    if m.sent <= 0 or not 0 <= m.received <= m.sent:
        m.error = 'Invalid ping counts'
        return m
    m.loss = 100 * (m.sent - m.received) / m.sent
    replies = {}
    for seq, rtt in re.findall(r'icmp_seq=(\d+).*?time=([\d.]+)\s*ms', output):
        value = float(rtt)
        if value >= 0:
            replies.setdefault(int(seq), value)
    # Do not bridge lost sequence numbers, or count duplicate replies twice.
    pairs = [abs(replies[s] - replies[s-1]) for s in sorted(replies) if s-1 in replies]
    m.adjacent_pairs = len(pairs)
    m.rtt_variation = statistics.mean(pairs) if pairs else None
    m.latency = statistics.mean(replies.values()) if replies else None
    m.status = 'reachable' if m.received and replies else 'no_reply' if not m.received else 'error'
    if m.status == 'error':
        m.error = 'Replies reported but RTT values could not be parsed'
    return m


def ping_command(interface, target, count):
    if not re.fullmatch(r'en\d+', interface):
        raise ValueError('Use a macOS enN interface')
    ipaddress.IPv4Address(target)
    if not 2 <= count <= 300:
        raise ValueError('count must be 2..300')
    return ['/sbin/ping', '-n', '-b', interface, '-c', str(count), '-i', '1', '-W', '1000', '-t', str(count+3), target]


def measure(interface, target='1.1.1.1', count=10):
    command = ping_command(interface, target, count)
    start = time.monotonic()
    try:
        if platform.system() != 'Darwin':
            raise OSError('Live monitor requires macOS')
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=count+6, env={**os.environ, 'LC_ALL': 'C'})
        m = parse_ping(result.stdout, interface)
        if result.returncode not in (0, 2):
            m = Measurement(interface, error=f'ping exit {result.returncode}: {result.stderr.strip()}', raw_output=result.stdout + result.stderr)
        elif m.status == 'error':
            m.error += ': ' + result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        m = Measurement(interface, error=str(exc))
    m.duration_seconds = time.monotonic()-start
    return m
