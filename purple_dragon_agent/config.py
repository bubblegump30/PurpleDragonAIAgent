from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import json
import os
import sys
import tempfile
from . import __version__
from .lm_studio import LMStudioClient
from .research import normalize_options
from .security import normalize_security

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / 'config'
DEFAULT_CONFIG = CONFIG_DIR / 'default_config.json'
USER_CONFIG = CONFIG_DIR / 'user_config.json'


def normalize_config(saved: dict, defaults: dict) -> dict:
    if not isinstance(saved, dict):
        raise ValueError('Settings must be a JSON object. Run Diagnose-Startup.bat for details.')
    result = deepcopy(defaults)
    if isinstance(saved.get('workspace'), str) and saved['workspace'].strip():
        result['workspace'] = saved['workspace']
    policies = saved.get('permissions', {})
    if not isinstance(policies, dict):
        raise ValueError('Permission settings must be an object.')
    for action in result['permissions']:
        if action in policies:
            value = policies[action]
            result['permissions'][action] = value if value in ('allow', 'ask', 'deny') else 'deny'
    lm = saved.get('lm_studio', {})
    if not isinstance(lm, dict):
        raise ValueError('Local model settings must be an object.')
    for key in result['lm_studio']:
        if key in lm:
            result['lm_studio'][key] = lm[key]
    model = result['lm_studio']
    if not isinstance(model['enabled'], bool):
        raise ValueError('Model enabled setting must be true or false.')
    if not isinstance(model['model'], str):
        raise ValueError('Model name must be text.')
    if not isinstance(model['endpoint'], str):
        raise ValueError('Model endpoint must be text.')
    if not type(model['temperature']) in (int, float) or not 0 <= model['temperature'] <= 2:
        raise ValueError('Model temperature must be between 0 and 2.')
    if type(model['timeout_seconds']) is not int or not 1 <= model['timeout_seconds'] <= 300:
        raise ValueError('Model timeout must be between 1 and 300 seconds.')
    if type(model.get('max_tokens')) is not int or not 1 <= model['max_tokens'] <= 16384:
        raise ValueError('Response limit must be between 1 and 16,384 tokens.')
    profiles=model.get('profiles')
    if not isinstance(profiles,dict) or len(profiles)>32:
        raise ValueError('Use at most 32 saved model profiles.')
    for identifier,profile in profiles.items():
        if not isinstance(identifier,str) or not identifier.strip() or len(identifier)>512 or not isinstance(profile,dict) or set(profile)!={'temperature','timeout_seconds','max_tokens'}:
            raise ValueError('Invalid model profile.')
        LMStudioClient('http://127.0.0.1:1234/v1/chat/completions',identifier,**profile)
    if model['enabled']:
        LMStudioClient(model['endpoint'], model['model'])
    memory = saved.get('project_memory', {})
    if not isinstance(memory,dict):raise ValueError('Project memory settings must be an object.')
    result.setdefault('project_memory',{'use_context':False,'record_history':True})
    for key in ('use_context','record_history'):
        if key in memory:
            if type(memory[key]) is not bool:raise ValueError('Project memory switches must be true or false.')
            result['project_memory'][key]=memory[key]
    result['research']=normalize_options(saved.get('research',defaults.get('research',{})))
    result['security'] = normalize_security(saved.get('security',defaults.get('security',{})),result['permissions'])
    result['version'] = __version__
    return result


def load_config() -> dict:
    defaults = json.loads(DEFAULT_CONFIG.read_text(encoding='utf-8'))
    if not USER_CONFIG.exists():
        config = normalize_config({}, defaults)
        save_config(config)
        return config
    try:
        saved = json.loads(USER_CONFIG.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON in {USER_CONFIG}. Your settings were preserved. Correct the file or rename it to create fresh defaults.') from exc
    return normalize_config(saved, defaults)


def save_config(config: dict, destination: Path | None = None) -> None:
    target = Path(destination) if destination is not None else USER_CONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, filename = tempfile.mkstemp(prefix='settings-', suffix='.tmp', dir=target.parent)
    path = Path(filename)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, target)
    finally:
        path.unlink(missing_ok=True)
