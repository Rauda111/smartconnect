"""Build a new private one-click kit. No UI launch, deployment or traffic."""
import argparse,hashlib,html,json,os,plistlib,re,shutil,subprocess,sys,zipfile
from pathlib import Path
SOURCE=Path(__file__).resolve().parent
REPO=SOURCE.parents[1]
ORIGIN='https://smartconnect-prototype2-staging-4b5e878.onrender.com'
def write(path,text,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.write_text(text);path.chmod(mode)
def private_form(origin,reader,role):
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,256}',reader) or role not in ('A','B'):raise ValueError('Invalid private launch input')
    if not (origin==ORIGIN or re.fullmatch(r'http://127\.0\.0\.1:\d{4,5}',origin)):raise ValueError('Unsupported launch destination')
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>SmartConnect</title></head><body>'
            '<h1>Opening SmartConnect…</h1><p>No cameras, microphones or measurements start here.</p>'
            '<form id="launch" method="post" action="'+html.escape(origin,quote=True)+'/launch" target="_self">'
            '<input type="hidden" name="reader" value="'+html.escape(reader,quote=True)+'">'
            '<input type="hidden" name="role" value="'+role+'">'
            '<noscript><button type="submit">Open SmartConnect</button></noscript></form>'
            '<script>document.getElementById("launch").submit();</script></body></html>')
def mac_app(root,name,action,python):
    app=root/(name+'.app');exe=app/'Contents/MacOS/SmartConnect'
    # Paths, never credentials, appear in the process arguments.
    script='#!/bin/zsh\nSC_DEMO_ROOT="$(cd -- "$(dirname -- "$0")/../../.." && pwd)"\nexec '+shlex_quote(python)+' "$SC_DEMO_ROOT/jury_launch.py" '+action+'\n'
    write(exe,script,0o700)
    info={'CFBundleExecutable':'SmartConnect','CFBundleIdentifier':'local.smartconnect.'+action,'CFBundleName':name,'CFBundlePackageType':'APPL','CFBundleVersion':'1','LSUIElement':True}
    p=app/'Contents/Info.plist';p.write_bytes(plistlib.dumps(info));p.chmod(0o600)
def shlex_quote(text):
    import shlex
    return shlex.quote(text)
def windows_launcher():
    script=r'''$ErrorActionPreference='Stop'; try {
      $root=$env:SC_DEMO_ROOT; $ready=$false;
      Write-Host 'SmartConnect is checking staging. No camera or microphone is active.';
      for($i=0;$i -lt 4;$i++) { try { $r=Invoke-WebRequest -UseBasicParsing -Uri '__ORIGIN__/launch.js' -TimeoutSec 15; if($r.StatusCode -eq 200 -and $r.Content.Contains('smartconnect.reader')) {$ready=$true;break} } catch {} ; if($i -lt 3){Start-Sleep -Seconds 2} };
      if(-not $ready){Write-Host 'The prepared staging update is unavailable or not deployed yet. No call started.';exit 1};
      $candidates=@((Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),(Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),(Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),(Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'));
      $browser=$candidates | Where-Object {Test-Path $_} | Select-Object -First 1;
      if(-not $browser){Write-Host 'Current Chrome or Edge is required. No security settings were changed.';exit 1};
      $file=Join-Path $root 'PRIVATE-Windows-Launch.html';
      Start-Process -FilePath $browser -ArgumentList ([string]::Concat([char]34,$file,[char]34));
      exit 0;
    } catch {Write-Host 'SmartConnect could not open. No private error details are printed.';exit 1}'''.replace('__ORIGIN__',ORIGIN)
    inline=' '.join(line.strip() for line in script.splitlines())
    return '@echo off\r\nsetlocal\r\nset "SC_DEMO_ROOT=%~dp0"\r\npowershell.exe -NoProfile -Command "'+inline+'"\r\nif errorlevel 1 pause\r\n'
