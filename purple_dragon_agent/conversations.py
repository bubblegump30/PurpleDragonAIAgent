"""Bounded, atomic local conversation storage, isolated by canonical workspace."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .files import atomic_bytes

class ConversationStore:
    def __init__(self, directory, workspace):
        key=hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()
        self.path=Path(directory)/f'{key}.json'
    def _read(self):
        if not self.path.exists():return []
        if self.path.stat().st_size>4_000_000:raise ValueError('Conversation storage exceeds its limit. Preserve the file before recovery.')
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data,list) or len(data)>100:raise ValueError()
            ids=set()
            for row in data:
                if not isinstance(row,dict) or set(row)!={'id','title','updated','messages'}:raise ValueError()
                if not re.fullmatch('[0-9a-f]{32}',row['id']) or row['id'] in ids:raise ValueError()
                ids.add(row['id'])
                if not isinstance(row['title'],str) or not 1<=len(row['title'])<=120 or not isinstance(row['updated'],str):raise ValueError()
                if not isinstance(row['messages'],list) or len(row['messages'])>200:raise ValueError()
                for m in row['messages']:
                    if not isinstance(m,dict) or set(m)!={'role','text'} or m['role'] not in {'user','assistant'} or not isinstance(m['text'],str) or len(m['text'])>100000:raise ValueError()
            return data
        except (ValueError,TypeError,KeyError,RecursionError):raise ValueError('Conversation storage is damaged. Original data was preserved; restore it from a backup before retrying.') from None
    def _write(self,rows):
        raw=json.dumps(rows,ensure_ascii=False).encode('utf-8')
        if len(raw)>4_000_000:raise ValueError('Conversation storage is full. Delete old conversations before retrying.')
        atomic_bytes(self.path,raw)
    def get(self,identifier):
        if not isinstance(identifier,str):raise ValueError('Select a conversation.')
        for row in self._read():
            if row['id']==identifier:return row
        raise ValueError('Conversation no longer exists in this workspace.')
    def list(self,query=''):
        if not isinstance(query,str) or len(query)>200:raise ValueError('Search must contain at most 200 characters.')
        return sorted([dict(id=r['id'],title=r['title'],updated=r['updated'],count=len(r['messages'])) for r in self._read() if query.casefold() in (r['title']+' '+ ' '.join(m['text'] for m in r['messages'])).casefold()],key=lambda r:r['updated'],reverse=True)
    def create(self):
        rows=self._read()
        if len(rows)>=100:raise ValueError('Conversation limit reached. Delete an old conversation first.')
        row={'id':uuid.uuid4().hex,'title':'New conversation','updated':datetime.now(timezone.utc).isoformat(),'messages':[]}
        rows.append(row);self._write(rows);return row
    def update(self,identifier,title=None,delete=False,messages=None):
        rows=self._read();row=next((r for r in rows if r['id']==identifier),None)
        if row is None:raise ValueError('Conversation no longer exists in this workspace.')
        if delete:rows.remove(row)
        else:
            if title is not None:
                if not isinstance(title,str) or not 1<=len(title.strip())<=120:raise ValueError('Title must contain 1–120 characters.')
                row['title']=title.strip()
            if messages is not None:
                if len(messages)>200 or any(len(m['text'])>100000 for m in messages):raise ValueError('Conversation is full. Start a new chat.')
                row['messages']=messages
            row['updated']=datetime.now(timezone.utc).isoformat()
        self._write(rows);return row
