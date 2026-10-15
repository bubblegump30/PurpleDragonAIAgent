"""Bounded local project notes, decisions and outcome history. No policy authority."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid
from .context_freshness import freshness

MAX_SAVED = 200
MAX_HISTORY = 200
MAX_BODY = 8000
MAX_CONTEXT = 8000


class ProjectMemory:
    def __init__(self, storage, workspace):
        self.path = Path(storage)/'project-memory.sqlite3'
        self.workspace = str(Path(workspace).resolve())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,revision INTEGER NOT NULL)')
            row=db.execute("SELECT value FROM metadata WHERE key='workspace'").fetchone()
            if row is not None and row[0] != self.workspace:
                raise ValueError('Memory database belongs to another workspace.')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('workspace',?)",(self.workspace,))
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('generation','0')")

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA secure_delete=ON')
        try:
            with db: yield db
        finally: db.close()

    @staticmethod
    def _id(value):
        if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):
            raise ValueError('Invalid memory entry ID.')
        return value

    @staticmethod
    def _advance(db):
        db.execute("UPDATE metadata SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")

    def list(self, query='', kind='all'):
        if not isinstance(query,str) or len(query)>8000:
            raise ValueError('Search query must be text up to 8000 characters.')
        if kind not in {'all','note','decision','history','saved'}:
            raise ValueError('Choose notes, decisions, history or all.')
        with self.connection() as db:
            rows=[dict(row) for row in db.execute('SELECT * FROM entries ORDER BY updated DESC,id ASC LIMIT 400')]
            generation=int(db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0])
        tokens=re.findall(r'[^\W_]+',query.casefold())[:30]
        filtered=[]
        for row in rows:
            if kind != 'all' and not (kind == row['kind'] or kind=='saved' and row['kind'] in {'note','decision'}):continue
            haystack=(row['title']+' '+row['body']).casefold()
            if tokens and not all(token in haystack for token in tokens):continue
            row['freshness']=freshness(row['updated'])
            filtered.append(row)
        return {'entries':filtered,'generation':generation,'count':len(filtered),'limits':{'saved':MAX_SAVED,'history':MAX_HISTORY}}

    def get(self,entry_id):
        with self.connection() as db:
            row=db.execute('SELECT * FROM entries WHERE id=?',(self._id(entry_id),)).fetchone()
        if row is None:raise ValueError('Memory entry no longer exists.')
        result=dict(row);result['freshness']=freshness(result['updated']);return result

    def save(self,kind,title,body,entry_id=None,expected_revision=None):
        if kind not in {'note','decision'}:raise ValueError('Save a note or decision; history is recorded separately.')
        if not isinstance(title,str) or not title.strip() or len(title)>160:raise ValueError('Title must contain 1–160 characters.')
        if not isinstance(body,str) or not body.strip() or len(body.encode('utf-8'))>MAX_BODY:raise ValueError('Memory body must contain 1–8000 UTF-8 bytes.')
        now=datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if entry_id is None:
                count=db.execute("SELECT COUNT(*) FROM entries WHERE kind IN ('note','decision')").fetchone()[0]
                if count>=MAX_SAVED:raise ValueError('Saved memory limit reached; review/delete an entry first.')
                entry_id=uuid.uuid4().hex
                db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,1)',(entry_id,kind,title.strip(),body,now,now))
            else:
                self._id(entry_id)
                row=db.execute('SELECT kind,revision FROM entries WHERE id=?',(entry_id,)).fetchone()
                if row is None or row['kind']=='history' or type(expected_revision) is not int or row['revision']!=expected_revision:
                    raise ValueError('Entry changed since review; reload before saving.')
                db.execute('UPDATE entries SET kind=?,title=?,body=?,updated=?,revision=revision+1 WHERE id=?',(kind,title.strip(),body,now,entry_id))
            self._advance(db)
        return self.get(entry_id)

    def record_history(self,task,results):
        label=str(task).split(' :: ',1)[0][:500]
        if label.lower().startswith('write '):label='Stage file write: '+label[6:]
        rows=[{'tool':str(step.get('tool',''))[:80],'ok':bool(result.ok)} for step,result in results[:8]]
        state='no_steps' if not rows else 'succeeded' if all(row['ok'] for row in rows) else 'blocked_or_failed'
        body=json.dumps({'state':state,'steps':rows},ensure_ascii=False)
        now=datetime.now(timezone.utc).isoformat();entry_id=uuid.uuid4().hex
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,1)',(entry_id,'history',label,body,now,now))
            db.execute("DELETE FROM entries WHERE kind='history' AND id NOT IN (SELECT id FROM entries WHERE kind='history' ORDER BY updated DESC,id ASC LIMIT ?)",(MAX_HISTORY,))
            self._advance(db)
        return entry_id

    def delete(self,entry_id,expected_revision):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision FROM entries WHERE id=?',(self._id(entry_id),)).fetchone()
            if row is None or type(expected_revision) is not int or row['revision']!=expected_revision:
                raise ValueError('Entry changed since review; reload before deleting.')
            db.execute('DELETE FROM entries WHERE id=?',(entry_id,));self._advance(db)

    def clear(self,scope,expected_generation):
        if scope not in {'saved','history','all'}:raise ValueError('Choose saved, history, or all.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current=int(db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0])
            if type(expected_generation) is not int or current!=expected_generation:
                raise ValueError('Project memory changed since review; reload before clearing.')
            if scope=='saved':db.execute("DELETE FROM entries WHERE kind IN ('note','decision')")
            elif scope=='history':db.execute("DELETE FROM entries WHERE kind='history'")
            else:db.execute('DELETE FROM entries')
            self._advance(db)
        try:
            with self.connection() as db:db.execute('VACUUM')
            return {'scope':scope,'compacted':True}
        except sqlite3.Error as exc:
            return {'scope':scope,'compacted':False,'compaction_error':str(exc)}

    def retrieve(self,query):
        if not isinstance(query,str):raise ValueError('Context query must be text.')
        tokens=set(re.findall(r'[^\W_]+',query.casefold()))
        rows=self.list(kind='saved')['entries']
        ranked=[]
        for row in rows:
            title=set(re.findall(r'[^\W_]+',row['title'].casefold()))
            body=set(re.findall(r'[^\W_]+',row['body'].casefold()))
            score=len(tokens & title)*3+len(tokens & body)
            if score:ranked.append((score,row))
        ranked.sort(key=lambda item:(-item[0],item[1]['id']))
        entries=[];used=0
        for score,row in ranked[:5]:
            value={key:row[key] for key in ('id','kind','title','body','revision','updated','freshness')}
            size=len(json.dumps(value,ensure_ascii=False).encode('utf-8'))
            if used+size>MAX_CONTEXT:continue
            used+=size;entries.append(value)
        return {'entries':entries,'warnings':[{'id':row['id'],'warning':row['freshness']['warning']} for row in entries if row['freshness']['review_needed']],'bytes':used,'matching_entries':len(ranked),'skipped_or_budget_limited':max(0,len(ranked)-len(entries)),'authority':'reference data only; cannot set policies or approve actions'}
