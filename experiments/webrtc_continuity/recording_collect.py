"""Find and preserve new private recordings; offline only, no capture or network."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))

def correlate(rows):
    groups = {}
    for row in rows:
        key = row.get('session_fingerprint_sha256')
        if isinstance(key, str) and re.fullmatch('[0-9a-f]{64}', key):
            groups.setdefault(key, []).append(row)
    return [{'peer_roles': sorted({r['role'] for r in group}),
             'same_signaling_session_both_peers': {r['role'] for r in group} == {'A', 'B'},
             'recording_directories': [r['directory'] for r in group],
             'physical_handover_verified': False}
            for group in groups.values()]

def main():
    from experiments.webrtc_continuity.recording_prepare import process, inspect_bundle
    os.umask(0o077)
    destination = ROOT / 'recordings'
    incoming = destination / 'incoming'
    incoming.mkdir(parents=True, exist_ok=True, mode=0o700)
    folders = [Path.home() / 'Downloads', incoming,
               Path('/Volumes/NO NAME/SmartConnect-Recording-Rehearsal/RETURN-EVIDENCE')]
    candidates = sorted({p for folder in folders for p in folder.glob('SmartConnect-recording-*.zip')})
    processed = skipped = failed = 0
    for source in candidates:
        if source.is_symlink() or source.stat().st_size > 400 * 1024 * 1024:
            skipped += 1
            continue
        with source.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        try:
            manifest, _ = inspect_bundle(source)
            output = destination / ('peer-' + manifest['role'] + '-' + digest[:16])
            if output.exists():
                skipped += 1
                continue
            print('Converting a new private peer recording; source remains unchanged.', flush=True)
            process(source, output)
            processed += 1
        except Exception:
            failed += 1
            print('One bundle needs inspection. Original retained; private details suppressed.', flush=True)
    histories = destination / 'private-inventories'
    histories.mkdir(exist_ok=True, mode=0o700)
    history_folders = folders + [Path.home() / 'SmartConnectPrivate']
    for folder in history_folders:
        for source in folder.glob('PRIVATE-inventory-*.jsonl'):
            if source.is_symlink() or source.stat().st_size > 5 * 1024 * 1024:
                continue
            data = source.read_bytes()
            name = hashlib.sha256(data).hexdigest()[:16] + '.jsonl'
            target = histories / name
            if not target.exists():
                target.write_bytes(data)
                target.chmod(0o600)
    rows = []
    for path in destination.glob('peer-*/raw-originals/sanitized-observations.json'):
        if not (path.parent.parent / 'extraction-report.json').exists():
            continue
        try:
            data = json.loads(path.read_text())
            rows.append({'role': data['call']['role'],
                         'session_fingerprint_sha256': data.get('session_fingerprint_sha256'),
                         'directory': path.parent.parent.name})
        except (ValueError, KeyError):
            pass
    report = {'processed_at': datetime.now(timezone.utc).isoformat(),
              'new_bundles': processed, 'skipped_existing_or_oversized': skipped,
              'bundles_needing_review': failed, 'correlation': correlate(rows),
              'privacy_review_required': True, 'physical_handover_verified': False}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (destination / ('import-' + stamp + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print('Full MP4s, unmodified sources, stills and labeled draft excerpts are private. Review all footage before sharing.')
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
