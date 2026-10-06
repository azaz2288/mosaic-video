from pathlib import Path
import os, re, subprocess, tempfile, time, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.common import database
from app.transcode import ffmpeg
from app.media_profiles import output_dimensions, scale_filter, master_playlist


class ProfileTests(unittest.TestCase):
    def test_output_parser_ignores_input_dimensions(self):
        log = b'Input #0, mp4\n Stream #0:0: Video: h264, yuv420p, 1920x1080, 30 fps\nOutput #0, hls\n Stream #0:0: Video: h264, yuv420p, 854x480 [SAR 1:1 DAR 427:240], 30 fps\n'
        self.assertEqual(output_dimensions(log), (854, 480))

    def test_missing_odd_audio_only_and_malformed_dimensions_fail_closed(self):
        for log in [b'', b'Input #0, mp4\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps',
                    b'Output #0, hls\n Stream #0:0: Audio: aac, 48000 Hz',
                    b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 321x181, 10 fps',
                    b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 0x2, 10 fps']:
            with self.subTest(log=log), self.assertRaises(RuntimeError): output_dimensions(log)

    def test_pid_and_language_stream_identifiers(self):
        self.assertEqual(output_dimensions(b'Output #0, hls\n Stream #0:0[0x100](und): Video: h264, yuv420p, 320x180, 10 fps'), (320,180))

    def test_filter_caps_both_dimensions_and_preserves_sar(self):
        self.assertIn("min(iw,854)", scale_filter(854,480))
        self.assertIn("min(ih,480)", scale_filter(854,480))
        self.assertNotIn('setsar', scale_filter(854,480))

    def test_master_describes_actual_frames_not_profile_names(self):
        text=master_playlist([{'profile':'480','width':270,'height':480,'bandwidth':1000000}])
        self.assertIn('RESOLUTION=270x480',text)
        self.assertIn('480/index.m3u8',text)
        self.assertNotIn('854x480',text)

    def test_old_queue_migration_is_idempotent_and_keeps_jobs(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'0'}):
            root=Path(tmp)
            with database(root) as db:
                db.execute('CREATE TABLE media_jobs(id TEXT PRIMARY KEY,video_id TEXT UNIQUE,state TEXT,error TEXT,created REAL,updated REAL)')
                db.execute("INSERT INTO media_jobs VALUES('old','video','completed','',1,2)")
            create_app(root);create_app(root)
            with database(root) as db:
                row=dict(db.execute('SELECT * FROM media_jobs').fetchone())
            self.assertEqual((row['id'],row['state'],row['updated'],row['variants_json']),('old','completed',2,'[]'))

    def test_queued_and_legacy_status_metadata(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'0'}):
            root=Path(tmp);client=TestClient(create_app(root))
            video=client.post('/api/videos',data={'title':'synthetic','category':'生活'},files={'file':('x.webm',b'\x1a\x45\xdf\xa3fixture')}).json()['id']
            status=client.get(f'/api/videos/{video}/processing').json()
            self.assertEqual(status['variants'],[]);self.assertNotIn('variants_json',status)
            with database(root) as db:db.execute("UPDATE media_jobs SET state='completed'")
            self.assertEqual(client.get(f'/api/videos/{video}/processing').json()['variants'],[])

    def test_real_wide_portrait_square_odd_and_sar_sources(self):
        exe=ffmpeg()
        if not exe:self.skipTest('FFmpeg unavailable')
        cases=[(360,640,'1',False),(1920,800,'1',False),(1080,1080,'1',False),(321,181,'1',False),(320,180,'2',False),(320,180,'1',True)]
        for width,height,sar,rotate in cases:
            with self.subTest(source=(width,height,sar)),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
                root=Path(tmp);clip=root/'clip.mp4'
                subprocess.run([exe,'-nostdin','-y','-f','lavfi','-i',f'testsrc=size={width}x{height}:rate=4','-t','0.5','-vf',f'setsar={sar}','-c:v','libx264','-pix_fmt','yuv444p',str(clip)],capture_output=True,check=True,timeout=30)
                if rotate:
                    rotated=root/'rotated.mp4'
                    subprocess.run([exe,'-nostdin','-y','-display_rotation','90','-i',str(clip),'-c','copy',str(rotated)],capture_output=True,check=True,timeout=30)
                    clip=rotated;width,height=height,width
                with TestClient(create_app(root/'state')) as client:
                    ident=client.post('/api/videos',data={'title':'Synthetic profiles','category':'创作'},files={'file':('clip.mp4',clip.read_bytes())}).json()['id']
                    for _ in range(120):
                        state=client.get(f'/api/videos/{ident}/processing').json()
                        if state['state'] in {'completed','failed'}:break
                        time.sleep(.25)
                    self.assertEqual(state['state'],'completed',state)
                    master=client.get(f'/api/videos/{ident}/assets/master.m3u8').text
                    for variant in state['variants']:
                        profile=variant['profile'];w=variant['width'];h=variant['height']
                        self.assertLessEqual(w,min(width,854 if profile=='480' else 1280))
                        self.assertLessEqual(h,min(height,int(profile)))
                        self.assertEqual((w%2,h%2),(0,0))
                        segment=root/'state'/'processed'/ident/profile/'segment00000.ts'
                        # Output is known MPEG-TS with rotation baked into frames.
                        # Pin its demuxer instead of probing a tiny 2-frame TS;
                        # still decode real pixels and verify dimensions/SAR.
                        decoded=subprocess.run([exe,'-hide_banner','-nostats','-nostdin','-f','mpegts','-i',str(segment),'-map','0:v:0','-frames:v','1','-c:v','rawvideo','-pix_fmt','rgb24','-f','rawvideo','-'],capture_output=True,check=True,timeout=30)
                        self.assertEqual(output_dimensions(decoded.stderr),(w,h))
                        self.assertEqual(len(decoded.stdout),w*h*3)
                        # Decoded display aspect agrees with source up to rounding.
                        output=decoded.stderr.decode(errors='replace').partition('Output #0,')[2]
                        match=re.search(r'SAR (\d+):(\d+)',output)
                        actual_sar=int(match[1])/int(match[2]) if match else 1
                        self.assertAlmostEqual(w/h*actual_sar,width/height*int(sar),places=3)
                        self.assertIn(f'RESOLUTION={w}x{h}',master)
                    restarted=TestClient(create_app(root/'state'))
                    self.assertEqual(restarted.get(f'/api/videos/{ident}/processing').json()['variants'],state['variants'])


if __name__=='__main__':unittest.main()
