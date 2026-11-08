"""Build a NEW private Mac/Windows rehearsal kit; offline, no deployment or capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parent

def write(path, text, mode=0o600):
    path.write_text(text)
    path.chmod(mode)

def build(destination, previous):
    destination, previous = Path(destination), Path(previous)
    if destination.exists():
        raise ValueError('Use a fresh destination; existing kits are never overwritten')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    shutil.copytree(previous/'runtime', destination/'runtime', ignore=shutil.ignore_patterns('__pycache__'))
    runtime = destination/'runtime/experiments/webrtc_continuity'
    for name in ['index.html','app.js','core.js','style.css','jury.js','recording.js',
                 'jury_inventory.py','recording_prepare.py']:
        shutil.copyfile(SOURCE/name, runtime/name)
    for name in ['jury_operator.py','recording_collect.py','JURY_RECORDING.txt']:
        shutil.copyfile(SOURCE/name,destination/name)
    for name in ['.env','SmartConnect-Mac-A.html','SmartConnect-Windows-B.html']:
        shutil.copyfile(previous/name,destination/name)
    (destination/'recordings/incoming').mkdir(parents=True,mode=0o700)
    windows = destination/'Windows-Kit'
    windows.mkdir(mode=0o700)
    (windows/'RETURN-EVIDENCE').mkdir(mode=0o700)
    shutil.copyfile(previous/'SmartConnect-Windows-B.html',windows/'SmartConnect-Windows-B.html')
    shutil.copyfile(SOURCE/'jury_inventory_windows.ps1', windows/'jury_inventory_windows.ps1')
    # Inline, readable PowerShell commands use the normal command interpreter.
    # No execution-policy, registry, firewall or network configuration is changed.
    ps = '''$ErrorActionPreference='Stop'; try {
      $root=Join-Path $env:USERPROFILE 'SmartConnectPrivate'; [IO.Directory]::CreateDirectory($root) | Out-Null;
      $started=[DateTime]::UtcNow; $history=Join-Path $root ('PRIVATE-inventory-B-'+$started.ToString('yyyyMMddTHHmmssZ')+'.jsonl');
      $current=Join-Path $root 'current-interfaces.json'; $encoding=New-Object Text.UTF8Encoding($false);
      Write-Host 'Local inventory only, up to 420 seconds. Keep this window open. No addresses printed.';
      while (([DateTime]::UtcNow-$started).TotalSeconds -lt 420) {
        $interfaces=@(); foreach ($adapter in @(Get-NetAdapter -IncludeHidden)) {
          $network='unknown'; if ($adapter.NdisPhysicalMedium -in @(1,9)) {$network='wifi'} elseif ($adapter.NdisPhysicalMedium -eq 14) {$network='ethernet'} elseif ($adapter.NdisPhysicalMedium -eq 8) {$network='cellular'};
          $addresses=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue | ForEach-Object {$_.IPAddress});
          $interfaces+=@{id=('adapter-'+$adapter.ifIndex);index=[int]$adapter.ifIndex;active=($adapter.Status -eq 'Up');network=$network;addresses=$addresses};
        };
        $row=@{schema=1;kind='interface_inventory';platform='windows';role='B';captured_at=[DateTime]::UtcNow.ToString('o');interfaces=$interfaces};
        $json=ConvertTo-Json -InputObject $row -Depth 6 -Compress; [IO.File]::WriteAllText($current,$json,$encoding);
        [IO.File]::AppendAllText($history,$json+[Environment]::NewLine,$encoding); Start-Sleep -Seconds 5;
      }; Write-Host 'Inventory finished.';
    } catch {Write-Host 'Inventory unavailable. Do not change security settings. Keep path UNVERIFIED.'; exit 1}'''
    inline = ' '.join(line.strip() for line in ps.splitlines())
    write(windows/'START-WINDOWS.cmd', '@echo off\r\nstart "" msedge "%~dp0SmartConnect-Windows-B.html"\r\npowershell.exe -NoProfile -Command "'+inline+'"\r\npause\r\n')
    write(windows/'WINDOWS-STEPS.txt', '''AFTER STAGING UPDATE AND SEPARATE RECORDING/MEDIA APPROVAL
1. Double-click START-WINDOWS.cmd. Keep the inventory window open. Use Edge or Chrome.
2. Page: Peer B, SmartConnect-assisted, 300 seconds, automatic signaling.
3. Click Link private local interface inventory; select
   %USERPROFILE%\\SmartConnectPrivate\\current-interfaces.json
4. Check the separately approved media and recording boxes. Open sanitized jury view.
5. Click Start approved tab recording. Select ONLY this SmartConnect browser tab.
6. Confirm RECORDING. When told, Start this peer, allow camera/microphone and keep it in front.
7. Speak/wave in both directions. Recommended network is REMOTE MAC; local Windows path is separate.
8. At 300 seconds confirm ended and one SmartConnect-recording-B-....zip download.
   If absent, click Download recording bundle. Do not reload until saved.
9. After the call ONLY: copy the new ZIP and newest PRIVATE-inventory-B-....jsonl
   (from %USERPROFILE%\\SmartConnectPrivate) to RETURN-EVIDENCE on this USB.
   Safely eject and return to Mac once. Keep raw footage/private files off public slides.
If recording cannot verify this tab, do not choose desktop/window or change security settings.
If media has no two-way progress after 30 seconds, end both peers and use the offline evidence video.
''')
    header = '#!/bin/zsh\ncd -- "${0:A:h}"\numask 077\n'
    footer = '\nread "reply?Press Return to close. "\n'
    write(destination/'0-Check-Staging.command',header+'''echo "Read-only HTTPS and local checks. No call, capture or measurement probes."
/opt/anaconda3/bin/python jury_operator.py check --staging
'''+footer,0o700)
    write(destination/'1-Start-Local-Inventory.command',header+'''echo "Read-only local OS inventory. No camera, microphone or network probes."
open -a "Google Chrome" "SmartConnect-Mac-A.html"
PYTHONPATH="$PWD/runtime" /opt/anaconda3/bin/python -m experiments.webrtc_continuity.jury_inventory
'''+footer,0o700)
    collector = (previous/'2-Start-Approved-Measurements.command').read_text().replace('sc_operator.py','jury_operator.py')
    collector = collector.replace('No capture, route changes', 'This command starts no recording, route changes')
    write(destination/'2-Start-Approved-Measurements.command',collector,0o700)
    write(destination/'3-Process-New-Recordings.command',header+'''/opt/anaconda3/bin/python recording_collect.py
'''+footer,0o700)
    write(destination/'Copy-Windows-Kit-To-USB.command',header+'''/opt/anaconda3/bin/python copy_windows_kit.py
'''+footer,0o700)
    write(destination/'copy_windows_kit.py', '''"""Copy only the reader launcher and bounded Windows helper to an existing USB. No formatting."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
