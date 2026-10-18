from pathlib import Path
import os,subprocess,tempfile,time,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.transcode import ffmpeg

class TranscodeTests(unittest.TestCase):
    def test_real_audio_is_retained_in_deduplicated_hls(self):
        exe=ffmpeg()
        if not exe:self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);clip=root/'audio.mp4'
            subprocess.run([exe,'-nostdin','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=12',
                            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2',
                            '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(clip)],
                           capture_output=True,check=True,timeout=30)
            with TestClient(create_app(root/'state')) as client:
                ident=client.post('/api/videos',data={'title':'Original synthetic tone','category':'创作'},
                                  files={'file':('clip.mp4',clip.read_bytes())}).json()['id']
                for _ in range(120):
                    job=client.get(f'/api/videos/{ident}/processing').json()
                    if job['state'] in {'completed','failed'}:break
                    time.sleep(.25)
                self.assertEqual(job['state'],'completed',job)
                self.assertEqual(len(job['variants']),1,job['variants'])
                self.assertEqual(job['variants'][0]['deduplicated_profiles'],['720'])
                segment=root/'state'/'processed'/ident/job['artifact_id']/'480'/'segment00000.ts'
                decoder=os.environ.get('MEDIA_VERIFY_FFMPEG',exe)
                decoded=subprocess.run([decoder,'-nostdin','-f','mpegts','-i',str(segment),
                                        '-map','0:a:0','-t','0.5','-c:a','pcm_s16le','-f','s16le','-'],
                                       capture_output=True,timeout=30)
                self.assertEqual(decoded.returncode,0,decoded.stderr.decode(errors='replace')[-4000:])
                self.assertGreater(len(decoded.stdout),1000)

    def test_real_low_resolution_video_publishes_one_byte_identical_rendition(self):
        exe=ffmpeg()
        if not exe:self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);clip=root/'clip.mp4'
            subprocess.run([exe,'-nostdin','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],capture_output=True,check=True,timeout=30)
            with TestClient(create_app(root/'state')) as client:
                video=client.post('/api/videos',data={'title':'Real media','category':'创作'},files={'file':('clip.mp4',clip.read_bytes())}).json()
                for _ in range(120):
                    state=client.get('/api/videos/'+video['id']+'/processing').json()
                    if state['state'] in {'completed','failed'}:break
                    time.sleep(.25)
                self.assertEqual(state['state'],'completed',state)
                self.assertEqual(client.get('/api/videos/'+video['id']+'/assets/poster.jpg').status_code,200)
                self.assertEqual(len(state['variants']),1,state['variants'])
                variant=state['variants'][0]
                self.assertEqual((variant['profile'],variant['width'],variant['height']),('480',320,180))
                self.assertEqual(variant['deduplicated_profiles'],['720'])
                self.assertEqual(variant['deduplication_source'],'sha256-vod-bytes-v1')
                self.assertGreater(variant['deduplicated_bytes'],0)
                self.assertIn('#EXTM3U',client.get('/api/videos/'+video['id']+'/assets/480/index.m3u8').text)
                self.assertEqual(client.get('/api/videos/'+video['id']+'/assets/720/index.m3u8').status_code,404)
                master=client.get('/api/videos/'+video['id']+'/assets/master.m3u8').text
                self.assertEqual(master.count('RESOLUTION=320x180'),1)
                artifact=root/'state'/'processed'/video['id']/state['artifact_id']
                self.assertEqual(sorted(p.name for p in artifact.iterdir()),['480','master.m3u8','poster.jpg'])
                self.assertEqual(client.get('/api/videos/'+video['id']+'/assets/../../app.db').status_code,404)

if __name__=='__main__':unittest.main()
