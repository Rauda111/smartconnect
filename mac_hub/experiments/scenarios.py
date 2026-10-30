"""Seeded synthetic probe-window observations, never live measurements."""
from datetime import datetime, timedelta, timezone
import random

NAMES = ('stable', 'deteriorating_wifi', 'congested_wifi',
         'cellular_degradation', 'wifi_recovery', 'network_unavailability')
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def generate(name, seed=0):
    """90 five-second observation windows. Events are controlled ground truth.

    Noise seeds test sensitivity to these assumed curves, not field variability.
    200 assumed probes/window permit 0.5 percentage-point synthetic loss steps;
    this is not the packet timing/configuration of the real collector.
    """
    if name not in NAMES or not isinstance(seed, int) or seed < 0:
        raise ValueError('Unknown scenario or invalid seed')
    rng = random.Random(seed)
    rows = []
    for i in range(90):
        t = i * 5.0
        wifi, cell = [22., 0., 3.], [38., 0., 5.]
        stable_region = i < 20 or i >= 65
        if name == 'stable':
            stable_region = True
        elif name in ('deteriorating_wifi', 'wifi_recovery'):
            x = max(0., min(1., (i-20)/15))
            wifi = [22+95*x, 6*x, 3+25*x]
            if name == 'wifi_recovery' and i >= 55:
                x = max(0., 1-(i-55)/10)
                wifi = [22+95*x, 6*x, 3+25*x]
        elif name == 'congested_wifi':
            if i >= 20:
                wifi = [95., 4., 30.]
        elif name == 'cellular_degradation':
            wifi, cell = [48., 0., 4.], [15., 0., 2.]
            if i >= 20:
                cell = [130., 5., 30.]
        elif name == 'network_unavailability':
            stable_region = i < 20 or i >= 70
        row = dict(scenario=name, seed=seed, source='synthetic',
                   timestamp=(EPOCH+timedelta(seconds=t)).isoformat(), elapsed_seconds=t,
                   stable_region=stable_region, target='synthetic_endpoint')
        for n, values in [('wifi', wifi), ('cellular', cell)]:
            latency = max(0., values[0]+rng.uniform(-2, 2))
            loss = round(max(0., values[1]+rng.uniform(-.3, .3))*2)/2
            variation = max(0., values[2]+rng.uniform(-.5, .5))
            status = 'reachable'
            if name == 'network_unavailability':
                if n == 'wifi' and 20 <= i < 50:
                    status = 'no_reply'
                    latency, loss, variation = None, 100., None
                if n == 'cellular' and 35 <= i < 65:
                    status = 'error'
                    latency, loss, variation = None, None, None
            row.update({f'{n}_status': status, f'{n}_latency': latency,
                        f'{n}_loss': loss, f'{n}_rtt_variation': variation,
                        f'{n}_sent': 0 if status == 'error' else 200,
                        f'{n}_received': None if loss is None else round(200*(1-loss/100))})
        rows.append(row)
    events = []
    def event(onset, target, label):
        events.append(dict(onset_seconds=onset, expected_path=target, event=label))
    if name in ('deteriorating_wifi', 'congested_wifi', 'wifi_recovery'):
        event(100., 'cellular', 'wifi_degradation_onset')
    if name == 'cellular_degradation':
        event(100., 'wifi', 'cellular_degradation_onset')
    if name == 'wifi_recovery':
        event(275., 'wifi', 'wifi_recovery_onset')
    if name == 'network_unavailability':
        event(100., 'cellular', 'wifi_no_reply')
        event(175., 'none', 'both_unavailable')
        event(250., 'wifi', 'wifi_returns')
    return rows, events
