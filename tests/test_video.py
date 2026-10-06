from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app

WEBM=b'\x1a\x45\xdf\xa3'+b'container fixture only'*20


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.client=TestClient(create_app(self.root))
    def tearDown(self): self.tmp.cleanup()
    def upload(self,name='clip.webm',raw=WEBM):
        return self.client.post('/api/videos',data={'title':'测试作品','category':'科技'},files={'file':(name,raw,'video/webm')})
    def test_upload_and_restart_persistence(self):
        response=self.upload();self.assertEqual(response.status_code,201)
        ident=response.json()['id']
        other=TestClient(create_app(self.root))
        self.assertEqual(other.get('/api/videos/'+ident).json()['title'],'测试作品')
    def test_range_playback_and_random_name(self):
        video=self.upload('../../clip.webm').json()
        response=self.client.get('/api/videos/'+video['id']+'/media',headers={'Range':'bytes=0-3'})
        self.assertEqual(response.status_code,206);self.assertEqual(response.content,WEBM[:4])
        self.assertEqual(video['filename'],video['id']+'.webm')
    def test_reject_invalid_container(self):
        self.assertEqual(self.upload(raw=b'<script>bad</script>').status_code,400)
        self.assertEqual(list((self.root/'media').iterdir()),[])
    def test_reject_extension_and_category(self):
        self.assertEqual(self.upload(name='clip.exe').status_code,400)
        response=self.client.post('/api/videos',data={'title':'a','category':'invalid'},files={'file':('clip.webm',WEBM)})
        self.assertEqual(response.status_code,400)
    def test_like_favorite_and_filter(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.client.post('/api/videos/'+ident+'/interaction/favorite').json()['favorite'],1)
        self.assertEqual(len(self.client.get('/api/videos?favorites=true').json()),1)
        self.assertEqual(self.client.post('/api/videos/'+ident+'/interaction/favorite').json()['favorite'],0)
        self.assertEqual(self.client.get('/api/videos?favorites=true').json(),[])
    def test_comments_persist_and_blank_rejected(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.client.post('/api/videos/'+ident+'/comments',json={'text':'hello'}).status_code,201)
        self.assertEqual(self.client.get('/api/videos/'+ident+'/comments').json()[0]['text'],'hello')
        self.assertEqual(self.client.post('/api/videos/'+ident+'/comments',json={'text':'   '}).status_code,400)
    def test_danmaku_time_validation(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.client.post('/api/videos/'+ident+'/danmaku',json={'text':'hi','at':2}).status_code,201)
        self.assertEqual(self.client.get('/api/videos/'+ident+'/danmaku').json()[0]['at'],2)
        self.assertEqual(self.client.post('/api/videos/'+ident+'/danmaku',json={'text':'hi','at':-1}).status_code,422)
    def test_search_and_unknown(self):
        self.upload()
        self.assertEqual(len(self.client.get('/api/videos?q=测试&category=科技').json()),1)
        self.assertEqual(self.client.get('/api/videos?q=missing').json(),[])
        self.assertEqual(self.client.get('/api/videos/unknown').status_code,404)
    def test_cross_site_blocked(self):
        self.assertEqual(self.client.post('/api/videos/x/interaction/like',headers={'Origin':'https://evil.example'}).status_code,403)


if __name__=='__main__':unittest.main()
