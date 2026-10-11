"""Persistent FFmpeg queue with atomic claims and restart recovery."""
from pathlib import Path
from contextlib import asynccontextmanager
import json,os,sqlite3,subprocess,tempfile,threading,time,uuid
from fastapi import HTTPException,Request
from fastapi.responses import FileResponse
from .common import database
from .media_profiles import scale_filter, output_dimensions, master_playlist
from .media_process import run_process,check_deadline,MediaCancelled,MediaStopped,MediaDeadline

def ffmpeg():
    if os.getenv('FFMPEG_PATH'):return os.environ['FFMPEG_PATH']
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:return None

def install_media(app,root,identity):
    media=root/'media';processed=root/'processed';processed.mkdir(exist_ok=True)
    raw_budget=os.getenv('MEDIA_JOB_TIMEOUT_SECONDS','300')
    if not raw_budget.isascii() or not raw_budget.isdecimal() or not 1<=int(raw_budget)<=3600:
        raise ValueError('MEDIA_JOB_TIMEOUT_SECONDS必须为1至3600的整数')
    budget=int(raw_budget)
    with database(root) as db:
        db.execute('CREATE TABLE IF NOT EXISTS media_jobs(id TEXT PRIMARY KEY,video_id TEXT UNIQUE,state TEXT,error TEXT,created REAL,updated REAL)')
        if 'variants_json' not in {row[1] for row in db.execute('PRAGMA table_info(media_jobs)')}:
            db.execute("ALTER TABLE media_jobs ADD COLUMN variants_json TEXT NOT NULL DEFAULT '[]'")
        if 'artifact_id' not in {row[1] for row in db.execute('PRAGMA table_info(media_jobs)')}:
            db.execute("ALTER TABLE media_jobs ADD COLUMN artifact_id TEXT NOT NULL DEFAULT ''")
        # One application process owns this local queue.
        db.execute("UPDATE media_jobs SET state='queued' WHERE state='running'")
        db.execute("UPDATE media_jobs SET state='cancelled' WHERE state='cancelling'")
    def enqueue(ident):
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM media_jobs WHERE video_id=? AND state IN ('queued','running','cancelling')",(ident,)).fetchone():
                raise HTTPException(409,'转码任务仍在排队、运行或取消中')
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
            deadline=time.monotonic()+budget
            def interrupted():
                if stop.is_set():raise MediaStopped()
                with database(root) as db:
                    current=db.execute('SELECT state FROM media_jobs WHERE id=?',(job['id'],)).fetchone()
                if not current or current['state']!='running':raise MediaCancelled()
            try:
                exe=ffmpeg()
                if not exe:raise RuntimeError('FFmpeg不可用，请安装requirements或设置FFMPEG_PATH')
                if not video:raise RuntimeError('视频已删除')
                source=media/video['filename'];parent=processed/video['id'];parent.mkdir(exist_ok=True)
                common=[exe,'-hide_banner','-loglevel','info','-nostats','-nostdin','-y','-i',str(source)]
                def run(args):
                    return run_process(common+args,deadline,interrupted)
                with tempfile.TemporaryDirectory(prefix='.work-',dir=parent) as staging:
                    target=Path(staging)
                    run(['-map','0:v:0','-frames:v','1','-vf',scale_filter(480,480),str(target/'poster.jpg')])
                    for height in (480,720):
                        folder=target/str(height);folder.mkdir()
                        width_cap=854 if height==480 else 1280
                        log=run(['-map','0:v:0','-map','0:a:0?','-vf',scale_filter(width_cap,height),'-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-f','hls','-hls_time','4','-hls_playlist_type','vod','-hls_segment_filename',str(folder/'segment%05d.ts'),str(folder/'index.m3u8')])
                        width,actual_height=output_dimensions(log)
                        if width>width_cap or actual_height>height:raise RuntimeError('转码输出超过尺寸上限')
                        # Historical bandwidth estimates, not measured peak rates.
                        variants.append({'profile':str(height),'width':width,'height':actual_height,'bandwidth':1000000 if height==480 else 2000000})
                    (target/'master.m3u8').write_text(master_playlist(variants),encoding='utf-8')
                    check_deadline(deadline,interrupted)
                    with database(root) as db:
                        db.execute('BEGIN IMMEDIATE')
                        current=db.execute('SELECT state FROM media_jobs WHERE id=?',(job['id'],)).fetchone()
                        if not current or current['state']!='running':raise MediaCancelled()
                        if stop.is_set():raise MediaStopped()
                        if time.monotonic()>=deadline:raise MediaDeadline()
                        # One attempt, unique output; never replace prior completed media.
                        os.rename(target,parent/job['id'])
                        db.execute("UPDATE media_jobs SET state='completed',error='',updated=?,variants_json=?,artifact_id=? WHERE id=? AND state='running'",(time.time(),json.dumps(variants),job['id'],job['id']))
                continue
            except MediaStopped:state,error='queued',''
            except MediaCancelled:state,error='cancelled',''
            except MediaDeadline:state,error='failed','任务总时限已到；可重试或调整服务端预算'
            except (RuntimeError,OSError,sqlite3.Error,subprocess.TimeoutExpired):state,error='failed','媒体无法解码、转码或发布；请检查编码、FFmpeg和本机存储'
            with database(root) as db:
                db.execute("UPDATE media_jobs SET state=CASE WHEN state='cancelling' THEN 'cancelled' ELSE ? END,error=?,updated=?,variants_json='[]' WHERE id=? AND state IN ('running','cancelling')",(state,error,time.time(),job['id']))
    worker_thread=None
    def start_worker():
        nonlocal worker_thread
        stop.clear()
        if os.getenv('MEDIA_WORKER','1')=='1':
            worker_thread=threading.Thread(target=worker,daemon=True);worker_thread.start()
    @asynccontextmanager
    async def lifespan(application):
        start_worker()
        try:yield
        finally:
            stop.set()
            if worker_thread:
                worker_thread.join(timeout=20)
                if worker_thread.is_alive():raise RuntimeError('媒体工作线程未在关闭期限内退出')
    app.router.lifespan_context=lifespan

    @app.get('/api/videos/{ident}/processing')
    def status(ident:str):
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
            job=db.execute('SELECT * FROM media_jobs WHERE video_id=?',(ident,)).fetchone()
            if not job:return {'state':'not-queued','variants':[]}
            result=dict(job);result['variants']=json.loads(result.pop('variants_json'))
            result['budget_seconds']=budget
            return result
    @app.post('/api/videos/{ident}/processing/cancel')
    def cancel(ident:str,request:Request):
        actor=identity(request)['id']
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE')
            video=db.execute('SELECT owner FROM videos WHERE id=?',(ident,)).fetchone()
            if not video:raise HTTPException(404,'视频不存在')
            if video['owner']!=actor:raise HTTPException(403,'只能取消自己的转码任务')
            job=db.execute('SELECT * FROM media_jobs WHERE video_id=?',(ident,)).fetchone()
            if not job:raise HTTPException(404,'任务不存在')
            if job['state'] in {'completed','failed'}:raise HTTPException(409,'任务已结束；无需取消')
            state='cancelled' if job['state'] in {'queued','cancelled'} else 'cancelling'
            db.execute("UPDATE media_jobs SET state=?,error='',updated=?,variants_json='[]' WHERE id=?",(state,time.time(),job['id']))
            return {'state':state}
    @app.get('/api/videos/{ident}/assets/{asset:path}')
    def asset(ident:str,asset:str):
        if not ident.isalnum():raise HTTPException(404,'无效视频')
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
            job=db.execute('SELECT state,artifact_id FROM media_jobs WHERE video_id=?',(ident,)).fetchone()
            if not job or job['state']!='completed':raise HTTPException(404,'转码资源尚未完成或已取消')
        artifact_id=job['artifact_id']
        if artifact_id and (len(artifact_id)!=32 or any(c not in '0123456789abcdef' for c in artifact_id)):raise HTTPException(404,'资源不可用')
        if any(part.startswith('.') for part in Path(asset).parts):raise HTTPException(404,'资源不可用')
        target=(processed/ident/artifact_id).resolve();path=(target/asset).resolve()
        if not path.is_relative_to(target) or path.suffix not in {'.jpg','.m3u8','.ts'} or not path.is_file():raise HTTPException(404,'资源不可用')
        types={'.jpg':'image/jpeg','.m3u8':'application/vnd.apple.mpegurl','.ts':'video/mp2t'}
        return FileResponse(path,media_type=types[path.suffix])
    return enqueue
