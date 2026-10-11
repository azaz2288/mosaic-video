"""Synthetic-only UI fixture. Worker paused for reproducible queued cancellation."""
from pathlib import Path
import json,os,socket,subprocess,sys,tempfile,threading,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',8897))
    with tempfile.TemporaryDirectory(prefix='mosaic-control-demo-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap');os.environ['MEDIA_WORKER']='1'
        from app.main import create_app
        from app.transcode import ffmpeg
        from fastapi.testclient import TestClient
        import uvicorn
        clip=root/'synthetic.mp4'
        subprocess.run([ffmpeg(),'-nostdin','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-t','4','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],capture_output=True,check=True,timeout=30)
        with TestClient(create_app(root/'state')) as client:
            completed=client.post('/api/videos',data={'title':'已完成合成片 · 320×180','category':'创作'},files={'file':('synthetic.mp4',clip.read_bytes())}).json()['id']
            until=time.monotonic()+30
            while time.monotonic()<until:
                job=client.get(f'/api/videos/{completed}/processing').json()
                if job['state'] in {'failed','completed'}:break
                time.sleep(.1)
            if job['state']!='completed':raise RuntimeError(job)
        os.environ['MEDIA_WORKER']='0'
        app=create_app(root/'state')
        with TestClient(app) as client:
            # Legal trailing padding makes a distinct synthetic input, not a dedup.
            queued=client.post('/api/videos',data={'title':'待取消合成片 · 原视频保留','category':'科技'},files={'file':('synthetic.mp4',clip.read_bytes()+bytes(16))}).json()['id']
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8897,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        print(json.dumps({'completed':completed,'queued':queued,'url':'http://127.0.0.1:8897/','worker':'paused for deterministic UI cancellation','fixture':'synthetic only'}),flush=True)
        print('Enter stops server and cleans synthetic fixture',flush=True)
        try:input()
        finally:
            server.should_exit=True;thread.join(15)
            if thread.is_alive():raise RuntimeError('Demo server did not stop')


if __name__=='__main__':main()
