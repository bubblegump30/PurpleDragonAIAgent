"""Bounded workspace indexing and durable, reviewed file transactions."""
from pathlib import Path
from collections import Counter
import base64
import difflib
import hashlib
import json
import os
import tempfile
import uuid

from .workspace import IGNORED_DIRECTORIES

IGNORED = IGNORED_DIRECTORIES
MAX_FILE = 1_000_000
MAX_TOTAL = 10_000_000


def digest(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def encode(data):
    return None if data is None else base64.b64encode(data).decode('ascii')


def decode(data):
    return None if data is None else base64.b64decode(data, validate=True)


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, filename = tempfile.mkstemp(prefix='.pd-write-', dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class FileAgent:
    def __init__(self, workspace, storage):
        self.workspace = workspace
        storage = Path(storage).resolve()
        if storage == workspace.root or workspace.root in storage.parents:
            raise ValueError('Recovery storage must be outside the selected workspace.')
        key = hashlib.sha256(str(workspace.root).encode()).hexdigest()
        self.storage = storage / key
        self.storage.mkdir(parents=True, exist_ok=True)
        self.pending_path = self.storage / 'pending.json'
        self.snapshots_dir = self.storage / 'snapshots'
        self.snapshots_dir.mkdir(exist_ok=True)

    def _path(self, name):
        if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Use a relative workspace file path without parent traversal.')
        from pathlib import PureWindowsPath
        if PureWindowsPath(name).drive or '\\' in name:
            raise ValueError('Use relative paths with forward slashes.')
        original = self.workspace.root / name
        for path in (original, *original.parents):
            if path == self.workspace.root:
                break
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                raise PermissionError('Linked paths are unavailable for file transactions.')
        path = self.workspace.resolve(name)
        if os.path.normcase(str(original.absolute())) != os.path.normcase(str(path)):
            raise PermissionError('Resolved aliases are unavailable for transactions.')
        if path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
            raise PermissionError('Transactions require regular, unlinked files.')
        return path

    def _read(self, name):
        path = self._path(name)
        if not path.exists():
            return None
        with path.open('rb') as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError(f'{name}: exceeds the 1 MB file limit.')
        return data

    def index(self, limit=1000):
        rows = []
        truncated = False
        for directory, dirs, names in os.walk(self.workspace.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED and not (Path(directory)/d).is_symlink() and not getattr(Path(directory)/d, 'is_junction', lambda: False)())
            for name in sorted(names):
                relative = (Path(directory)/name).relative_to(self.workspace.root).as_posix()
                try:
                    path = self._path(relative)
                    if len(rows) >= limit:
                        truncated = True
                        break
                    rows.append({'path':relative, 'bytes':path.stat().st_size, 'extension':path.suffix.lower() or '(none)'})
                except (OSError, ValueError):
                    continue
            if truncated:
                break
        files = {row['path'] for row in rows}
        projects = [label for filename, label in [('pyproject.toml','Python'), ('package.json','Node/JavaScript'), ('Cargo.toml','Rust'), ('go.mod','Go')] if filename in files]
        return {'files':rows, 'count':len(rows), 'truncated':truncated, 'extensions':dict(Counter(row['extension'] for row in rows)), 'project_types':projects}

    def preview(self, name):
        data = self._read(name)
        if data is None:
            raise FileNotFoundError(name)
        if b'\0' in data:
            raise ValueError('Binary files cannot be previewed or edited as text.')
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('Preview supports UTF-8 text only.') from exc

    def _save(self, path, value):
        atomic_bytes(path, json.dumps(value, indent=2).encode('utf-8'))

    def _load(self, path):
        if path.stat().st_size > MAX_TOTAL * 3:
            raise ValueError('Recovery record exceeds its size limit.')
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict):
            raise ValueError('Recovery record must be an object.')
        if value.get('workspace') != str(self.workspace.root):
            raise ValueError('Recovery record belongs to another workspace.')
        if not isinstance(value.get('files'), list) or len(value['files']) > 1000:
            raise ValueError('Invalid recovery file list.')
        seen = set()
        for row in value['files']:
            key = os.path.normcase(str(self._path(row['path'])))
            if key in seen:
                raise ValueError('Duplicate paths in recovery record.')
            seen.add(key)
            for side in ('before', 'after'):
                data = decode(row[side])
                if data is not None and len(data) > MAX_FILE:
                    raise ValueError('Recovery file exceeds size limit.')
                if digest(data) != row[side + '_hash']:
                    raise ValueError('Recovery record checksum mismatch.')
        return value

    def stage(self, changes, expected_hashes=None):
        if not isinstance(changes, dict) or not changes or len(changes) > 20:
            raise ValueError('Stage between one and twenty text files.')
        existing = {}
        context_hashes = {}
        if self.pending_path.exists():
            pending = self._load(self.pending_path)
            if pending['kind'] != 'change':
                raise ValueError('Discard or apply the pending restore before staging edits.')
            existing = {row['path']: row for row in pending['files']}
            context_hashes = dict(pending.get('context_hashes', {}))
        if expected_hashes is not None:
            if not isinstance(expected_hashes, dict) or len(expected_hashes) > 8:
                raise ValueError('Coding context requires at most eight source hashes.')
            context_hashes.update(expected_hashes)
        for name, expected in context_hashes.items():
            if digest(self._read(name)) != expected:
                raise ValueError(f'Conflict: {name} no longer matches coding context.')
        incoming_paths = set()
        for name, text in changes.items():
            if not isinstance(text, str) or '\0' in text:
                raise ValueError('Changes must contain UTF-8 text without binary null bytes.')
            name = self._path(name).relative_to(self.workspace.root).as_posix()
            key = os.path.normcase(name)
            if key in incoming_paths:
                raise ValueError('Duplicate paths in proposed changes.')
            incoming_paths.add(key)
            before = self._read(name)
            if expected_hashes is not None and (name not in expected_hashes or digest(before) != expected_hashes[name]):
                raise ValueError(f'Conflict: {name} no longer matches coding context.')
            if name in existing and digest(before) != existing[name]['before_hash']:
                raise ValueError(f'Conflict: {name} changed since staging; discard and review again.')
            if before is not None:
                self.preview(name)
            after = text.encode('utf-8')
            if len(after) > MAX_FILE:
                raise ValueError('Proposed file exceeds 1 MB.')
            existing[name] = self._row(name, before, after)
        rows = list(existing.values())
        if len(rows) > 20 or sum(len(decode(row['before']) or b'') + len(decode(row['after']) or b'') for row in rows) > MAX_TOTAL:
            raise ValueError('Change set exceeds twenty files or 10 MB.')
        proposal = {'id':uuid.uuid4().hex, 'workspace':str(self.workspace.root), 'kind':'change', 'files':rows, 'context_hashes':context_hashes}
        self._save(self.pending_path, proposal)
        return self.review()

    @staticmethod
    def _row(name, before, after):
        return {'path':name, 'before':encode(before), 'after':encode(after), 'before_hash':digest(before), 'after_hash':digest(after)}

    def review(self):
        if not self.pending_path.exists():
            raise ValueError('No pending changes.')
        proposal = self._load(self.pending_path)
        diffs = []
        summaries = []
        for row in proposal['files']:
            before = (decode(row['before']) or b'').decode('utf-8').splitlines()
            after = (decode(row['after']) or b'').decode('utf-8').splitlines()
            diff = '\n'.join(difflib.unified_diff(before, after, fromfile='before/'+row['path'], tofile='after/'+row['path'], lineterm=''))
            before_bytes, after_bytes = decode(row['before']), decode(row['after'])
            if before_bytes != after_bytes and before == after:
                diff += '\n(Newline/encoding bytes differ.)'
            diff += '\nBefore SHA-256: ' + str(row['before_hash']) + '\nAfter SHA-256: ' + str(row['after_hash'])
            summaries.append({'path':row['path'],'change':'delete' if row['after'] is None else 'create' if row['before'] is None else 'modify',
                              'before_bytes':len(before_bytes) if before_bytes is not None else None,'after_bytes':len(after_bytes) if after_bytes is not None else None,
                              'before_hash':row['before_hash'],'after_hash':row['after_hash'],'diff':diff})
            diffs.append(('REMOVE ' if row['after'] is None else 'FILE ') + row['path'] + '\n' + (diff or '(no text difference)'))
        return {'id':proposal['id'], 'kind':proposal['kind'], 'paths':[row['path'] for row in proposal['files']], 'diff':'\n\n'.join(diffs),'files':summaries,'context_hashes':dict(proposal.get('context_hashes',{}))}

    def discard(self):
        self.pending_path.unlink(missing_ok=True)

    def apply(self, proposal_id):
        proposal = self._load(self.pending_path)
        if proposal['id'] != proposal_id:
            raise ValueError('Proposal changed since review. Review again.')
        for name, expected in proposal.get('context_hashes', {}).items():
            if digest(self._read(name)) != expected:
                raise ValueError(f'Conflict: coding context {name} changed; nothing applied.')
        for row in proposal['files']:
            if digest(self._read(row['path'])) != row['before_hash']:
                raise ValueError(f"Conflict: {row['path']} changed since review; nothing applied.")
        snapshot = dict(proposal, status='applying')
        snapshot_path = self.snapshots_dir / (proposal_id + '.json')
        self._save(snapshot_path, snapshot)
        try:
            for row in proposal['files']:
                if digest(self._read(row['path'])) != row['before_hash']:
                    raise ValueError(f"Concurrent change detected: {row['path']}")
                self._put(row['path'], decode(row['after']))
            snapshot['status'] = 'applied'
            self._save(snapshot_path, snapshot)
            self.discard()
        except Exception as exc:
            snapshot['status'] = 'interrupted'
            self._save(snapshot_path, snapshot)
            raise RuntimeError(f"Apply interrupted. Recovery snapshot: {proposal_id}. {exc}") from exc
        return {'snapshot':proposal_id, 'paths':[row['path'] for row in proposal['files']]}

    def _put(self, name, data):
        path = self._path(name)
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic_bytes(path, data)

    def snapshots(self):
        result = []
        for path in sorted(self.snapshots_dir.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:100]:
            try:
                value = self._load(path)
                result.append({'id':value['id'], 'kind':value['kind'], 'status':value.get('status','saved'), 'files':len(value['files']), 'valid':True})
            except (ValueError, OSError, KeyError, TypeError):
                result.append({'id':path.stem, 'status':'unavailable', 'valid':False,
                               'message':'Invalid, protected or unreadable snapshot. Other snapshots remain available.'})
        return result

    def snapshot(self):
        index = self.index()
        if index['truncated']:
            raise ValueError('Workspace index exceeds 1000 files; snapshot refused.')
        rows, skipped, total = [], [], 0
        for row in index['files']:
            name = row['path']
            try:
                self.preview(name)
                data = self._read(name)
            except (ValueError, OSError):
                skipped.append(name)
                continue
            total += len(data)
            if total > MAX_TOTAL:
                raise ValueError('Snapshot exceeds 10 MB; nothing saved.')
            rows.append(self._row(name, data, data))
        value = {'id':uuid.uuid4().hex,'workspace':str(self.workspace.root),'kind':'workspace','status':'saved','files':rows,'skipped':skipped}
        self._save(self.snapshots_dir/(value['id']+'.json'), value)
        return {'snapshot':value['id'], 'files':len(rows), 'skipped':skipped}

    def prepare_restore(self, snapshot_id):
        if self.pending_path.exists():
            raise ValueError('Discard or apply pending edits before preparing a restore.')
        if not isinstance(snapshot_id, str) or len(snapshot_id) != 32 or any(c not in '0123456789abcdef' for c in snapshot_id):
            raise ValueError('Invalid snapshot ID.')
        original = self._load(self.snapshots_dir/(snapshot_id+'.json'))
        rows = []
        total = 0
        for row in original['files']:
            current = self._read(row['path'])
            if original['kind'] != 'workspace' and digest(current) not in {row['before_hash'],row['after_hash']}:
                raise ValueError(f"Conflict: {row['path']} changed after snapshot; restore refused.")
            target = decode(row['before'])
            if current != target:
                total += len(current or b'') + len(target or b'')
                if total > MAX_TOTAL:
                    raise ValueError('Restore change set exceeds 10 MB.')
                rows.append(self._row(row['path'], current, target))
        if not rows:
            raise ValueError('Snapshot already matches the tracked files.')
        proposal = {'id':uuid.uuid4().hex, 'workspace':str(self.workspace.root), 'kind':'restore', 'source_snapshot':snapshot_id, 'files':rows}
        self._save(self.pending_path, proposal)
        return self.review()
