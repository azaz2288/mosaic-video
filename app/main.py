from pathlib import Path
import os
import time
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .common import prepare, mount_ui, database, data_root

CATEGORIES = ["生活", "科技", "游戏", "知识", "音乐", "创作"]
MAX_BYTES = 512 * 1024 * 1024


class Comment(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class Danmaku(BaseModel):
    text: str = Field(min_length=1, max_length=80)
    at: float = Field(ge=0, le=86400)


def create_app(root=None):
    root=Path(root or data_root("mosaic"))
    app=prepare(FastAPI(title="Mosaic",version="0.1.0"),root)
    media=root/'media';media.mkdir(exist_ok=True)
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS videos(
          id TEXT PRIMARY KEY,title TEXT,description TEXT,category TEXT,filename TEXT,size INTEGER,created REAL,
          liked INTEGER DEFAULT 0,favorite INTEGER DEFAULT 0);
          CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,text TEXT,created REAL);
          CREATE TABLE IF NOT EXISTS danmaku(id TEXT PRIMARY KEY,video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,text TEXT,at REAL,created REAL);''')
    def video(db,ident):
        row=db.execute('SELECT * FROM videos WHERE id=?',(ident,)).fetchone()
        if not row: raise HTTPException(404,"视频不存在")
        return dict(row)

    @app.get('/api/config')
    def config(): return {"categories":CATEGORIES,"max_bytes":MAX_BYTES,"mode":"单用户本地社区"}

    @app.get('/api/videos')
    def videos(q: str=Query('',max_length=120),category: str='',favorites: bool=False,offset:int=Query(0,ge=0),limit:int=Query(40,ge=1,le=100)):
        where=['title LIKE ?'];args=['%'+q+'%']
        if category:
            where.append('category=?');args.append(category)
        if favorites: where.append('favorite=1')
        with database(root) as db:
            return [dict(r) for r in db.execute('SELECT id,title,description,category,size,created,liked,favorite FROM videos WHERE '+' AND '.join(where)+' ORDER BY created DESC LIMIT ? OFFSET ?',args+[limit,offset])]

    @app.post('/api/videos',status_code=201)
    def upload(file:UploadFile=File(...),title:str=Form(...),description:str=Form(''),category:str=Form('生活')):
        title=title.strip();description=description.strip()
        if not title or len(title)>100 or len(description)>2000 or category not in CATEGORIES:
            raise HTTPException(400,"请填写有效标题与分类；标题100字以内，简介2000字以内")
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in {'.mp4','.webm'}: raise HTTPException(400,"第一版支持MP4和WebM")
        ident=uuid.uuid4().hex
        partial=media/(ident+'.partial');final=media/(ident+suffix)
        try:
            first=file.file.read(1024*1024)
            valid=(suffix=='.mp4' and len(first)>=12 and first[4:8]==b'ftyp') or (suffix=='.webm' and first[:4]==b'\x1a\x45\xdf\xa3')
            if not valid: raise HTTPException(400,"文件容器标识无效")
            size=len(first)
            with partial.open('xb') as output:
                output.write(first)
                while chunk:=file.file.read(1024*1024):
                    size+=len(chunk)
                    if size>MAX_BYTES: raise HTTPException(413,"视频超过512MiB")
                    output.write(chunk)
            os.rename(partial,final)
            with database(root) as db:
                db.execute('INSERT INTO videos(id,title,description,category,filename,size,created) VALUES(?,?,?,?,?,?,?)',
                           (ident,title,description,category,final.name,size,time.time()))
                return video(db,ident)
        except Exception:
            partial.unlink(missing_ok=True);final.unlink(missing_ok=True)
            raise

    @app.get('/api/videos/{ident}')
    def detail(ident:str):
        with database(root) as db: return video(db,ident)

    @app.get('/api/videos/{ident}/media')
    def playback(ident:str):
        with database(root) as db: row=video(db,ident)
        path=media/row['filename']
        if not path.is_file(): raise HTTPException(404,"媒体文件缺失")
        return FileResponse(path,media_type='video/mp4' if path.suffix=='.mp4' else 'video/webm')

    @app.post('/api/videos/{ident}/interaction/{action}')
    def toggle(ident:str,action:str):
        if action not in {'like','favorite'}: raise HTTPException(404,"操作不存在")
        column='liked' if action=='like' else 'favorite'
        with database(root) as db:
            video(db,ident)
            db.execute(f'UPDATE videos SET {column}=1-{column} WHERE id=?',(ident,))
            return video(db,ident)

    @app.get('/api/videos/{ident}/comments')
    def comments(ident:str):
        with database(root) as db:
            video(db,ident)
            return [dict(r) for r in db.execute('SELECT * FROM comments WHERE video_id=? ORDER BY created DESC LIMIT 200',(ident,))]

    @app.post('/api/videos/{ident}/comments',status_code=201)
    def add_comment(ident:str,body:Comment):
        text=body.text.strip()
        if not text: raise HTTPException(400,"评论不能为空")
        with database(root) as db:
            video(db,ident);key=uuid.uuid4().hex
            db.execute('INSERT INTO comments VALUES(?,?,?,?)',(key,ident,text,time.time()))
            return {"id":key,"text":text}

    @app.get('/api/videos/{ident}/danmaku')
    def danmaku(ident:str):
        with database(root) as db:
            video(db,ident)
            return [dict(r) for r in db.execute('SELECT * FROM danmaku WHERE video_id=? ORDER BY at LIMIT 2000',(ident,))]

    @app.post('/api/videos/{ident}/danmaku',status_code=201)
    def add_danmaku(ident:str,body:Danmaku):
        text=body.text.strip()
        if not text: raise HTTPException(400,"弹幕不能为空")
        with database(root) as db:
            video(db,ident);key=uuid.uuid4().hex
            db.execute('INSERT INTO danmaku VALUES(?,?,?,?,?)',(key,ident,text,body.at,time.time()))
            return {"id":key,"text":text,"at":body.at}

    mount_ui(app)
    return app


app=create_app()
