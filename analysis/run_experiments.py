"""Run the unchanged finalized simulator CLI, preserving fresh CSVs and provenance.

Usage: python run_experiments.py --repo /path/to/smartconnect --results-dir /path/to/final_testing
Activate the repository venv before invoking. Refuses to overwrite final raw results.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SCENARIOS = ('leaving_wifi', 'congested_wifi', 'large_download', 'recovery')
SEEDS = range(10)
SOURCE_FILES = ('simulate.py', 'baseline.py', 'smartconnect.py', 'scenarios.py',
                'config.py', 'test_simulation.py', 'test_smartconnect.py',
                'requirements.txt', 'README.md', 'app.py', '.gitignore')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--results-dir', required=True, type=Path)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.results_dir.resolve()
    raw, logs = out / 'raw_csv', out / 'verification'
    if raw.exists() and any(raw.iterdir()):
        raise SystemExit('Raw result directory must be empty. Choose a fresh results directory.')
    if git(repo, 'diff', '--name-only') or git(repo, 'diff', '--cached', '--name-only'):
        raise SystemExit('Tracked source has local changes; refusing experiments.')
    raw.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    snapshot = out / 'source_snapshot'
    snapshot.mkdir(parents=True, exist_ok=True)
    source_hashes = {name: digest(repo / name) for name in SOURCE_FILES}
    for name in SOURCE_FILES:
        shutil.copyfile(repo / name, snapshot / name)

    test = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=repo,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (logs / 'unit_tests.log').write_text(test.stdout)
    if test.returncode or not re.search(r'Ran 9 tests\b', test.stdout) or not re.search(r'^OK$', test.stdout, re.M):
        raise SystemExit('Required nine-test gate failed. Stop; inspect verification/unit_tests.log.')
    print('Test gate: Ran 9 tests; OK', flush=True)
    frozen = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (logs / 'environment.txt').write_text(sys.version + '\n' + frozen)
    manifest = {
        'repository': git(repo, 'remote', 'get-url', 'origin'),
        'commit': git(repo, 'rev-parse', 'HEAD'),
        'branch': git(repo, 'branch', '--show-current'),
        'remote_main_commit': git(repo, 'rev-parse', 'origin/main'),
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'python': sys.version, 'scenarios': list(SCENARIOS), 'seeds': list(SEEDS),
        'source_sha256': source_hashes,
        'simulation_label': 'Controlled simulation results using realistic assumed Wi-Fi and 5G-like network conditions.',
        'tests': {'count': 9, 'passed': True, 'log': 'verification/unit_tests.log'},
        'runs': [], 'complete': False,
    }
    manifest_path = logs / 'experiment_manifest.json'
    configurations = [('baseline', None), ('smartconnect', 'video_call'),
                      ('smartconnect', 'file_download')]
    for scenario in SCENARIOS:
        for seed in SEEDS:
            for method, app in configurations:
                suffix = 'baseline' if method == 'baseline' else f'smartconnect_{app}'
                filename = f'{scenario}_seed{seed}_{suffix}.csv'
                native = repo / 'outputs' / filename
                if native.exists():
                    raise SystemExit(f'Refusing to use or overwrite existing experiment output: {native}')
                command = [sys.executable, 'simulate.py', '--scenario', scenario,
                           '--method', method, '--seed', str(seed)]
                if app:
                    command += ['--application', app]
                result = subprocess.run(command, cwd=repo, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                log_name = filename.removesuffix('.csv') + '.log'
                (logs / log_name).write_text(result.stdout)
                if result.returncode or not native.is_file():
                    raise SystemExit(f'Experiment failed: {filename}; see {log_name}')
                target = raw / filename
                shutil.copyfile(native, target)
                if digest(native) != digest(target):
                    raise SystemExit(f'Raw copy checksum mismatch: {filename}')
                manifest['runs'].append({'scenario': scenario, 'seed': seed,
                    'method': method, 'application': app, 'command': command,
                    'raw_csv': str(target.relative_to(out)), 'sha256': digest(target),
                    'log': str((logs / log_name).relative_to(out))})
                manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
            print(f'Completed {scenario} seed {seed}: {len(manifest["runs"])}/120', flush=True)
    final_hashes = {name: digest(repo / name) for name in SOURCE_FILES}
    if final_hashes != source_hashes or git(repo, 'diff', '--name-only'):
        raise SystemExit('Source changed during experiments; do not use results.')
    assert len(manifest['runs']) == 120
    manifest.update(complete=True, source_unchanged=True,
                    completed_utc=datetime.now(timezone.utc).isoformat())
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Complete: 120 untouched raw CSVs; source hashes unchanged.', flush=True)

if __name__ == '__main__':
    main()
