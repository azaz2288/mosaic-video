"""Synthetic-only queue cancellation, publication and real child boundaries."""
from pathlib import Path
from contextlib import contextmanager
import os, sqlite3, sys, tempfile, threading, time, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.common import database


def synthetic_output(command, text='synthetic'):
    output=Path(command[-1])
    if output.suffix=='.m3u8':
        (output.parent/'segment00000.ts').write_bytes(b'x'*188)
        output.write_text('#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXTINF:1.000000,\nsegment00000.ts\n#EXT-X-ENDLIST\n',encoding='ascii')
    else:output.write_text(text,encoding='utf-8')


class MediaControlTests(unittest.TestCase):
    def upload(self, client):
        return client.post('/api/videos', data={'title':'Synthetic control','category':'创作'},
                           files={'file':('fixture.webm',b'\x1a\x45\xdf\xa3control')}).json()['id']

    def test_queued_cancel_is_idempotent_persistent_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MEDIA_WORKER':'0'}):
            root=Path(tmp);client=TestClient(create_app(root));ident=self.upload(client)
            route=f'/api/videos/{ident}/processing'
            self.assertEqual(client.post(route+'/cancel').status_code,200)
            self.assertEqual(client.post(route+'/cancel').status_code,200)
            self.assertEqual(client.get(route).json()['state'],'cancelled')
            restarted=TestClient(create_app(root))
            self.assertEqual(restarted.get(route).json()['state'],'cancelled')
            self.assertEqual(restarted.get(f'/api/videos/{ident}/media').status_code,200)
            self.assertEqual(restarted.post(f'/api/community/videos/{ident}/retry').status_code,200)
            self.assertEqual(restarted.get(route).json()['state'],'queued')

    def test_cancel_permissions_cross_origin_and_active_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MEDIA_WORKER':'0'}):
            client=TestClient(create_app(Path(tmp)));other=TestClient(client.app)
            client.post('/api/auth/register',json={'username':'owner','password':'-'.join(['synthetic','owner','test'])})
            other.post('/api/auth/register',json={'username':'other','password':'-'.join(['synthetic','other','test'])})
            ident=self.upload(client);route=f'/api/videos/{ident}/processing/cancel'
            self.assertEqual(other.post(route).status_code,403)
            self.assertEqual(client.post(route,headers={'Origin':'https://invalid.example'}).status_code,403)
            for state in ('queued','running'):
                with database(Path(tmp)) as db:db.execute('UPDATE media_jobs SET state=?',(state,))
                self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,409)
            self.assertEqual(client.post(route).json()['state'],'cancelling')
            self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,409)
            create_app(Path(tmp))
            self.assertEqual(client.get(f'/api/videos/{ident}/processing').json()['state'],'cancelled')

    def test_unpublished_assets_are_not_served_and_completed_cancel_refused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MEDIA_WORKER':'0'}):
            root=Path(tmp);client=TestClient(create_app(root));ident=self.upload(client)
            target=root/'processed'/ident;target.mkdir();(target/'poster.jpg').write_bytes(b'synthetic')
            for state in ('queued','running','failed','cancelling','cancelled'):
                with database(root) as db:db.execute('UPDATE media_jobs SET state=?',(state,))
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/poster.jpg').status_code,404)
            with database(root) as db:db.execute("UPDATE media_jobs SET state='completed'")
            self.assertEqual(client.get(f'/api/videos/{ident}/assets/poster.jpg').status_code,200)
            self.assertEqual(client.post(f'/api/videos/{ident}/processing/cancel').status_code,409)

    def test_real_child_timeout_and_cancel_are_reaped(self):
        from app.media_process import run_process, MediaCancelled, MediaDeadline
        for kind in ('cancel','timeout'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                marker=Path(tmp)/'started';stop=threading.Event();children=[]
                command=[sys.executable,'-c','import pathlib,time;pathlib.Path(__import__("sys").argv[1]).touch();time.sleep(60)',str(marker)]
                def check():
                    if stop.is_set():raise MediaCancelled()
                def signal():
                    until=time.monotonic()+5
                    while not marker.exists() and time.monotonic()<until:time.sleep(.01)
                    stop.set()
                thread=threading.Thread(target=signal) if kind=='cancel' else None
                if thread:thread.start()
                import subprocess
                original=subprocess.Popen
                def track(*args,**kwargs):
                    child=original(*args,**kwargs);children.append(child);return child
                started=time.monotonic()
                with patch('app.media_process.subprocess.Popen',side_effect=track):
                    with self.assertRaises(MediaCancelled if kind=='cancel' else MediaDeadline):
                        run_process(command,time.monotonic()+(10 if thread else .4),check)
                if thread:thread.join(6)
                self.assertTrue(children);self.assertIsNotNone(children[0].poll())
                self.assertLess(time.monotonic()-started,6)

    def test_shared_deadline_across_calls_and_post_exit_check(self):
        from app.media_process import run_process, MediaCancelled, MediaDeadline
        deadline=time.monotonic()+.6
        command=[sys.executable,'-c','import time;time.sleep(.4)']
        run_process(command,deadline,lambda:None)
        with self.assertRaises(MediaDeadline):run_process(command,deadline,lambda:None)
        calls=[]
        def cancel_after_exit():
            calls.append(1)
            if len(calls)>1:raise MediaCancelled()
        with self.assertRaises(MediaCancelled):run_process([sys.executable,'-c','pass'],time.monotonic()+5,cancel_after_exit)

    def wait_job(self,client,ident,states):
        until=time.monotonic()+10
        while time.monotonic()<until:
            job=client.get(f'/api/videos/{ident}/processing').json()
            if job['state'] in states:return job
            time.sleep(.025)
        self.fail(f'timed out waiting for {states}: {job}')

    def test_running_cancel_reaps_child_and_discards_staging(self):
        from app.media_process import run_process
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);marker=root/'started'
            def slow(command,deadline,check):
                return run_process([sys.executable,'-c','import pathlib,time;pathlib.Path(__import__("sys").argv[1]).touch();time.sleep(60)',str(marker)],deadline,check)
            with patch('app.transcode.run_process',side_effect=slow),TestClient(create_app(root/'state')) as client:
                ident=self.upload(client);self.wait_job(client,ident,{'running'})
                until=time.monotonic()+5
                while not marker.exists() and time.monotonic()<until:time.sleep(.01)
                self.assertTrue(marker.exists())
                self.assertEqual(client.post(f'/api/videos/{ident}/processing/cancel').json()['state'],'cancelling')
                self.assertEqual(self.wait_job(client,ident,{'cancelled'})['variants'],[])
                self.assertEqual(client.get(f'/api/videos/{ident}/media').status_code,200)
            self.assertEqual(list((root/'state'/'processed'/ident).iterdir()),[])

    def test_shutdown_reaps_running_child_and_requeues(self):
        from app.media_process import run_process
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);marker=root/'started'
            def slow(command,deadline,check):
                return run_process([sys.executable,'-c','import pathlib,time;pathlib.Path(__import__("sys").argv[1]).touch();time.sleep(60)',str(marker)],deadline,check)
            with patch('app.transcode.run_process',side_effect=slow):
                with TestClient(create_app(root/'state')) as client:
                    ident=self.upload(client);self.wait_job(client,ident,{'running'})
                    until=time.monotonic()+5
                    while not marker.exists() and time.monotonic()<until:time.sleep(.01)
                    self.assertTrue(marker.exists())
            with database(root/'state') as db:self.assertEqual(db.execute('SELECT state FROM media_jobs').fetchone()[0],'queued')
            self.assertEqual(list((root/'state'/'processed'/ident).iterdir()),[])

    def test_cancel_after_final_encode_cannot_publish_and_total_timeout_is_sanitized(self):
        from app.media_process import MediaDeadline
        for failure in ('cancel','timeout','io'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
                root=Path(tmp);calls=[]
                def encode(command,deadline,check):
                    calls.append(deadline);synthetic_output(command)
                    if failure=='timeout' and len(calls)==2:raise MediaDeadline()
                    if failure=='io' and len(calls)==2:raise OSError('private path must not escape')
                    if failure=='cancel' and len(calls)==3:
                        with database(root) as db:db.execute("UPDATE media_jobs SET state='cancelling'")
                    return b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps'
                with patch('app.transcode.run_process',side_effect=encode),TestClient(create_app(root)) as client:
                    ident=self.upload(client);job=self.wait_job(client,ident,{'cancelled','failed'})
                    self.assertEqual(job['state'],'cancelled' if failure=='cancel' else 'failed')
                    self.assertEqual(job['variants'],[]);self.assertEqual(job['artifact_id'],'')
                    self.assertNotIn('private path',job['error']);self.assertNotIn(str(root),job['error'])
                    self.assertEqual(client.get(f'/api/videos/{ident}/assets/master.m3u8').status_code,404)
                    self.assertEqual(list((root/'processed'/ident).iterdir()),[])
                    self.assertEqual(len(set(calls)),1)

    def test_budget_validation_and_log_limit(self):
        from app.media_process import run_process
        for value in ('0','3601','nan','1.5','-1','１２'):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'0','MEDIA_JOB_TIMEOUT_SECONDS':value}):
                with self.assertRaises(ValueError):create_app(Path(tmp))
        with self.assertRaisesRegex(RuntimeError,'读取预算'):
            run_process([sys.executable,'-c','import sys;sys.stderr.write("x"*300000)'],time.monotonic()+5,lambda:None)

    def test_retry_preserves_prior_artifact_and_publishes_unique_complete_directory(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'0'}):
            root=Path(tmp);app=create_app(root);client=TestClient(app);ident=self.upload(client)
            prior='a'*32;old=root/'processed'/ident/prior;old.mkdir(parents=True)
            (old/'poster.jpg').write_bytes(b'prior synthetic output')
            with database(root) as db:db.execute("UPDATE media_jobs SET state='completed',artifact_id=?",(prior,))
            route=f'/api/videos/{ident}'
            self.assertEqual(client.get(route+'/assets/poster.jpg').content,b'prior synthetic output')
            self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,200)
            self.assertEqual(client.get(route+'/assets/poster.jpg').status_code,404)
            client.post(route+'/processing/cancel')
            self.assertEqual((old/'poster.jpg').read_bytes(),b'prior synthetic output')
            self.assertEqual(client.get(route+'/media').status_code,200)
            self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,200)
            def encode(command,deadline,check):
                synthetic_output(command,'new synthetic output')
                return b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps'
            with patch.dict(os.environ,{'MEDIA_WORKER':'1'}),patch('app.transcode.run_process',side_effect=encode),TestClient(app) as active:
                job=self.wait_job(active,ident,{'completed'})
                self.assertEqual(job['artifact_id'],job['id']);self.assertNotEqual(job['artifact_id'],prior)
                self.assertEqual(active.get(route+'/assets/poster.jpg').text,'new synthetic output')
                self.assertEqual(active.get(route+f'/assets/{prior}/poster.jpg').status_code,404)
            self.assertEqual((old/'poster.jpg').read_bytes(),b'prior synthetic output')
            self.assertFalse(any(p.name.startswith('.work-') for p in old.parent.iterdir()))

    def test_database_publication_rollback_is_hidden_and_worker_continues(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);faults=[]
            @contextmanager
            def fail_publication_once(path):
                with database(path) as db:
                    yield db
                    if not faults and db.execute("SELECT 1 FROM media_jobs WHERE state='completed'").fetchone():
                        faults.append(1)
                        raise sqlite3.OperationalError('synthetic private commit failure')
            def encode(command,deadline,check):
                synthetic_output(command)
                return b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps'
            with patch('app.transcode.database',side_effect=fail_publication_once),patch('app.transcode.run_process',side_effect=encode),TestClient(create_app(root)) as client:
                ident=self.upload(client);job=self.wait_job(client,ident,{'failed'})
                self.assertEqual(faults,[1]);self.assertEqual(job['artifact_id'],'')
                self.assertEqual(job['variants'],[]);self.assertNotIn('private',job['error'])
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/poster.jpg').status_code,404)
                orphan=root/'processed'/ident/job['id']
                self.assertTrue((orphan/'poster.jpg').is_file())
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/{job["id"]}/poster.jpg').status_code,404)
                self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,200)
                completed=self.wait_job(client,ident,{'completed'})
                self.assertNotEqual(completed['artifact_id'],job['id'])
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/poster.jpg').status_code,200)
                self.assertTrue(orphan.exists())  # No automatic orphan deletion / GC claim.


if __name__=='__main__':unittest.main()
