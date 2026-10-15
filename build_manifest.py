"""Create a deterministic integrity manifest for bundled code and documentation."""
import hashlib,json
import os
from pathlib import Path
from purple_dragon_agent import __version__

def build(root,distribution="source"):
    if distribution not in {"source","windows-onedir"}:raise ValueError("Unknown distribution profile.")
    root=Path(root);rows=[]
    excluded={'conversation-data','.venv','logs','workspace','__pycache__','private-secrets','recovery-backups','verification-results','dist','build','.build-venv','.git'}
    for directory, dirs, names in os.walk(root,followlinks=False):
        dirs[:]=sorted(name for name in dirs if name not in excluded)
        for name in dirs:
            path=Path(directory)/name
            if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
                raise ValueError('Release directories must not be links.')
        for name in sorted(names):
            file=Path(directory)/name;relative=file.relative_to(root)
            if file.suffix in {'.pyc','.secret'} or name in {'RELEASE-MANIFEST.json','user_config.json','guide_state.json','desktop_preferences.json'} or name.startswith('user_config.before-upgrade-'):continue
            if file.is_symlink():raise ValueError('Release files must not be symlinks.')
            if not file.is_file():continue
            digest=hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1_000_000),b''):digest.update(chunk)
            rows.append({'path':relative.as_posix(),'bytes':file.stat().st_size,'sha256':digest.hexdigest()})
    rows.sort(key=lambda row:row['path'])
    (root/'RELEASE-MANIFEST.json').write_text(json.dumps({'schema':1,'version':__version__,'distribution':distribution,'files':rows},indent=2)+'\n')
    return len(rows)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(Path(__file__).resolve().parent));parser.add_argument('--distribution',choices=['source','windows-onedir'],default='source');options=parser.parse_args();print(build(Path(options.root),options.distribution))
