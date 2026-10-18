"""Exact generated-VOD identities; equal size/resolution is not equality."""
from pathlib import Path
import hashlib, os, tempfile, time, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.common import database
from app.main import create_app
from app.media_bandwidth import measure_playlist, hash_segment, fingerprint
from app.media_process import MediaCancelled, MediaDeadline
from test_media_bandwidth import fixture
import test_media_control as control


class DedupTests(unittest.TestCase):
    def measure(self,path,check=lambda:None):
        return measure_playlist(path,time.monotonic()+10,check)

    def test_domain_length_framed_digest_matches_independent_byte_concatenation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=fixture(folder,('4','1'),(37,19),4)
            data=path.read_bytes();parts=[b'sha256-vod-bytes-v1\0',len(data).to_bytes(8,'big'),data]
            total=len(data)
            for name in ('segment00000.ts','segment00001.ts'):
                encoded=name.encode('ascii');content=(folder/name).read_bytes()
                parts += [len(encoded).to_bytes(8,'big'),encoded,len(content).to_bytes(8,'big'),content]
                total+=len(content)
            result=self.measure(path)
            self.assertEqual(result['content_sha256'],hashlib.sha256(b''.join(parts)).hexdigest())
            self.assertEqual(result['output_bytes'],total)
            self.assertEqual(result['content_digest_source'],'sha256-vod-bytes-v1')

    def test_directory_independent_and_repaired_manifest_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            left=Path(tmp)/'480';right=Path(tmp)/'720';left.mkdir();right.mkdir()
            a=self.measure(fixture(left,('0.5',),(188,),0))
            b=self.measure(fixture(right,('0.5',),(188,),1))
            self.assertEqual(a['content_sha256'],b['content_sha256'])
            self.assertEqual(a['output_bytes'],b['output_bytes'])

    def test_same_size_changed_byte_and_same_total_repartition_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=fixture(folder,('4','4'),(32,32),4)
            original=self.measure(path)['content_sha256']
            for pos in (0,16,31):
                fixture(folder,('4','4'),(32,32),4)
                content=bytearray(b'x'*32);content[pos]=ord('y')
                (folder/'segment00001.ts').write_bytes(content)
                self.assertNotEqual(self.measure(path)['content_sha256'],original)
            self.assertNotEqual(self.measure(fixture(folder,('4','4'),(31,33),4))['content_sha256'],original)
            self.assertNotEqual(self.measure(fixture(folder,('3','4'),(32,32),4))['content_sha256'],original)

    def test_streamed_hash_many_chunks_and_cancel_or_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'segment00000.ts';data=b'original synthetic segment'*200;path.write_bytes(data)
            calls=[]
            with patch('app.media_bandwidth.HASH_CHUNK_BYTES',17):
                digest=hashlib.sha256();hash_segment(digest,path,fingerprint(path),lambda:calls.append(1))
                self.assertEqual(digest.hexdigest(),hashlib.sha256(data).hexdigest())
                self.assertGreater(len(calls),len(data)//17)
                for exception in (MediaCancelled,MediaDeadline):
                    steps=[]
                    def stop():
                        steps.append(1)
                        if len(steps)==4:raise exception()
                    with self.assertRaises(exception):hash_segment(hashlib.sha256(),path,fingerprint(path),stop)

    def test_read_time_truncate_grow_and_replace_refused(self):
        for mutation in ('truncate','grow','replace'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'segment00000.ts';path.write_bytes(b'x'*100);initial=fingerprint(path);calls=[]
                def change():
                    calls.append(1)
                    if len(calls)==3:
                        if mutation=='replace':
                            replacement=path.parent/'replacement.ts';replacement.write_bytes(b'x'*100)
                            # Windows cannot rename over an open file: changing the
                            # path after close is checked separately below.
                            if os.name=='nt':return
                            os.replace(replacement,path)
                        else:path.write_bytes(b'x'*(10 if mutation=='truncate' else 150))
                if mutation=='replace' and os.name=='nt':
                    replacement=path.parent/'replacement.ts';replacement.write_bytes(b'x'*100)
                    os.replace(replacement,path)
                with patch('app.media_bandwidth.HASH_CHUNK_BYTES',17),self.assertRaises((RuntimeError,OSError)):
                    hash_segment(hashlib.sha256(),path,initial,change)

    def test_earlier_segment_changed_while_later_hashed_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=fixture(folder,('4','1'),(37,19),4)
            def mutate(digest,segment,info,checkpoint):
                hash_segment(digest,segment,info,checkpoint)
                if segment.name=='segment00001.ts':(folder/'segment00000.ts').write_bytes(b'y'*37)
            with patch('app.media_bandwidth.hash_segment',side_effect=mutate),self.assertRaises(RuntimeError):self.measure(path)

    def run_synthetic(self,root,kind,client):
        def encode(command,deadline,check):
            control.synthetic_output(command)
            output=Path(command[-1]);high='1280' in str(command)
            if output.suffix=='.m3u8' and high:
                if kind=='bytes':(output.parent/'segment00000.ts').write_bytes(b'y'*188)
                if kind=='timing':output.write_text(output.read_text().replace('1.000000','0.900000'))
            size='640x360' if high and kind=='dimensions' else '320x180'
            return f'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, {size}, 10 fps'.encode()
        with patch('app.transcode.run_process',side_effect=encode):
            ident=control.MediaControlTests().upload(client)
            job=control.MediaControlTests().wait_job(client,ident,{'completed','failed'})
        self.assertEqual(job['state'],'completed',job)
        return ident,job

    def test_identical_bytes_merge_persist_and_no_duplicate_asset(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp)
            with TestClient(create_app(root)) as client:
                ident,job=self.run_synthetic(root,'identical',client)
                self.assertEqual(len(job['variants']),1)
                variant=job['variants'][0]
                self.assertEqual(variant['deduplicated_profiles'],['720'])
                self.assertEqual(variant['deduplicated_bytes'],variant['output_bytes'])
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/720/index.m3u8').status_code,404)
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/master.m3u8').text.count('#EXT-X-STREAM-INF'),1)
                self.assertEqual(sorted(p.name for p in (root/'processed'/ident/job['artifact_id']).iterdir()),['480','master.m3u8','poster.jpg'])
            with patch.dict(os.environ,{'MEDIA_WORKER':'0'}),TestClient(create_app(root)) as restarted:
                self.assertEqual(restarted.get(f'/api/videos/{ident}/processing').json()['variants'],job['variants'])

    def test_same_dimensions_different_bytes_or_timing_and_different_dimensions_keep_both(self):
        for kind in ('bytes','timing','dimensions'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
                root=Path(tmp)
                with TestClient(create_app(root)) as client:
                    ident,job=self.run_synthetic(root,kind,client)
                    self.assertEqual([v['profile'] for v in job['variants']],['480','720'])
                    self.assertTrue(all('deduplicated_profiles' not in v for v in job['variants']))
                    self.assertEqual(client.get(f'/api/videos/{ident}/assets/master.m3u8').text.count('#EXT-X-STREAM-INF'),2)
                    self.assertEqual(client.get(f'/api/videos/{ident}/assets/720/index.m3u8').status_code,200)

    def test_cancel_timeout_and_io_during_second_digest_never_publish(self):
        for failure in ('cancel','timeout','io'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
                root=Path(tmp);calls=[]
                def digest(*args):
                    calls.append(1)
                    if len(calls)==2:
                        if failure=='cancel':
                            with database(root) as db:db.execute("UPDATE media_jobs SET state='cancelling'")
                            args[-1]()
                        if failure=='timeout':raise MediaDeadline()
                        if failure=='io':raise OSError('synthetic private path')
                    return hash_segment(*args)
                def encode(command,deadline,check):
                    control.synthetic_output(command)
                    return b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps'
                with patch('app.media_bandwidth.hash_segment',side_effect=digest),patch('app.transcode.run_process',side_effect=encode),TestClient(create_app(root)) as client:
                    ident=control.MediaControlTests().upload(client)
                    job=control.MediaControlTests().wait_job(client,ident,{'cancelled','failed'})
                    self.assertEqual(job['state'],'cancelled' if failure=='cancel' else 'failed')
                    self.assertEqual(job['variants'],[]);self.assertEqual(job['artifact_id'],'')
                    self.assertNotIn('private',job['error']);self.assertNotIn(str(root),job['error'])
                    self.assertEqual(list((root/'processed'/ident).iterdir()),[])
                    self.assertEqual(client.get(f'/api/videos/{ident}/media').status_code,200)
                    self.assertEqual(client.get(f'/api/videos/{ident}/assets/master.m3u8').status_code,404)


if __name__=='__main__':unittest.main()
