"""Bounded local release evidence, with no network, processes or credential reads."""
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import hashlib
import platform
import sys
from . import __version__
from .recovery import release_readiness


def webview2_evidence():
    if sys.platform != 'win32':
        return {'status':'not_windows', 'note':'Windows WebView2 was not tested on this platform.'}
    import winreg
    versions = set()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\EdgeUpdate\Clients', 0, winreg.KEY_READ | view) as clients:
                    for index in range(128):
                        try:
                            name = winreg.EnumKey(clients, index)
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(clients, name) as client:
                                label = winreg.QueryValueEx(client, 'name')[0]
                                value = winreg.QueryValueEx(client, 'pv')[0]
                                if isinstance(label,str) and 'webview2' in label.lower() and isinstance(value,str) and len(value)<=80:
                                    versions.add(value)
                        except OSError:
                            continue
            except OSError:
                continue
    return {'status':'registry_detected' if versions else 'not_detected', 'versions':sorted(versions),
            'note':'Registry evidence is a hint, not proof of a working renderer. Detection can miss custom installations. Run Windows GUI acceptance.'}


def trust_report(root):
    root = Path(root)
    integrity = release_readiness(root)
    manifest = root/'RELEASE-MANIFEST.json'
    manifest_hash = None
    try:
        if manifest.stat().st_size<=2_000_000 and not manifest.is_symlink():
            manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    except OSError:
        pass
    dependencies = {}
    for package in ('pywebview','pythonnet'):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = 'not found in package metadata (may be bundled)'
    error = root/'logs/startup-error.log'
    try:
        error_state = {'present':error.is_file(), 'bytes':error.stat().st_size if error.is_file() else 0}
    except OSError:
        error_state = {'present':None, 'note':'Startup log metadata unavailable.'}
    return {'version':__version__, 'checked_at':datetime.now(timezone.utc).isoformat(),
            'integrity':integrity, 'manifest_sha256':manifest_hash,
            'publisher_verification':{'status':'not_verified' if getattr(sys,'frozen',False) else 'not_applicable_source',
                'note':'This report does not inspect Authenticode or establish publisher identity. No signing certificate is supplied by this source release.'},
            'runtime':{'platform':platform.system(),'python':platform.python_version(),'architecture':platform.machine(),
                'frozen':bool(getattr(sys,'frozen',False)),'dependencies':dependencies},
            'webview2':webview2_evidence(), 'startup_error':error_state,
            'privacy':'Contains local release/runtime evidence and log metadata only. No settings, workspace text, credentials or raw startup logs are included.',
            'limitations':['A local manifest can be replaced together with its files; matching hashes do not establish provenance.',
                'A separately obtained ZIP SHA-256 detects byte differences only when the expected hash comes from a trusted source.',
                'No Defender, SmartScreen, antivirus, signing or Windows acceptance result is claimed.']}