volume=Path('/Volumes/NO NAME')
if not volume.is_dir():
    print('Connect the existing USB drive to the Mac, then run this helper again. Nothing was changed.')
    raise SystemExit(1)
target=volume/'SmartConnect-Recording-Rehearsal'
if target.exists():
    print('Kit already exists. It was preserved; check its version before use.')
    raise SystemExit(1)
shutil.copytree(root/'Windows-Kit',target)
print('Windows kit copied. No writer credential included. Safely eject before moving it to Windows.')
''')
    write(destination/'PRIVATE-READ-ME.txt','''PRIVATE OPERATOR KIT — NOT A PUBLIC PRESENTATION FOLDER
Contains the staging writer and reader credentials. Never upload, screenshot, share or commit this folder.
Windows-Kit contains only the existing reader launcher, local inventory helper and instructions.
Nothing runs on installation. Staging deployment and recording/probe approvals remain required.
0 checks the REVIEWED new client; it will report an asset mismatch until that commit is deployed.
1 opens the private Mac launcher and starts only bounded LOCAL interface inventory.
2 starts real probes only after the separate approval acknowledgment and an active call.
3 privately preserves/decodes new recording ZIPs and produces full MP4s, PNGs and labeled DRAFT highlights.
Recordings must be reviewed in full before sharing; no finished real recording exists yet.
Full steps: JURY_RECORDING.txt. Offline fallback: ../SmartConnectCompetition2026/START-HERE.html.
''')
    manifest={str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in destination.rglob('*') if p.is_file() and p.suffix not in ['.html'] and p.name!='.env'}
    write(destination/'runtime-provenance.json',json.dumps({'offline_preparation_only':True,'sha256':manifest},indent=2)+'\n')
    for path in destination.rglob('*'):
        path.chmod(0o700 if path.is_dir() or path.suffix=='.command' else 0o600)
    print('New private kit prepared. Credentials not printed. No deployment, media, probes or capture started.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path,default=Path.home()/'SmartConnectCompetitionPrivate')
    a=p.parse_args()
    build(a.output,a.previous)
