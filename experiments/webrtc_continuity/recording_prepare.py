"""Offline footage extraction. Never records, probes, changes networks or uploads."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

def inspect_bundle(source):
    with zipfile.ZipFile(source) as z:
        names=z.namelist()
        if len(names)>30 or len(set(names))!=len(names):raise ValueError('Unexpected archive structure')
        if any('/' in n or '\\' in n or n.startswith('.') for n in names):raise ValueError('Unsafe archive entry')
        allowed=lambda n:n in ['full-unedited-A.webm','full-unedited-B.webm','recording-manifest.json','sanitized-observations.json'] or (n.startswith('still-') and n.endswith('.png'))
        if not all(allowed(n) for n in names) or sum(i.file_size for i in z.infolist())>400*1024*1024:raise ValueError('Unexpected or oversized archive')
        if z.getinfo('recording-manifest.json').file_size>65536 or z.getinfo('sanitized-observations.json').file_size>10*1024*1024:raise ValueError('Oversized metadata')
        manifest=json.loads(z.read('recording-manifest.json'))
        role=manifest.get('role')
        if role not in ['A','B'] or 'full-unedited-'+role+'.webm' not in names:raise ValueError('Missing peer recording')
        if manifest.get('surface')!='verified_current_browser_tab' or manifest.get('raw_recording_unedited') is not True:raise ValueError('Recording surface provenance missing')
        observations=json.loads(z.read('sanitized-observations.json'))
        if observations.get('call',{}).get('role')!=role:raise ValueError('Peer evidence mismatch')
        return manifest,observations

def intervals(duration,markers):
    """Chronological 150 s maximum, no repeated frames or invented events."""
    if duration<=150:return[(0,duration)]
    recovery=[float(m['recording_elapsed_ms'])/1000 for m in markers if m.get('reason')=='recovery-request' and isinstance(m.get('recording_elapsed_ms'),(int,float))]
    points=[0,duration*.22,duration*.48,duration*.72,duration-30]
    for i,value in enumerate(recovery[:2]):points[2+i]=max(0,min(duration-30,value-12))
    ranges=sorted((max(0,min(duration-30,p)),max(0,min(duration-30,p))+30) for p in points)
    merged=[]
    for start,end in ranges:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    remaining=150-sum(b-a for a,b in merged)
    for i in range(len(merged)-1):
        extra=min(remaining,merged[i+1][0]-merged[i][1]);merged[i]=(merged[i][0],merged[i][1]+extra);remaining-=extra
        if remaining<=.001:break
    return merged

def process(source,output,ffmpeg='ffmpeg',ffprobe='ffprobe'):
    source=Path(source).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Output must be a fresh folder')
    manifest,observations=inspect_bundle(source)
    if shutil.disk_usage(output.parent).free<source.stat().st_size*4+256*1024*1024:raise ValueError('Insufficient recording workspace')
    output.mkdir(mode=0o700);raw=output/'raw-originals';raw.mkdir(mode=0o700)
    shutil.copyfile(source,raw/'original-bundle.zip')
    with zipfile.ZipFile(source) as z:
        for item in z.infolist():
            with z.open(item) as src,open(raw/item.filename,'xb') as dst:shutil.copyfileobj(src,dst)
    role=manifest['role'];movie=raw/('full-unedited-'+role+'.webm')
    info=json.loads(subprocess.check_output([ffprobe,'-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(movie)],text=True))
    def run(args):subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin',*args],check=True,capture_output=True)
    full=output/('full-unedited-'+role+'.mp4')
    run(['-i',str(movie),'-map','0:v:0','-map','0:a?','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-preset','fast','-crf','20','-c:a','aac','-b:a','160k','-movflags','+faststart',str(full)])
    # Browser MediaRecorder WebM commonly has no duration/seek index. Decode it
    # once, then use the indexed full MP4 for duration, accurate seeking and cuts.
    duration=float(json.loads(subprocess.check_output([ffprobe,'-v','error','-show_entries','format=duration','-of','json',str(full)],text=True))['format']['duration'])
    if not 0<duration<=430:raise ValueError('Unexpected recording duration')
    frames=output/'frames';frames.mkdir()
    run(['-i',str(full),'-frames:v','1',str(frames/'frame-start.png')])
    run(['-i',str(full),'-vf','fps=1/15','-fps_mode','vfr',str(frames/'frame-%03d.png')])
    cuts=intervals(duration,manifest.get('markers',[]));clips=output/'excerpts';clips.mkdir();edl=[]
    for i,(start,end) in enumerate(cuts):
        path=clips/f'excerpt-{i+1:02}.mp4'
        label=f'RECORDED EXCERPT {i+1} | source {start:.1f}-{end:.1f} seconds'
        from PIL import Image,ImageDraw,ImageFont
        width=next(s['width'] for s in info['streams'] if s['codec_type']=='video')
        banner=Image.new('RGBA',(width,46),(0,0,0,210));draw=ImageDraw.Draw(banner)
        draw.text((8,10),label,fill='white',font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',max(10,min(22,width//50))))
        overlay=clips/f'excerpt-label-{i+1:02}.png';banner.save(overlay)
        vf='[0:v]pad=ceil(iw/2)*2:ceil(ih/2)*2[v];[v][1:v]overlay=x=0:y=H-h:format=auto[vout]'
        run(['-ss',str(start),'-i',str(full),'-i',str(overlay),'-t',str(end-start),'-filter_complex',vf,'-map','[vout]','-map','0:a?','-c:v','libx264','-preset','fast','-crf','20','-c:a','aac','-b:a','160k',str(path)])
        edl.append({'file':path.name,'source_start_seconds':start,'source_end_seconds':end})
    # Relative generated names avoid interpreting user-controlled paths in concat text.
    listing=clips/'concat.txt';listing.write_text(''.join("file '"+r['file']+"'\n" for r in edl))
    run(['-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(output/'DRAFT-highlights-review-before-sharing.mp4')])
    receipt={'processed_at':datetime.now(timezone.utc).isoformat(),'role':role,'raw_source_sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'full_duration_seconds':duration,'draft_duration_seconds':sum(b-a for a,b in cuts),'edits':edl,'private_review_required':True,'physical_handover_verified':False,'historical_footage_inserted':False,'source_unchanged':True}
    (output/'extraction-report.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for path in output.rglob('*'):path.chmod(0o700 if path.is_dir() else 0o600)
    return receipt

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args(argv)
    try:print(json.dumps(process(a.source,a.output),indent=2));return 0
    except Exception:print('Extraction stopped safely. Check bundle, free disk space, output folder and local ffmpeg. Private details suppressed.');return 1
if __name__=='__main__':raise SystemExit(main())
