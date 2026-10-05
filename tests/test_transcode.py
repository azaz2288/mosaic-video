from pathlib import Path
import os,subprocess,tempfile,time,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.transcode import ffmpeg

class TranscodeTests(unittest.TestCase):
    def test_real_video_generates_thumbnail_and_two_hls_variants(self):
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
                for height in (480,720):self.assertIn('#EXTM3U',client.get('/api/videos/'+video['id']+f'/assets/{height}/index.m3u8').text)
                self.assertEqual(client.get('/api/videos/'+video['id']+'/assets/../../app.db').status_code,404)

if __name__=='__main__':unittest.main()
