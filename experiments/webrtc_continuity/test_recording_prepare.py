import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import subprocess
import shutil
from experiments.webrtc_continuity.recording_prepare import inspect_bundle,intervals,process

class RecordingPreparationTests(unittest.TestCase):
    def test_chronological_nonduplicating_150_second_edit(self):
        result=intervals(310,[{'reason':'recovery-request','recording_elapsed_ms':185000},{'reason':'recovery-request','recording_elapsed_ms':230000}])
        self.assertAlmostEqual(sum(b-a for a,b in result),150)
        self.assertTrue(all(a>=0 and b<=310 and b>a for a,b in result))
        self.assertTrue(all(result[i][1]<=result[i+1][0] for i in range(len(result)-1)))
        self.assertTrue(any(a<=185<=b for a,b in result));self.assertTrue(any(a<=230<=b for a,b in result))
    def test_short_recording_never_looped_or_extended(self):self.assertEqual(intervals(80,[]),[(0,80)])
    def test_missing_events_do_not_invent_events(self):
        result=intervals(300,[]);self.assertAlmostEqual(sum(b-a for a,b in result),150)
    def test_rejects_path_traversal_before_extracting(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../private.txt','not extracted')
            with self.assertRaises(ValueError):inspect_bundle(p)
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Local ffmpeg required')
    def test_offline_media_pipeline_with_explicit_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);movie=root/'TEST-FIXTURE.webm'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','2','-c:v','libvpx','-c:a','libopus','-live','1',str(movie)],check=True,capture_output=True)
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(movie)],text=True))
            self.assertNotIn('duration',probe['format']) # Real MediaRecorder-style unindexed input.
            bundle=root/'TEST-FIXTURE.zip'
            with zipfile.ZipFile(bundle,'w') as z:
                z.writestr('recording-manifest.json',json.dumps({'role':'A','surface':'verified_current_browser_tab','raw_recording_unedited':True,'synthetic_test_fixture':True,'markers':[]}))
                z.writestr('sanitized-observations.json',json.dumps({'call':{'role':'A'},'synthetic_test_fixture':True}))
                z.write(movie,'full-unedited-A.webm')
            result=process(bundle,root/'processed')
            self.assertLess(result['draft_duration_seconds'],2.1);self.assertFalse(result['physical_handover_verified']);self.assertTrue((root/'processed/frames/frame-start.png').exists())
            self.assertEqual((root/'processed/raw-originals/full-unedited-A.webm').read_bytes(),movie.read_bytes())
    def test_requires_matching_peer_and_surface_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('recording-manifest.json',json.dumps({'role':'A','surface':'verified_current_browser_tab','raw_recording_unedited':True}))
                z.writestr('sanitized-observations.json',json.dumps({'call':{'role':'B'}}))
                z.writestr('full-unedited-A.webm','fixture only')
            with self.assertRaises(ValueError):inspect_bundle(p)
