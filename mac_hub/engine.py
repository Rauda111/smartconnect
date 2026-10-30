"""Causal partial-metric adapter of the simulation policy, in elapsed seconds."""
import math
from smartconnect import WEIGHTS, BOUNDS, LIMITS, classify_trend

NETWORKS = ('wifi', 'cellular')


class Engine:
    def __init__(self, application='video_call', margin=.05, hold=3, dwell=30):
        if application not in WEIGHTS or hold < 1 or dwell < 0 or margin < 0:
            raise ValueError('Invalid policy configuration')
        self.application, self.margin, self.hold, self.dwell = application, margin, hold, dwell
        self.current = None
        self.pending = None
        self.streak = 0
        self.last_switch = -math.inf
        self.last_time = -math.inf
        self.history = {n: [] for n in NETWORKS}

    def step(self, measurements, now):
        if not math.isfinite(now) or now <= self.last_time:
            raise ValueError('Time must increase strictly')
        if set(measurements) != set(NETWORKS):
            raise ValueError('Both paths required')
        # Common measured dimensions avoid comparing unlike score coverage.
        common = [k for k in ('latency', 'loss') if all(
            m.status == 'reachable' and getattr(m, k) is not None
            for m in measurements.values())]
        # An unavailable path does not prevent scoring the surviving path.
        if not common:
            common = ['latency', 'loss']
        coverage = sum(WEIGHTS[self.application][k] for k in common)
        details = {}
        for n, m in measurements.items():
            valid = m.status == 'reachable' and all(
                getattr(m, k) is not None and math.isfinite(getattr(m, k)) for k in common)
            score = None
            slope = 0.
            if valid:
                score = sum(WEIGHTS[self.application][k] * (1-max(0, min(1,
                    (getattr(m, k)-BOUNDS[k][0])/(BOUNDS[k][1]-BOUNDS[k][0])))) for k in common)/coverage
                self.history[n].append(score)
                self.history[n] = self.history[n][-5:]
                h = self.history[n]
                if len(h) > 1:
                    xbar = (len(h)-1)/2
                    slope = sum((i-xbar)*(v-sum(h)/len(h)) for i,v in enumerate(h))/sum((i-xbar)**2 for i in range(len(h)))
            else:
                self.history[n].clear()
            breaches = [k for k, limit in LIMITS[self.application].items()
                        if k in common and getattr(m,k) is not None and getattr(m,k)>limit]
            details[n] = dict(score=score, adjusted_score=max(0,min(1,score+.5*slope)) if valid else None,
                              trend=classify_trend(slope) if valid else 'Unavailable', trend_slope=slope if valid else None,
                              breaches=','.join(breaches), unknown_guardrails=','.join(k for k in LIMITS[self.application] if k not in common))
        usable = [n for n in NETWORKS if details[n]['score'] is not None]
        previous = self.current
        reason = 'Hold: insufficient advantage or candidate breaches observed guardrails'
        advantage = None
        if self.current not in usable:
            # Outage exception: never retain a recommendation for a failed path.
            self.current = next((n for n in usable if not details[n]['breaches']), None)
            self.pending, self.streak = None, 0
            reason = 'Availability reset: recommend usable path immediately' if self.current else 'No eligible path: unavailable or observed guardrail breach'
            if self.current:
                self.last_switch = now
        else:
            candidate = next(n for n in NETWORKS if n != self.current)
            superior = False
            if candidate in usable:
                advantage = details[candidate]['adjusted_score']-details[self.current]['adjusted_score']
                rescue = bool(details[self.current]['breaches']) and advantage > 0
                superior = not details[candidate]['breaches'] and (advantage >= self.margin or rescue)
            if superior:
                self.streak = self.streak+1 if self.pending == candidate else 1
                self.pending = candidate
                reason = f'Hold: superiority {self.streak}/{self.hold}; elapsed dwell {now-self.last_switch:.1f}/{self.dwell}s'
                if self.streak >= self.hold and now-self.last_switch >= self.dwell:
                    self.current = candidate
                    self.last_switch = now
                    reason = 'Recommend change: sustained advantage; observed guardrails and dwell satisfied'
                    self.pending, self.streak = None, 0
            else:
                self.pending, self.streak = None, 0
        self.last_time = now
        return dict(recommended=self.current or 'none', previous=previous or 'none',
                    recommendation_change=previous is not None and previous != self.current,
                    baseline=next((n for n in NETWORKS if measurements[n].status == 'reachable'), 'none'),
                    explanation=reason, advantage=advantage, hold_count=self.streak,
                    coverage=coverage, application=self.application, details=details)
