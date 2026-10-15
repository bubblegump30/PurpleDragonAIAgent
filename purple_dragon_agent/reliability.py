"""Small, display-independent startup and upgrade checks."""
from pathlib import Path
import json
import errno
import sys
from datetime import datetime, timezone
from .config import normalize_config
from .files import atomic_bytes


def window_geometry(screen_width, screen_height):
    width=min(1672,max(320,int(screen_width)-40))
    height=min(1010,max(240,int(screen_height)-60))
    return width,height,(min(800,width),min(500,height))


def window_chrome(platform_name):
    # Windows owns resize hit-testing, Snap and maximized work-area constraints.
    return {'frameless':platform_name!='win32', 'resizable':True,
            'fullscreen':False, 'easy_drag':False}


class RuntimeLease:
    """OS-held app-folder lock; released automatically on process termination."""
    def __init__(self, folder):
        self.path=Path(folder)/'logs/runtime.lock'
        self.file=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        if self.path.stat().st_size==0:
            self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close();self.file=None
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise OSError('Could not acquire the application-folder lock. Check folder access and storage availability.') from exc
            raise RuntimeError('Purple Dragon AI Agent is already running from this folder. Close it before launching again or importing settings.') from exc
        return self

    def __exit__(self,*args):
        if self.file:
            self.file.seek(0)
            try:
                if sys.platform=='win32':
                    import msvcrt
                    msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
            finally:
                self.file.close();self.file=None


def import_previous_settings(source, destination):
    with RuntimeLease(destination):
        return _import_previous_settings(source,destination)


def _import_previous_settings(source, destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination:
        raise ValueError('Choose the previous release folder, not this release.')
    previous=source/'config/user_config.json'
    if not previous.is_file():
        raise ValueError('The selected folder has no config/user_config.json.')
    saved=json.loads(previous.read_text(encoding='utf-8'))
    defaults=json.loads((destination/'config/default_config.json').read_text(encoding='utf-8'))
    if not isinstance(saved,dict):
        raise ValueError('Previous settings must be an object.')
    old_workspace=Path(saved.get('workspace') or 'workspace')
    if not old_workspace.is_absolute():
        old_workspace=source/old_workspace
    saved['workspace']=str(old_workspace.resolve())
    normalized=normalize_config(saved,defaults)
    target=destination/'config/user_config.json'
    backup=None
    if target.exists():
        timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=destination/'config'/f'user_config.before-upgrade-{timestamp}.json'
        atomic_bytes(backup,target.read_bytes())
    atomic_bytes(target,json.dumps(normalized,indent=2).encode('utf-8'))
    return {'workspace':normalized['workspace'],'backup':str(backup) if backup else None,
            'message':'Settings imported. The existing workspace remains in its original location.'}
