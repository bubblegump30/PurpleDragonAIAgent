"""Versioned settings recovery with review fingerprints and release integrity checks."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import time
import uuid
from .config import normalize_config
from .files import atomic_bytes

MAX_CONFIG=256000

def fingerprint(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode('utf-8')
def read_bounded(path,limit=MAX_CONFIG):
    if path.is_symlink():raise PermissionError('Linked recovery files are unavailable.')
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Recovery/manifest file exceeds its bounded size limit.')
    return data

class RecoveryCenter:
    def __init__(self,folder):
        self.folder=Path(folder).resolve();self.config=self.folder/'config'
        self.backups=self.config/'recovery-backups';self.previews={}
    def _directory(self):
        if self.config.is_symlink() or self.backups.is_symlink():raise PermissionError('Linked recovery folders are unavailable.')
    def defaults(self):return json.loads(read_bounded(self.config/'default_config.json'))
    def current_bytes(self):
        self._directory();path=self.config/'user_config.json'
        return read_bounded(path) if path.exists() else b''
    def list(self):
        self._directory();rows=[]
        for path in sorted(self.backups.glob('*.json'),reverse=True)[:100]:
            try:
                data=read_bounded(path);value=json.loads(data)
                if not isinstance(value,dict):raise ValueError('Recovery checkpoint must be an object.')
                valid=isinstance(value,dict) and value.get('schema')==1 and isinstance(value.get('settings'),dict) and fingerprint(encoded(value['settings']))==value.get('sha256')
                rows.append({'id':path.stem,'created_at':value.get('created_at'),'label':str(value.get('label',''))[:80],'valid':valid})
            except (ValueError,OSError,TypeError,RecursionError):rows.append({'id':path.stem,'valid':False})
        return rows
    def backup(self,settings,label='Manual settings checkpoint'):
        self._directory()
        normalized=normalize_config(settings,self.defaults())
        # Retain an absolute workspace so recovery is independent of release folder location.
        workspace=Path(normalized['workspace'])
        if not workspace.is_absolute():normalized['workspace']=str((self.folder/workspace).resolve())
        identifier=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex
        record={'schema':1,'created_at':datetime.now(timezone.utc).isoformat(),'label':str(label)[:80],'settings':normalized,'sha256':fingerprint(encoded(normalized))}
        self.backups.mkdir(parents=True,exist_ok=True)
        atomic_bytes(self.backups/(identifier+'.json'),json.dumps(record,indent=2).encode())
        return {'id':identifier,'label':record['label'],'sha256':record['sha256']}
    def _load(self,identifier):
        self._directory()
        if not isinstance(identifier,str) or not identifier or len(identifier)>100 or any(c not in '0123456789TZabcdef-' for c in identifier):raise ValueError('Select a listed recovery backup.')
        data=read_bounded(self.backups/(identifier+'.json'));record=json.loads(data)
        if not isinstance(record,dict) or record.get('schema')!=1 or not isinstance(record.get('settings'),dict) or fingerprint(encoded(record['settings']))!=record.get('sha256'):raise ValueError('Recovery backup integrity check failed.')
        return data,normalize_config(record['settings'],self.defaults())
    def preview(self,identifier,current=None,reset=False):
        effective_current=current
        if reset:
            data=read_bounded(self.config/'default_config.json');settings=normalize_config({},json.loads(data));identifier='defaults'
            # Reset must preserve the existing project destination when it can be read.
            if current is None:
                try:current=json.loads(self.current_bytes())
                except (ValueError,OSError):current={}
            if isinstance(current,dict) and isinstance(current.get('workspace'),str) and current['workspace'].strip():settings['workspace']=current['workspace']
        else:data,settings=self._load(identifier)
        previous=self.current_bytes();token=uuid.uuid4().hex
        before=current if isinstance(current,dict) else {}
        changed=[key for key in ('workspace','permissions','lm_studio','research','project_memory','security') if before.get(key)!=settings.get(key)]
        preview={'id':token,'backup_id':identifier,'source_hash':fingerprint(data),'disk_hash':fingerprint(previous),'effective_hash':fingerprint(encoded(effective_current)),'created':time.monotonic(),'settings':settings,'review':{'workspace':settings['workspace'],'changed_sections':changed,'permission_changes':settings['permissions'],'model_connection':settings['lm_studio'],'research':settings['research'],'project_memory':settings['project_memory'],'security':settings['security'],'warning':'Restores settings only. Workspace files, credentials, snapshots and audit history are not restored. All base policies and destinations will be replaced as reviewed.'}}
        self.previews={token:preview}
        return {k:deepcopy(preview[k]) for k in ('id','backup_id','review')}
    def apply(self,token,current=None):
        if not isinstance(token,str) or token not in self.previews:raise ValueError('Prepare a fresh settings recovery review.')
        proposal=self.previews[token]
        if time.monotonic()-proposal['created']>300:raise ValueError('Settings recovery review expired; preview again.')
        if proposal['disk_hash']!=fingerprint(self.current_bytes()) or proposal['effective_hash']!=fingerprint(encoded(current)):raise ValueError('Current settings changed after review; nothing restored.')
        if proposal['backup_id']=='defaults':data=read_bounded(self.config/'default_config.json')
        else:data,_=self._load(proposal['backup_id'])
        if fingerprint(data)!=proposal['source_hash']:raise ValueError('Backup changed after review; nothing restored.')
        rollback=None
        if isinstance(current,dict):
            try:rollback=self.backup(current,'Before settings restore')
            except (ValueError,TypeError):pass # Invalid settings preserved byte-for-byte below.
        previous=self.current_bytes()
        if fingerprint(previous)!=proposal['disk_hash']:raise ValueError('Settings changed during recovery preparation; nothing restored.')
        if previous:
            # Keep exact corrupt bytes too; these are inert recovery evidence, not executable configuration.
            evidence=self.config/'recovery-backups'/('raw-'+uuid.uuid4().hex+'.bin')
            evidence.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(evidence,previous)
        settings=normalize_config(proposal['settings'],self.defaults())
        workspace=Path(settings['workspace'])
        if not workspace.is_absolute():workspace=self.folder/workspace
        if workspace.exists() and not workspace.is_dir():raise ValueError('Reviewed workspace points to a file; restore refused.')
        if fingerprint(self.current_bytes())!=proposal['disk_hash']:raise ValueError('Settings changed during recovery; nothing restored.')
        atomic_bytes(self.config/'user_config.json',json.dumps(settings,indent=2).encode())
        self.previews.clear()
        return {'settings':settings,'rollback':rollback,'message':'Settings restored. Previous bytes preserved; workspace content unchanged.'}


def release_readiness(folder):
    folder=Path(folder).resolve();errors=[];verified=0
    try:
        manifest=json.loads(read_bounded(folder/'RELEASE-MANIFEST.json',2000000))
        rows=manifest['files']
        if not isinstance(rows,list) or not rows or len(rows)>2000:raise ValueError('Invalid release manifest.')
        seen=set()
        for row in rows:
            name=row['path'];parts=PurePosixPath(name).parts
            if not isinstance(name,str) or not name or PurePosixPath(name).is_absolute() or '..' in parts or ':' in name or '\\' in name or name in seen:raise ValueError('Unsafe release manifest entry.')
            seen.add(name);path=folder/name
            if path.is_symlink() or not path.resolve().is_relative_to(folder):raise ValueError('Linked release entry refused.')
            if not path.is_file() or path.stat().st_size!=row['bytes'] or path.stat().st_size>100000000:
                errors.append({'path':name,'reason':'missing or size mismatch'});continue
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1000000),b''):digest.update(chunk)
            if digest.hexdigest()!=row['sha256']:errors.append({'path':name,'reason':'hash mismatch'})
            else:verified+=1
        required={'launcher.py','purple_dragon_agent/desktop.py','purple_dragon_agent/permissions.py','config/default_config.json','frontend/app.js','frontend/style.css','frontend/index.html'}
        distribution=manifest.get('distribution','source')
        if distribution not in {'source','windows-onedir'}:raise ValueError('Unknown distribution profile.')
        if distribution=='windows-onedir':required={'PurpleDragonAI.exe','PurpleDragonRecovery.exe','config/default_config.json','frontend/index.html','frontend/app.js','frontend/style.css'}
        if not required<=seen:raise ValueError('Manifest omits required runtime files.')
        # Every stylesheet and script referenced by the shipped entry page must be hashed.
        from html.parser import HTMLParser
        class Dependencies(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attributes=dict(attrs)
                ref=attributes.get('src') if tag=='script' else attributes.get('href') if tag=='link' and attributes.get('rel')=='stylesheet' else None
                if ref is None:return
                parts=PurePosixPath(ref).parts
                if not ref or ref.startswith('/') or '..' in parts or ':' in ref or '\\' in ref or '?' in ref or '#' in ref:
                    raise ValueError('Unsafe frontend dependency.')
                if 'frontend/'+ref not in seen:raise ValueError('Manifest omits frontend dependency: '+ref)
        Dependencies().feed(read_bounded(folder/'frontend/index.html',500000).decode('utf-8'))

        from . import __version__
        if manifest.get('version')!=__version__:raise ValueError('Manifest version mismatch.')
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:errors.append({'path':'RELEASE-MANIFEST.json','reason':str(exc)[:200]})
    return {'status':'candidate_checks_passed' if not errors else 'blocked','verified_files':verified,'errors':errors[:100],'runtime':{'platform':platform.system(),'python':platform.python_version()},'distribution':manifest.get('distribution','source') if 'manifest' in locals() and isinstance(manifest,dict) else 'unknown','pending':['Real Windows Edge WebView2 / DPI acceptance','Actual Windows DPAPI secret storage','Windows Sandbox execution','Live LM Studio and authenticated GitHub verification'],'limitations':'Checksums detect drift against this local manifest; this is not a signature, security certification or stable-release approval.'}
