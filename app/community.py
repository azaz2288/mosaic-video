from pathlib import Path
import time,uuid
from fastapi import HTTPException,Request
from pydantic import BaseModel,Field
from .common import database

class Text(BaseModel):
    text:str=Field(min_length=1,max_length=500)
class Edit(BaseModel):
    title:str=Field(min_length=1,max_length=100)
    description:str=Field('',max_length=2000)
class Collection(BaseModel):
    name:str=Field(min_length=1,max_length=60)

def install_community(app,root,identity,enqueue):
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS follows(user_id TEXT,author_id TEXT,PRIMARY KEY(user_id,author_id));
         CREATE TABLE IF NOT EXISTS view_history(user_id TEXT,video_id TEXT,position REAL,updated REAL,PRIMARY KEY(user_id,video_id));
         CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,user_id TEXT,text TEXT,read INTEGER DEFAULT 0,created REAL);
         CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id TEXT,video_id TEXT,reason TEXT,state TEXT,created REAL);
         CREATE TABLE IF NOT EXISTS collections(id TEXT PRIMARY KEY,user_id TEXT,name TEXT);
         CREATE TABLE IF NOT EXISTS collection_items(collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,PRIMARY KEY(collection_id,video_id));''')
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS video_fts USING fts5(id UNINDEXED,title,description,tokenize='trigram')")
        db.execute('DELETE FROM video_fts');db.execute('INSERT INTO video_fts SELECT id,title,description FROM videos')
        db.executescript('''CREATE TRIGGER IF NOT EXISTS video_search_insert AFTER INSERT ON videos BEGIN INSERT INTO video_fts VALUES(new.id,new.title,new.description); END;
        CREATE TRIGGER IF NOT EXISTS video_search_update AFTER UPDATE OF title,description ON videos BEGIN DELETE FROM video_fts WHERE id=old.id; INSERT INTO video_fts VALUES(new.id,new.title,new.description); END;
        CREATE TRIGGER IF NOT EXISTS video_search_delete AFTER DELETE ON videos BEGIN DELETE FROM video_fts WHERE id=old.id; END;''')
    def owned(db,ident,request):
        row=db.execute('SELECT * FROM videos WHERE id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'视频不存在')
        if row['owner']!=identity(request)['id']:raise HTTPException(403,'只能修改自己的作品')
        return row
    @app.get('/api/community/hidden')
    def hidden(request:Request):
        with database(root) as db:return [dict(r) for r in db.execute('SELECT id,title FROM videos WHERE owner=? AND hidden=1 ORDER BY created DESC',(identity(request)['id'],))]
    @app.patch('/api/community/videos/{ident}')
    def edit(ident:str,body:Edit,request:Request):
        with database(root) as db:
            owned(db,ident,request);db.execute('UPDATE videos SET title=?,description=? WHERE id=?',(body.title.strip(),body.description,ident))
        return {'ok':True}
    @app.delete('/api/community/videos/{ident}')
    def remove(ident:str,request:Request):
        with database(root) as db:
            owned(db,ident,request);db.execute('UPDATE videos SET hidden=1 WHERE id=?',(ident,))
        return {'ok':True,'note':'软删除，可通过恢复接口撤销'}
    @app.post('/api/community/videos/{ident}/restore')
    def restore(ident:str,request:Request):
        with database(root) as db:
            owned(db,ident,request);db.execute('UPDATE videos SET hidden=0 WHERE id=?',(ident,))
        return {'ok':True}
    @app.post('/api/community/videos/{ident}/retry')
    def retry(ident:str,request:Request):
        with database(root) as db:owned(db,ident,request)
        enqueue(ident);return {'ok':True}
    @app.get('/api/community/authors/{author}')
    def author(author:str,request:Request):
        with database(root) as db:
            user=db.execute('SELECT id,username FROM users WHERE id=?',(author,)).fetchone()
            videos=[dict(r) for r in db.execute('SELECT id,title,category FROM videos WHERE owner=? AND hidden=0',(author,))]
            following=bool(db.execute('SELECT 1 FROM follows WHERE user_id=? AND author_id=?',(identity(request)['id'],author)).fetchone())
        return {'author':dict(user) if user else {'id':author,'username':'本地创作者'},'videos':videos,'following':following}
    @app.post('/api/community/authors/{author}/follow')
    def follow(author:str,request:Request):
        user=identity(request)['id']
        if user==author:raise HTTPException(400,'不能关注自己')
        with database(root) as db:
            if db.execute('SELECT 1 FROM follows WHERE user_id=? AND author_id=?',(user,author)).fetchone():db.execute('DELETE FROM follows WHERE user_id=? AND author_id=?',(user,author));state=False
            else:db.execute('INSERT INTO follows VALUES(?,?)',(user,author));state=True
        return {'following':state}
    @app.post('/api/community/videos/{ident}/history')
    def history_add(ident:str,request:Request,position:float=0):
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
            db.execute('INSERT OR REPLACE INTO view_history VALUES(?,?,?,?)',(identity(request)['id'],ident,max(0,min(position,86400)),time.time()))
        return {'ok':True}
    @app.get('/api/community/history')
    def history(request:Request):
        with database(root) as db:return [dict(r) for r in db.execute('SELECT h.*,v.title FROM view_history h JOIN videos v ON v.id=h.video_id WHERE user_id=? AND v.hidden=0 ORDER BY updated DESC LIMIT 100',(identity(request)['id'],))]
    @app.get('/api/community/notifications')
    def notices(request:Request):
        with database(root) as db:return [dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 100',(identity(request)['id'],))]
    @app.post('/api/community/videos/{ident}/report')
    def report(ident:str,body:Text,request:Request):
        with database(root) as db:
            if not db.execute('SELECT 1 FROM videos WHERE id=?',(ident,)).fetchone():raise HTTPException(404,'视频不存在')
            db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,identity(request)['id'],ident,body.text,'open',time.time()))
        return {'ok':True}
    @app.get('/api/community/reports')
    def reports(request:Request):
        with database(root) as db:return [dict(r) for r in db.execute('SELECT r.*,v.title FROM reports r JOIN videos v ON v.id=r.video_id WHERE v.owner=? ORDER BY r.created DESC',(identity(request)['id'],))]
    @app.post('/api/community/reports/{ident}/resolve')
    def resolve(ident:str,request:Request):
        with database(root) as db:
            report=db.execute('SELECT * FROM reports WHERE id=?',(ident,)).fetchone()
            if not report:raise HTTPException(404,'举报不存在')
            owned(db,report['video_id'],request);db.execute("UPDATE reports SET state='reviewed' WHERE id=?",(ident,))
        return {'ok':True}
    @app.get('/api/community/collections')
    def collections(request:Request):
        with database(root) as db:
            result=[]
            for c in db.execute('SELECT * FROM collections WHERE user_id=?',(identity(request)['id'],)):
                result.append({**dict(c),'videos':[dict(r) for r in db.execute('SELECT v.id,v.title FROM videos v JOIN collection_items i ON i.video_id=v.id WHERE i.collection_id=? AND v.hidden=0',(c['id'],))]})
            return result
    @app.post('/api/community/collections')
    def add_collection(body:Collection,request:Request):
        ident=uuid.uuid4().hex
        with database(root) as db:db.execute('INSERT INTO collections VALUES(?,?,?)',(ident,identity(request)['id'],body.name.strip()))
        return {'id':ident}
    @app.post('/api/community/collections/{ident}/{video_id}')
    def add_item(ident:str,video_id:str,request:Request):
        with database(root) as db:
            if not db.execute('SELECT 1 FROM collections WHERE id=? AND user_id=?',(ident,identity(request)['id'])).fetchone():raise HTTPException(403,'合集权限不足')
            if not db.execute('SELECT 1 FROM videos WHERE id=? AND hidden=0',(video_id,)).fetchone():raise HTTPException(404,'视频不存在')
            db.execute('INSERT OR IGNORE INTO collection_items VALUES(?,?)',(ident,video_id))
        return {'ok':True}
    @app.get('/api/community/recommendations/{ident}')
    def recommend(ident:str):
        with database(root) as db:
            video=db.execute('SELECT * FROM videos WHERE id=?',(ident,)).fetchone()
            if not video:raise HTTPException(404,'视频不存在')
            return [{**dict(r),'reason':'同分区内容'} for r in db.execute('SELECT id,title,category FROM videos WHERE category=? AND id!=? AND hidden=0 ORDER BY created DESC LIMIT 8',(video['category'],ident))]
