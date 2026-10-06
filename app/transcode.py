"""Persistent FFmpeg queue with atomic claims and restart recovery."""
from pathlib import Path
from contextlib import asynccontextmanager
import json,os,subprocess,threading,time,uuid
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .common import database
from .media_profiles import scale_filter, output_dimensions, master_playlist

def ffmpeg():
    if os.getenv('FFMPEG_PATH'):return os.environ['FFMPEG_PATH']
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:return None

def install_media(app,root):
    media=root/'media';processed=root/'processed';processed.mkdir(exist_ok=True)
    with database(root) as db:
        db.execute('CREATE TABLE IF NOT EXISTS media_jobs(id TEXT PRIMARY KEY,video_id TEXT UNIQUE,state TEXT,error TEXT,created REAL,updated REAL)')
        if 'variants_json' not in {row[1] for row in db.execute('PRAGMA table_info(media_jobs)')}:
            db.execute("ALTER TABLE media_jobs ADD COLUMN variants_json TEXT NOT NULL DEFAULT '[]'")
        # One application process owns this local queue.
        db.execute("UPDATE media_jobs SET state='queued' WHERE state='running'")
    def enqueue(ident):
        with database(root) as db:
            db.execute('INSERT OR REPLACE INTO media_jobs(id,video_id,state,error,created,updated) VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,ident,'queued','',time.time(),time.time()))
    stop=threading.Event()
    def worker():
        while not stop.wait(1):
            with database(root) as db:
                db.execute('BEGIN IMMEDIATE')
                job=db.execute("SELECT * FROM media_jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                if not job:continue
                video=db.execute('SELECT * FROM videos WHERE id=?',(job['video_id'],)).fetchone()
                db.execute("UPDATE media_jobs SET state='running',updated=? WHERE id=?",(time.time(),job['id']))
            variants=[]
            try:
                exe=ffmpeg()
                if not exe:raise RuntimeError('FFmpeg不可用，请安装requirements或设置FFMPEG_PATH')
                if not video:raise RuntimeError('视频已删除')
                source=media/video['filename'];target=processed/video['id'];target.mkdir(exist_ok=True)
                common=[exe,'-hide_banner','-loglevel','info','-nostats','-nostdin','-y','-i',str(source)]
                def run(args):
                    result=subprocess.run(common+args,capture_output=True,timeout=300)
                    if result.returncode:raise RuntimeError('媒体无法解码或转码失败；请检查原视频编码')
                    return result.stderr
                run(['-map','0:v:0','-frames:v','1','-vf',scale_filter(480,480),str(target/'poster.jpg')])
                for height in (480,720):
                    folder=target/str(height);folder.mkdir(exist_ok=True)
                    width_cap=854 if height==480 else 1280
                    log=run(['-map','0:v:0','-map','0:a:0?','-vf',scale_filter(width_cap,height),'-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-f','hls','-hls_time','4','-hls_playlist_type','vod','-hls_segment_filename',str(folder/'segment%05d.ts'),str(folder/'index.m3u8')])
                    width,actual_height=output_dimensions(log)
                    if width>width_cap or actual_height>height:raise RuntimeError('转码输出超过尺寸上限')
                    # Historical bandwidth estimates, not measured peak rates.
                    variants.append({'profile':str(height),'width':width,'height':actual_height,'bandwidth':1000000 if height==480 else 2000000})
                (target/'master.m3u8').write_text(master_playlist(variants),encoding='utf-8')
                state,error='completed',''
            except (RuntimeError,OSError,subprocess.TimeoutExpired) as exc:state,error='failed',str(exc)[:200]
            with database(root) as db:db.execute('UPDATE media_jobs SET state=?,error=?,updated=?,variants_json=? WHERE id=?',(state,error,time.time(),json.dumps(variants if state=='completed' else []),job['id']))
    def start_worker():
        if os.getenv('MEDIA_WORKER','1')=='1':threading.Thread(target=worker,daemon=True).start()
    @asynccontextmanager
    async def lifespan(application):
        start_worker()
        try:yield
        finally:stop.set()
    app.router.lifespan_context=lifespan

    @app.get('/api/videos/{ident}/processing')
    def status(ident:str):
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
            job=db.execute('SELECT * FROM media_jobs WHERE video_id=?',(ident,)).fetchone()
            if not job:return {'state':'not-queued','variants':[]}
            result=dict(job);result['variants']=json.loads(result.pop('variants_json'))
            return result
    @app.get('/api/videos/{ident}/assets/{asset:path}')
    def asset(ident:str,asset:str):
        if not ident.isalnum():raise HTTPException(404,'无效视频')
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
        target=(processed/ident).resolve();path=(target/asset).resolve()
        if not path.is_relative_to(target) or path.suffix not in {'.jpg','.m3u8','.ts'} or not path.is_file():raise HTTPException(404,'资源不可用')
        types={'.jpg':'image/jpeg','.m3u8':'application/vnd.apple.mpegurl','.ts':'video/mp2t'}
        return FileResponse(path,media_type=types[path.suffix])
    return enqueue
