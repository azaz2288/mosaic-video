"""Original synthetic segments and independent exact window oracles."""
from pathlib import Path
from fractions import Fraction
import math, os, tempfile, time, unittest
from unittest.mock import patch
from test_support import bootstrap
from app.media_bandwidth import measure_playlist
from app.media_process import MediaCancelled, MediaDeadline


def fixture(folder, durations=('4','4','1'), sizes=(100,400,90), target=4):
    rows=['#EXTM3U','#EXT-X-VERSION:3',f'#EXT-X-TARGETDURATION:{target}',
          '#EXT-X-MEDIA-SEQUENCE:0','#EXT-X-PLAYLIST-TYPE:VOD']
    for i,(duration,size) in enumerate(zip(durations,sizes)):
        name=f'segment{i:05d}.ts'
        (folder/name).write_bytes(b'x'*size)
        rows += [f'#EXTINF:{duration},',name]
    rows += ['#EXT-X-ENDLIST']
    path=folder/'index.m3u8';path.write_text('\n'.join(rows)+'\n',encoding='ascii')
    return path


class BandwidthTests(unittest.TestCase):
    def measure(self, path, check=lambda:None):
        return measure_playlist(path,time.monotonic()+10,check)

    def test_exact_contiguous_window_oracle_and_average(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            # Small hot tail is not a qualifying individual window.
            durations=['2','3','1'];sizes=[11,31,30]
            result=self.measure(fixture(folder,durations,sizes,4))
            rates=[]
            for start in range(3):
                for end in range(start+1,4):
                    duration=sum(map(Fraction,durations[start:end]))
                    if Fraction(2)<=duration<=Fraction(6):
                        rates.append(Fraction(8*sum(sizes[start:end]),1)/duration)
            self.assertEqual(result['bandwidth'],math.ceil(max(rates)))
            self.assertEqual(result['average_bandwidth'],math.ceil(Fraction(8*sum(sizes),6)))
            self.assertEqual(result['bandwidth_source'],'measured-segment-windows-v1')
            self.assertEqual(result['segment_count'],3)
            self.assertEqual(result['bandwidth_window'],'target-duration')

    def test_fractional_boundary_and_short_ffmpeg_target_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(Path(tmp),['0.500000'],[188],0)
            result=self.measure(path)
            self.assertEqual(result['bandwidth'],3008)
            self.assertIn('#EXT-X-TARGETDURATION:1\n',path.read_text())
            self.assertEqual(result['bandwidth_window'],'target-duration')
            result=self.measure(fixture(Path(tmp),['0.250000'],[189],0))
            self.assertEqual(result['bandwidth'],6048)
            self.assertEqual(result['bandwidth_window'],'short-vod-single-segment')

    def test_malformed_and_unsupported_playlists_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);original=fixture(folder).read_text()
            bad=[original.replace('#EXTM3U','#bad'),original.replace('#EXT-X-ENDLIST',''),
                 original.replace('#EXT-X-TARGETDURATION:4','#EXT-X-TARGETDURATION:0'),
                 original.replace('#EXT-X-TARGETDURATION:4','#EXT-X-TARGETDURATION:-1'),
                 original.replace('#EXTINF:4,','#EXTINF:nan,'),
                 original.replace('#EXTINF:4,','#EXTINF:0,'),
                 original.replace('#EXTINF:4,','#EXTINF:-1,'),
                 original.replace('#EXTINF:4,','#EXTINF:1e3,'),
                 original.replace('#EXTINF:4,','#EXTINF:6,'),
                 original.replace('#EXT-X-ENDLIST','#EXT-X-KEY:METHOD=AES-128\n#EXT-X-ENDLIST'),
                 original.replace('segment00001.ts','segment00000.ts'),
                 original.replace('segment00000.ts\n',''),original+'segment00003.ts\n',
                 original.replace('#EXT-X-VERSION:3','#EXT-X-VERSION:3\n#EXT-X-VERSION:3')]
            for text in bad:
                with self.subTest(text=text):
                    path=folder/'index.m3u8';path.write_text(text)
                    with self.assertRaises(RuntimeError):self.measure(path)

    def test_external_traversal_encoded_and_nested_uris_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);original=fixture(folder).read_text()
            for name in ('../segment00000.ts','https://invalid.example/a.ts','/a.ts',
                         'C:\\a.ts','%73egment00000.ts','sub/segment00000.ts',
                         'segment00000.ts?x=1','segment00000.ts#fragment'):
                with self.subTest(uri=name):
                    path=folder/'index.m3u8';path.write_text(original.replace('segment00000.ts',name))
                    with self.assertRaises(RuntimeError):self.measure(path)

    def test_missing_empty_and_directory_segments_rejected(self):
        for kind in ('missing','empty','directory'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);path=fixture(folder);segment=folder/'segment00000.ts'
                segment.unlink()
                if kind=='empty':segment.touch()
                if kind=='directory':segment.mkdir()
                with self.assertRaises((RuntimeError,OSError)):self.measure(path)

    def test_playlist_and_count_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=fixture(folder)
            with patch('app.media_bandwidth.MAX_PLAYLIST_BYTES',10):
                with self.assertRaises(RuntimeError):self.measure(path)
            with patch('app.media_bandwidth.MAX_SEGMENTS',2):
                with self.assertRaises(RuntimeError):self.measure(path)

    def test_cancel_deadline_and_observed_file_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=fixture(folder)
            def cancel():raise MediaCancelled()
            with self.assertRaises(MediaCancelled):self.measure(path,cancel)
            with self.assertRaises(MediaDeadline):measure_playlist(path,time.monotonic()-1,lambda:None)
            calls=[]
            def mutate():
                calls.append(1)
                if len(calls)==17:(folder/'segment00000.ts').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):self.measure(path,mutate)

    def test_symlink_and_linked_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'real';folder.mkdir();path=fixture(folder)
            segment=folder/'segment00000.ts';segment.unlink()
            outside=root/'outside.ts';outside.write_bytes(b'outside')
            try:segment.symlink_to(outside)
            except OSError:self.skipTest('symlink permission unavailable')
            with self.assertRaises(RuntimeError):self.measure(path)
            segment.unlink();segment.write_bytes(b'real')
            link=root/'linked';link.symlink_to(folder,target_is_directory=True)
            with self.assertRaises(RuntimeError):self.measure(link/'index.m3u8')

    @unittest.skipUnless(os.name=='nt','Windows junction boundary')
    def test_windows_junction_parent_rejected(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'real';folder.mkdir();fixture(folder)
            link=root/'linked'
            result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(folder)],capture_output=True)
            self.assertEqual(result.returncode,0)
            try:
                with self.assertRaises(RuntimeError):self.measure(link/'index.m3u8')
            finally:link.rmdir()  # Only the synthetic junction, never its target.

    def test_playlist_observed_change_and_cancel_during_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(Path(tmp));calls=[]
            def mutate():
                calls.append(1)
                if len(calls)==17:path.write_text(path.read_text()+'\n')
            with self.assertRaises(RuntimeError):self.measure(path,mutate)
            path=fixture(Path(tmp));calls=[]
            def cancel():
                calls.append(1)
                if len(calls)==17:raise MediaCancelled()
            with self.assertRaises(MediaCancelled):self.measure(path,cancel)

    def test_seeded_independent_window_oracle(self):
        import random
        rng=random.Random(8216)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for _ in range(60):
                count=rng.randint(1,15)
                durations=[str(rng.randint(1,8)/2) for i in range(count)]
                sizes=[rng.randint(1,10000) for i in range(count)]
                rates=[]
                for start in range(count):
                    for end in range(start+1,count+1):
                        duration=sum(map(Fraction,durations[start:end]))
                        if 2<=duration<=6:rates.append(Fraction(8*sum(sizes[start:end]),1)/duration)
                if not rates:rates=[Fraction(8*s,1)/Fraction(d) for s,d in zip(sizes,durations)]
                result=self.measure(fixture(folder,durations,sizes,4))
                self.assertEqual(result['bandwidth'],math.ceil(max(rates)))
                self.assertEqual(result['average_bandwidth'],math.ceil(Fraction(8*sum(sizes),1)/sum(map(Fraction,durations))))

    def test_real_ffmpeg_multisegment_with_short_tail(self):
        import re, subprocess
        from app.transcode import ffmpeg
        exe=ffmpeg()
        if not exe:self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'index.m3u8'
            subprocess.run([exe,'-nostdin','-y','-f','lavfi','-i',
                            'testsrc2=size=320x180:rate=12','-t','13','-c:v','libx264',
                            '-g','12','-sc_threshold','0','-pix_fmt','yuv420p','-f','hls',
                            '-hls_time','4','-hls_playlist_type','vod','-hls_segment_filename',
                            str(folder/'segment%05d.ts'),str(path)],capture_output=True,check=True,timeout=30)
            text=path.read_text();durations=list(map(Fraction,re.findall(r'#EXTINF:([0-9.]+),',text)))
            names=re.findall(r'^segment[0-9]+\.ts$',text,re.M)
            sizes=[(folder/name).stat().st_size for name in names]
            target=int(re.search(r'#EXT-X-TARGETDURATION:([0-9]+)',text)[1])
            self.assertEqual(len(names),4);self.assertEqual(durations[-1],1)
            rates=[]
            for start in range(len(names)):
                for end in range(start+1,len(names)+1):
                    duration=sum(durations[start:end])
                    if Fraction(target,2)<=duration<=Fraction(3*target,2):
                        rates.append(Fraction(8*sum(sizes[start:end]),1)/duration)
            result=self.measure(path)
            self.assertEqual(result['bandwidth'],math.ceil(max(rates)))
            self.assertEqual(result['average_bandwidth'],math.ceil(Fraction(8*sum(sizes),1)/sum(durations)))
            self.assertEqual(path.read_text(),text)

    def test_bad_measurement_is_unpublished_and_retry_preserves_source(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        import test_media_control as control
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MEDIA_WORKER':'1'}):
            root=Path(tmp);bad=[True]
            def encode(command,deadline,check):
                control.synthetic_output(command)
                if bad[0] and Path(command[-1]).suffix=='.m3u8':
                    (Path(command[-1]).parent/'segment00000.ts').unlink()
                return b'Output #0, hls\n Stream #0:0: Video: h264, yuv420p, 320x180, 10 fps'
            with patch('app.transcode.run_process',side_effect=encode),TestClient(create_app(root)) as client:
                ident=control.MediaControlTests().upload(client)
                job=control.MediaControlTests().wait_job(client,ident,{'failed'})
                self.assertEqual(job['variants'],[])
                self.assertNotIn(str(root),job['error'])
                self.assertEqual(client.get(f'/api/videos/{ident}/assets/master.m3u8').status_code,404)
                self.assertEqual(client.get(f'/api/videos/{ident}/media').status_code,200)
                self.assertEqual(list((root/'processed'/ident).iterdir()),[])
                bad[0]=False
                self.assertEqual(client.post(f'/api/community/videos/{ident}/retry').status_code,200)
                completed=control.MediaControlTests().wait_job(client,ident,{'completed'})
                self.assertTrue(all(v['bandwidth_source']=='measured-segment-windows-v1' for v in completed['variants']))
