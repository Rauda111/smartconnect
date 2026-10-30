"""Causal application adapter, reusing Phase 1 stability controller unchanged."""
import math
from dataclasses import replace
from mac_hub.engine import Engine


def goodput(row):
    """Delivered body bits / entire fresh HTTPS request time; never capacity."""
    if row.get('status') != 'success':
        return None
    size, duration = row.get('bytes_received'), row.get('request_duration_ms')
    if size is None or duration is None or size <= 0 or duration <= 0:
        return None
    if not math.isfinite(size) or not math.isfinite(duration):
        return None
    return size * 8 / duration / 1000


class Controller:
    """Video: original RTT/loss adapter. Download: bounded-goodput utility.

    Download maps a predeclared utility into the existing engine's normalized
    latency dimension. This is a policy input adapter, never an RTT measurement.
    RTT/loss and synthetic utility remain separately labelled in the evidence.
    Both profiles retain Engine's trends, margin, three-window hold and 30s dwell.
    """
    def __init__(self, application):
        if application not in ('video_call', 'file_download'):
            raise ValueError('Unknown application')
        self.application = application
        self.engine = Engine(application)
        self.last_basis = None

    def step(self, measurements, probes, now):
        adapted = {}
        complete = all(goodput(probes[n]) is not None for n in measurements)
        basis = 'bounded_goodput_utility_and_loss' if self.application == 'file_download' and complete else 'icmp_rtt_and_loss'
        if self.last_basis is not None and basis != self.last_basis:
            # Scores on different metric bases must not share a trend or hold streak.
            self.engine.history = {n: [] for n in measurements}
            self.engine.pending, self.engine.streak = None, 0
        self.last_basis = basis
        utilities = {}
        for name, m in measurements.items():
            valid = m.status == 'reachable' and all(v is not None and math.isfinite(v)
                                                    for v in (m.latency, m.loss))
            if not valid:
                adapted[name] = replace(m, status='error')
                continue
            latency = m.latency
            if self.application == 'file_download' and complete:
                # Equal-size, pre-decision probes only. Fixed 10 Mbps reference;
                # log utility explicitly; never pass a fabricated throughput field.
                g = goodput(probes[name])
                utility = .8 * min(1, g / 10) + .2 * (1-min(1, max(0, (m.latency-1)/149)))
                utilities[name] = utility
                latency = 1 + 149 * (1-utility)
            adapted[name] = replace(m, latency=latency)
        result = self.engine.step(adapted, now)
        result.update(application=self.application,
                      scoring_basis=basis,
                      utility=utilities)
        return result
