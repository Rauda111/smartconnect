"""Deterministic synthetic adapter scenarios, never labeled live measurements."""
import argparse
import csv
from pathlib import Path
from mac_hub.monitor import Measurement
from mac_hub.engine import Engine
from mac_hub.run import record

NAMES = ('stable','deteriorating_wifi','cellular_degradation','wifi_recovery','unavailable_paths')


def scenario(name):
    if name not in NAMES:
        raise ValueError(name)
    for i in range(60):
        wifi, cell = 20., 35.
        if name in ('deteriorating_wifi','wifi_recovery') and i >= 10:
            wifi = 120.
        if name == 'wifi_recovery' and i >= 35:
            wifi = 20.
        if name == 'cellular_degradation':
            wifi, cell = 50., (15. if i < 20 else 140.)
        values = {n:Measurement(interface, 'reachable', latency, 0., 2., 10,10,9)
                  for n,interface,latency in [('wifi','en0',wifi),('cellular','en6',cell)]}
        if name == 'unavailable_paths':
            if 10 <= i < 30:
                values['wifi'] = Measurement('en0','no_reply',loss=100,sent=10)
            if 20 <= i < 40:
                values['cellular'] = Measurement('en6',error='synthetic interface error')
        yield i*12., values


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name in NAMES:
        for app in ('video_call','file_download'):
            engine=Engine(app)
            with (args.output_dir/f'{name}_{app}.csv').open('x',newline='') as f:
                writer=None
                for now, values in scenario(name):
                    row=record(values,now,app,engine,source='synthetic_fixture')
                    if writer is None:
                        writer=csv.DictWriter(f,fieldnames=list(row))
                        writer.writeheader()
                    writer.writerow(row)


if __name__ == '__main__':
    main()
