def synthetic_password(suffix):
    return '-'.join(['synthetic','pass',suffix])

from pathlib import Path
import os,tempfile,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.common import database

class AccountTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'MEDIA_WORKER':'0'});self.env.start()
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.app=create_app(self.root);self.a=TestClient(self.app);self.b=TestClient(self.app)
        self.a.post('/api/auth/register',json={'username':'alice','password':synthetic_password('123')})
        self.b.post('/api/auth/register',json={'username':'bobby','password':synthetic_password('456')})
    def tearDown(self):self.tmp.cleanup();self.env.stop()
    def video(self):return self.a.post('/api/videos',data={'title':'clip','category':'生活'},files={'file':('clip.webm',b'\x1a\x45\xdf\xa3'+b'fixture'*20)}).json()['id']
    def test_session_and_password_are_not_plaintext(self):
        self.assertEqual(self.a.get('/api/auth/me').json()['username'],'alice')
        with database(self.root) as db:self.assertNotIn('synthetic-pass',db.execute('SELECT password FROM users LIMIT 1').fetchone()[0])
        self.a.post('/api/auth/logout');self.assertEqual(self.a.get('/api/auth/me').json()['id'],'local')
        self.assertEqual(self.a.post('/api/auth/login',json={'username':'alice','password':'wrong-pass-123'}).status_code,401)
    def test_other_user_cannot_edit_and_favorites_are_private(self):
        ident=self.video()
        self.assertEqual(self.b.patch('/api/community/videos/'+ident,json={'title':'hijack'}).status_code,403)
        self.a.post('/api/videos/'+ident+'/interaction/favorite')
        self.assertEqual(len(self.a.get('/api/videos?favorites=true').json()),1)
        self.assertEqual(self.b.get('/api/videos?favorites=true').json(),[])
    def test_dedup_and_soft_delete(self):
        ident=self.video();self.assertEqual(self.video(),ident)
        self.assertEqual(self.a.delete('/api/community/videos/'+ident).status_code,200)
        self.assertEqual(self.a.get('/api/videos/'+ident).status_code,404)
        self.assertEqual(self.a.get('/api/community/hidden').json()[0]['id'],ident)
        self.assertEqual(self.b.get('/api/community/hidden').json(),[])
        self.assertEqual(self.b.get('/api/videos/'+ident+'/assets/master.m3u8').status_code,404)
        self.assertEqual(self.a.post('/api/community/videos/'+ident+'/restore').status_code,200)
    def test_history_collections_and_notifications(self):
        ident=self.video();self.b.post('/api/community/videos/'+ident+'/history?position=5')
        self.assertEqual(self.b.get('/api/community/history').json()[0]['position'],5)
        collection=self.b.post('/api/community/collections',json={'name':'favorites'}).json()['id']
        self.assertEqual(self.a.post('/api/community/collections/'+collection+'/'+ident).status_code,403)
        self.assertEqual(self.b.post('/api/community/collections/'+collection+'/'+ident).status_code,200)
        self.b.post('/api/videos/'+ident+'/comments',json={'text':'great'})
        self.assertEqual(len(self.a.get('/api/community/notifications').json()),1)
    def test_report_and_follow(self):
        ident=self.video();author=self.a.get('/api/auth/me').json()['id']
        self.assertTrue(self.b.post('/api/community/authors/'+author+'/follow').json()['following'])
        self.b.post('/api/community/videos/'+ident+'/report',json={'text':'review'})
        report=self.a.get('/api/community/reports').json()[0]
        self.assertEqual(self.b.post('/api/community/reports/'+report['id']+'/resolve').status_code,403)
        self.assertEqual(self.a.post('/api/community/reports/'+report['id']+'/resolve').status_code,200)

if __name__=='__main__':unittest.main()
