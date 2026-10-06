"""Independent synthetic media demo. Enter stops server and cleans its temp data."""
from pathlib import Path
import os, subprocess, sys, tempfile, threading, time, json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix='mosaic-profiles-demo-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        os.environ['MEDIA_WORKER']='1'
        from app.main import create_app
        from app.transcode import ffmpeg
        from fastapi.testclient import TestClient
        import uvicorn
        app=create_app(root/'state')
        evidence=[]
        with TestClient(app) as client:
            for width,height,title in [(320,180,'低清合成视频 · 不放大'),(360,640,'竖屏合成视频 · 实际尺寸')]:
                clip=root/f'{width}.mp4'
                subprocess.run([ffmpeg(),'-nostdin','-y','-f','lavfi','-i',f'testsrc2=size={width}x{height}:rate=12','-t','8','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],capture_output=True,check=True,timeout=30)
                started=time.monotonic()
                ident=client.post('/api/videos',data={'title':title,'category':'创作'},files={'file':('clip.mp4',clip.read_bytes())}).json()['id']
                for _ in range(180):
                    job=client.get(f'/api/videos/{ident}/processing').json()
                    if job['state'] in {'completed','failed'}:break
                    time.sleep(.25)
                if job['state']!='completed':raise RuntimeError(job)
                evidence.append({'source':[width,height],'seconds_including_queue_wait':round(time.monotonic()-started,3),'variants':job['variants']})
        os.environ['MEDIA_WORKER']='0'
        app=create_app(root/'state')
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8893,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        print(json.dumps(evidence,ensure_ascii=True),flush=True)
        print('Synthetic demo http://127.0.0.1:8893/ ; Enter stops and cleans temporary data',flush=True)
        try:input()
        finally:
            server.should_exit=True;thread.join(timeout=15)
            if thread.is_alive():raise RuntimeError('Demo server did not stop')


if __name__=='__main__':main()