def build(output,credentials,offline,python):
    output,credentials,offline=Path(output),Path(credentials),Path(offline)
    if output.exists():raise ValueError('Use a new private destination')
    config=dict(l.split('=',1) for l in credentials.read_text().splitlines() if l and not l.startswith('#'))
    if set(config)!={'SMARTCONNECT_SIGNAL_TOKEN','SMARTCONNECT_POLICY_TOKEN'} or any(not re.fullmatch(r'[A-Za-z0-9_-]{40,256}',v) for v in config.values()):raise ValueError('Invalid private configuration')
    os.umask(0o077);output.mkdir(mode=0o700);runtime=output/'runtime';runtime.mkdir(mode=0o700)
    # Copy source/data only, never .git, private environment files or old run folders.
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=REPO).decode().split('\0')
    extra=['experiments/webrtc_continuity/'+name for name in ['launch.js','jury_launch.py','jury_live_watch.py','prepare_simple_demo.py']]
    for relative in sorted(set(tracked+extra)):
        source=REPO/relative
        if not relative or not source.is_file():continue
        if '.env' in Path(relative).name or '.git' in Path(relative).parts:continue
        target=runtime/relative;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copy2(source,target)
    write(output/'.env','\n'.join(k+'='+v for k,v in config.items())+'\n')
    for name in ['jury_launch.py','jury_live_watch.py','jury_operator.py']:
        shutil.copyfile(SOURCE/name,output/name);(output/name).chmod(0o600)
    write(output/'PRIVATE-Mac-Launch.html',private_form(ORIGIN,config['SMARTCONNECT_SIGNAL_TOKEN'],'A'))
    for name,action in [('1 - Prototype 1 - Engine and Results','prototype1'),('2 - Prototype 2 - Mac A','mac'),('4 - Offline Recorded Demo','offline')]:mac_app(output,name,action,python)
    shutil.copytree(offline,output/'Offline-Demo')
    windows=output/'3 - Windows Laptop';windows.mkdir(mode=0o700)
    write(windows/'Prototype 2 - Windows B.cmd',windows_launcher())
    write(windows/'PRIVATE-Windows-Launch.html',private_form(ORIGIN,config['SMARTCONNECT_SIGNAL_TOKEN'],'B'))
    shutil.copytree(offline,windows/'Offline-Demo')
    write(windows/'Offline Recorded Demo.cmd','@echo off\r\nstart "" "%~dp0Offline-Demo\\video\\SmartConnect-Evidence-Edition.mp4"\r\n')
    write(windows/'Prototype 1 - Verified Results.cmd','@echo off\r\nstart "" "%~dp0Offline-Demo\\START-HERE.html"\r\n')
    instructions='''SMARTCONNECT — SIMPLE JURY WORKFLOW

Install this private kit once before the event. Keep the Windows folder on its
local disk. No USB transfer, URL copying, Terminal or inventory link is required
between calls. Do not show private launcher source or the Technical Details panel
while manually recording. No paid service, credential change or deployment is
performed by a launcher.

Mac: double-click "2 - Prototype 2 - Mac A". Windows: double-click
"Prototype 2 - Windows B.cmd". Both open the same staging service with A/B,
SmartConnect-assisted, Automatic signaling and 300 seconds already selected.
Refreshing the SAME tab keeps its access/configuration but stops media.
Start Call is the explicit camera/microphone action. End Call releases the room.
Choose New Call on BOTH laptops, then Start Call on B followed by A for a repeat.
New Call never starts cameras itself. Keep one peer tab per laptop.

Live measurements require a separate fresh approved-demo.json grant, prepared by
the assistant only after explicit approval. Without that grant, the Mac launcher
starts NO probes and measured recommendations remain unavailable. When approved,
the existing bounded collector starts after Mac A joins and is capped per grant.
The grant can cover at most two calls, 360 ICMP echoes / 270 seconds each, within
each 300-second call. Opening Prototype 1 displays existing recorded results;
it does not collect live network data.

60-SECOND REHEARSAL (after separate deployment/media/probe approval)
0–10 s: iPhone USB connected; both Wi-Fi links available; put on headphones.
10–20 s: open the Mac A and Windows B launchers. Allow a free-staging cold start
BEFORE the jury slot; cold starts can exceed this rehearsal schedule.
20–30 s: Start Call on Windows, then Mac; allow camera/microphone permissions.
30–45 s: wave/speak both ways. Show live recommendation separately from observed
media candidate and physical verification. Unknown stays unknown. Keep Technical
Details closed. Use your manual screen recorder only after its separate approval.
45–60 s: End Call, then New Call on both; Start B then A again only if TWO calls
were explicitly approved. No reopening launchers or moving files between calls.

If the venue blocks direct WebRTC, play the existing Offline Recorded Demo.
It is a narrated edition of preserved real experiment evidence, not new hardware
footage. No TURN relay is provisioned. HTTPS reachability is not proof that media
will cross venue NAT, firewalls or Wi-Fi client isolation.

This kit needs the prepared staging update before its private launchers work.
Production and existing working kits remain untouched. Native Windows execution
and two actual media sessions still require the physical acceptance test.
'''
    write(output/'READ-ME-FIRST.txt',instructions);write(windows/'READ-ME-FIRST.txt',instructions)
    writer=config['SMARTCONNECT_POLICY_TOKEN'].encode()
    for p in windows.rglob('*'):
        if p.is_file() and writer in p.read_bytes():raise ValueError('Writer found in Windows kit')
    manifest={str(p.relative_to(output)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in output.rglob('*') if p.is_file() and p.suffix not in ('.html',) and p.name!='.env'}
    # The manifest stays private; the credential itself and its digest are omitted.
    write(output/'PRIVATE-PACKAGE-MANIFEST.json',json.dumps({'status':'prepared_not_deployed','writer_excluded_from_windows':True,'probe_approval_present':False,'files':manifest},indent=2)+'\n')
    archive=output/'Windows-Private-Kit.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in windows.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(windows.parent))
    archive.chmod(0o600)
    return {'prepared':True,'writer_excluded_from_windows':True,'probes_or_media_started':False,'staging_deployed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--credentials',required=True);p.add_argument('--offline',required=True);p.add_argument('--python',default=sys.executable);a=p.parse_args()
    try:print(json.dumps(build(a.output,a.credentials,a.offline,a.python)))
    except Exception:print('Private kit build failed; private error details suppressed.');raise SystemExit(1)
if __name__=='__main__':main()
