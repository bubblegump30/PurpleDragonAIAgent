"""Native WebView shell over the existing permission-controlled agent core.

Only trusted, bundled UI is loaded. Model and workspace text is rendered as text,
never HTML. The web bridge deliberately exposes a small fixed set of operations.
"""
from __future__ import annotations
import json
import threading
import time
import uuid
from datetime import datetime,timezone
from dataclasses import asdict
from pathlib import Path
from .config import APP_DIR, load_config, save_config, normalize_config
from .workspace import Workspace
from .audit import AuditLog
from .permissions import PermissionEngine
from .tools import ToolRegistry
from .agent import Agent
from .multi_agent import MultiAgentSystem, validate_request
from .security import PROFILES, sandbox_status
from .secrets import SecretsBroker
from .recovery import RecoveryCenter, release_readiness
from .plugin_api import PluginCatalog
from .lm_studio import LMStudioClient
from .reliability import window_geometry, window_chrome, RuntimeLease
from .conversations import ConversationStore
from .model_connection import discover_models, test_inference, ConnectionFailure

TOOLS = frozenset({
    'security_review','sandbox_status',
    'git_status','git_diff','git_preview','git_execute',
    'list_files','read_file','write_file','index_workspace','preview_file',
    'stage_changes','review_changes','apply_changes','discard_changes',
    'snapshot_workspace','list_snapshots','prepare_restore','restore_snapshot',
    'analyze_code','propose_code_changes','rename_python_function',
    'detect_test_framework','preview_tests','run_tests','export_sandbox_tests',
    'preview_project_context','preview_research_context','list_memory','retrieve_memory','save_memory','delete_memory','clear_memory',
    'preview_web','fetch_web','list_web_sources','read_web_source',
    'create_research_brief','clear_web_sources',
})


class DesktopAPI:
    def __init__(self, config=None, app_dir=None, persist=True):
        self._app_dir = Path(app_dir or APP_DIR)
        self._config = config if config is not None else load_config()
        self._persist = persist
        self._window = None
        self._session_profile = 'standard'
        self._secrets = SecretsBroker(self._app_dir/'private-secrets')
        self._recovery = RecoveryCenter(self._app_dir)
        self._plugins = PluginCatalog(self._app_dir/'plugins')
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._chat_cancel = threading.Event()
        self._pending = None
        self._job = None
        self._last_duration = None
        self._workspace_count = None
        self._maximized = False
        self._ready = threading.Event()
        self._event_stamp = None
        self._event_rows = []
        self._connection = None
        self._connection_key = None
        self._connection_busy = False
        self._audit = AuditLog(self._app_dir / 'logs' / 'activity.jsonl')
        self._setup_core()
        self._audit.record('app_started',version=self._config['version'],interface='reference_webview')

    def desktop_preferences(self, changes=None):
        """Passive display settings only; never grants capabilities or changes workspace."""
        from .files import atomic_bytes
        defaults = {'layout': 'fit', 'contrast': False, 'reduce_motion': False}
        def validate(data):
            if not isinstance(data, dict) or set(data) - set(defaults):
                raise ValueError('Unknown desktop preference.')
            if 'layout' in data and data['layout'] not in ('fit', 'readable', 'large'):
                raise ValueError('Unknown display layout.')
            for key in ('contrast', 'reduce_motion'):
                if key in data and type(data[key]) is not bool:
                    raise ValueError(key + ' must be boolean.')
            return data
        if changes is not None:
            validate(changes)
        path = self._app_dir / 'config' / 'desktop_preferences.json'
        with self._lock:
            result = dict(defaults)
            try:
                if path.stat().st_size <= 1024:
                    result.update(validate(json.loads(path.read_text(encoding='utf-8'))))
            except (OSError, ValueError, TypeError, RecursionError):
                pass
            if changes is not None:
                result.update(changes)
                atomic_bytes(path, json.dumps(result).encode('utf-8'))
            return result

    def guide_preferences(self, welcome_seen=None):
        """Read or dismiss passive onboarding; never changes policies or workspace."""
        from .files import atomic_bytes
        if welcome_seen is not None and type(welcome_seen) is not bool:
            raise ValueError('welcome_seen must be a boolean.')
        path = self._app_dir / 'config' / 'guide_state.json'
        with self._lock:
            seen = False
            try:
                if path.stat().st_size <= 1024:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    seen = isinstance(data, dict) and data.get('welcome_seen') is True
            except (OSError, ValueError, RecursionError):
                pass
            if welcome_seen is not None:
                seen = welcome_seen
                atomic_bytes(path, json.dumps({'welcome_seen': seen}).encode('utf-8'))
            return {'welcome_seen': seen}

    def _conversation_store(self):
        return ConversationStore(self._app_dir/'conversation-data', self._workspace.root)

    def conversations(self, action='list', identifier=None, value=None):
        with self._lock:
            if action not in {'list','read','create','rename','delete'}:
                return {'ok':False,'message':'Unknown conversation action.'}
            if action in {'create','rename','delete'} and (self._stop.is_set() or self._is_busy()):
                return {'ok':False,'message':'Wait for the active task to finish.'}
            try:
                store=self._conversation_store()
                if action=='list':data=store.list(value or '')
                elif action=='read':data=store.get(identifier)
                elif action=='create':data=store.create()
                elif action=='rename':
                    if not isinstance(value,str):raise ValueError('Enter a conversation title.')
                    data=store.update(identifier,title=value)
                else:data=store.update(identifier,delete=True)
                return {'ok':True,'data':data}
            except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}

    def cancel_chat(self, identifier):
        with self._lock:
            if not self._job or self._job['id']!=identifier or self._job['kind'] not in {'task','draft'} or self._job['state']!='running':
                return {'ok':False,'message':'This conversation task is no longer running.'}
            self._chat_cancel.set()
            self._job['label']='Stopping — waiting for current request or operation'
            if self._pending:
                self._pending['approved']=False
                self._pending['event'].set()
                self._pending=None
            return {'ok':True,'message':'Stop requested. Waiting for the current model request or operation to return; no further tool steps will start.'}

    def _setup_core(self):
        previous_team=self._team.snapshot() if hasattr(self,'_team') else None
        previous_workspace=self._workspace.root if hasattr(self,'_workspace') else None
        self._plugins.reviews.clear()
        self._recovery.previews.clear()
        path = Path(self._config['workspace'])
        if not path.is_absolute():
            path = self._app_dir / path
        self._workspace = Workspace(path)
        self._workspace.security_options = self._config.get('security',{'protect_secret_files':True})
        self._permissions = PermissionEngine(self._config['permissions'], self._ask)
        self._permissions.restricted = set(self._config.get('security',{}).get('denied_tools',[])) | PROFILES[self._session_profile]
        self._tools = ToolRegistry(self._workspace, self._permissions, self._audit)
        self._tools.memory_options = dict(self._config['project_memory'])
        self._tools.research_options = dict(self._config['research'])
        model = self._config['lm_studio']
        self._model = LMStudioClient(**{k:model[k] for k in ('endpoint','model','temperature','timeout_seconds','max_tokens')}) if model['enabled'] else None
        self._tools.model = self._model
        self._agent = Agent(self._tools, self._model)
        self._team = MultiAgentSystem(self._tools)
        if previous_workspace==self._workspace.root and previous_team and previous_team['state'] in {'blocked','completed','cancelled'}:
            self._team.current=previous_team
        key=(model['endpoint'],model['model'],model['enabled'],model.get('temperature'),model.get('timeout_seconds'),model.get('max_tokens'))
        if key != self._connection_key:
            self._connection_key=key
            self._connection={'status':'configured' if model['enabled'] else 'disabled','models':[],'message':'Not tested in this session.','checked_at':None}

    def _is_busy(self):
        return self._connection_busy or bool(self._job and self._job['state']=='running') or self._tools.runner.snapshot()['state'] in {'starting','running'}

    def _ask(self, action, context):
        request = {'id':uuid.uuid4().hex, 'action':action, 'context':context,
                   'event':threading.Event(), 'approved':False}
        with self._lock:
            if self._stop.is_set() or (self._chat_cancel.is_set() and self._job and self._job['kind'] in {'task','draft'}):
                return False
            self._pending = request
        deadline = time.monotonic() + 300
        while not request['event'].wait(.1):
            if self._stop.is_set() or time.monotonic() >= deadline:
                break
        with self._lock:
            if self._pending is request:
                self._pending = None
            return request['approved'] and not self._stop.is_set()

    def ui_ready(self):
        if not self._ready.is_set():
            self._ready.set()
            self._audit.record('desktop_ui_ready', version=self._config['version'])
            try:
                (self._app_dir/'logs/startup-error.log').unlink(missing_ok=True)
            except OSError:
                pass
        return {'ok':True}

    def _events(self):
        try:
            stat=self._audit.path.stat()
            stamp=(stat.st_mtime_ns,stat.st_size)
        except OSError:
            return []
        if stamp != self._event_stamp:
            try: self._event_rows=self._audit.tail(6)
            except OSError: self._event_rows=[]
            self._event_stamp=stamp
        return list(self._event_rows)

    def _platform_status(self):
        from .platform_center import platform_status
        return platform_status(self._config, self._connection, self._workspace_count,
            self._is_busy(), self._pending is not None, self._session_profile,
            len(self._permissions.restricted), self._job)

    def platform_overview(self):
        """Passive catalog and session metadata. No file discovery, model or tool call."""
        from .platform_center import feature_catalog
        with self._lock:
            return {'status':self._platform_status(), 'features':feature_catalog()}

    def state(self):
        with self._lock:
            pending = self._pending
            policies = self._permissions.snapshot()
            job = self._job
            return {
                'native_window_frame':__import__('sys').platform=='win32',
                'platform_status':self._platform_status(),
                'version':self._config['version'], 'workspace':str(self._workspace.root),
                'files':self._workspace_count, 'busy':self._is_busy(),
                'job': dict(job) if job else None,
                'approval':{k:pending[k] for k in ('id','action','context')} if pending else None,
                'duration':self._last_duration,
                'model':self._config['lm_studio']['model'] if self._model else 'Fallback Planner',
                'model_enabled':self._model is not None,
                'asks':sum(v=='ask' for v in policies.values()),
                'denies':sum(v=='deny' for v in policies.values()),
                'connection':dict(self._connection, busy=self._connection_busy),
                'policies':policies, 'events':self._events(),
                'config':json.loads(json.dumps(self._config)),
                'runner':self._tools.runner.snapshot(),
                'team':self._team.snapshot(),
                'security':{'profile':self._session_profile,'restrictions':sorted(self._permissions.restricted),'sandbox':sandbox_status(),'secrets':self._secrets.list()},
            }

    def resolve_approval(self, request_id, approved):
        with self._lock:
            if type(approved) is not bool:
                return {'ok':False,'message':'Approval must be an explicit boolean.'}
            request = self._pending
            if not request or request['id'] != request_id:
                return {'ok':False,'message':'Approval expired or is no longer current.'}
            # Consume once; replay cannot approve the next operation.
            self._pending = None
            request['approved'] = approved
            request['event'].set()
            return {'ok':True}

    def start_job(self, kind, payload):
        if not isinstance(kind,str) or kind not in {'task','tool','draft','team','recovery','plugin'} or not isinstance(payload, dict):
            return {'ok':False,'message':'Invalid operation.'}
        if kind in {'task','draft','tool'} and set(payload)-({'name','args'} if kind=='tool' else {'task','conversation_id'}):
            return {'ok':False,'message':'Unsupported operation fields.'}
        if kind in {'plugin','recovery','tool'} and not isinstance(payload.get('name'),str):
            return {'ok':False,'message':'Operation name must be text.'}
        if kind == 'plugin' and (set(payload)-{'name','plugin_id','inputs','review_id'} or payload.get('name') not in {'list','preview','execute'}):
            return {'ok':False,'message':'Invalid plugin operation.'}
        if kind == 'recovery' and (set(payload)-{'name','backup_id','review_id'} or payload.get('name') not in {'trust','readiness','list_backups','backup','preview_restore','preview_reset','restore'}):
            return {'ok':False,'message':'Invalid recovery operation.'}
        if kind == 'team':
            if set(payload)=={'plan_id'}:
                if not isinstance(payload['plan_id'],str):return {'ok':False,'message':'Invalid plan review.'}
            else:
                try: payload=validate_request(payload)
                except (ValueError, TypeError) as exc: return {'ok':False,'message':str(exc)}
        if kind == 'tool' and payload.get('name') not in TOOLS:
            return {'ok':False,'message':'Tool is unavailable in the desktop bridge.'}
        if kind == 'tool' and not isinstance(payload.get('args', {}), dict):
            return {'ok':False,'message':'Tool arguments must be an object.'}
        if kind in {'task','draft'} and (not isinstance(payload.get('task'), str) or not payload['task'].strip() or len(payload['task']) > 20000):
            return {'ok':False,'message':'Enter a task of 1–20,000 characters.'}
        try: payload_size=len(json.dumps(payload))
        except (TypeError,ValueError):return {'ok':False,'message':'Operation must contain valid JSON data.'}
        payload=json.loads(json.dumps(payload))
        if payload_size > 500000:
            return {'ok':False,'message':'Operation is too large.'}
        with self._lock:
            if self._stop.is_set() or self._is_busy():
                return {'ok':False,'message':'Wait for the active task to finish.'}
            if kind == 'team':
                if 'plan_id' in payload:
                    try:
                        plan=self._team.consume(payload['plan_id'])
                        payload={'task':plan['request']['task'],'_prepared':plan}
                    except ValueError as exc:return {'ok':False,'message':str(exc)}
                self._team.cancelled.clear()
            if kind == 'plugin': self._plugins.cancelled.clear()
            if kind in {'task','draft'}:
                self._chat_cancel.clear()
                if payload.get('conversation_id') is not None:
                    try:
                        row=self._conversation_store().get(payload['conversation_id'])
                        if len(row['messages'])>198:raise ValueError('Conversation is full. Start a new chat.')
                        payload['history']=row['messages'][-20:]
                        self._conversation_store().update(row['id'], title=payload['task'].strip().splitlines()[0][:80] if not row['messages'] and row['title']=='New conversation' else row['title'], messages=row['messages']+[{'role':'user','text':payload['task']}])
                    except (OSError,ValueError) as exc:return {'ok':False,'message':str(exc)}
            identifier = uuid.uuid4().hex
            self._job = {'id':identifier,'state':'running','kind':kind,'label':(payload.get('task') if kind in {'task','draft','team'} else payload.get('name','Task'))[:100], 'result':None}
        try:
            threading.Thread(target=self._work,args=(identifier,kind,payload),daemon=True).start()
        except RuntimeError:
            with self._lock:
                self._job.update(state='finished',result={'ok':False,'message':'Could not start the task worker. No tools executed.','data':None})
            return {'ok':False,'message':'Could not start the task worker. Retry after freeing system resources.'}
        return {'ok':True,'id':identifier}

    def _work(self, identifier, kind, payload):
        started = time.monotonic()
        try:
            if kind == 'plugin':
                result = self._plugin_work(payload)
            elif kind == 'recovery':
                result = self._recovery_work(payload)
            elif kind == 'team':
                result = self._team.run_prepared(payload['_prepared']) if '_prepared' in payload else self._team.run(payload)
            elif kind == 'draft':
                if not self._model:
                    raise ValueError('Enable a local model in Settings before drafting text.')
                text = self._model.chat('You are a local writing assistant. Draft the requested text only. You have no tools and cannot execute actions.', payload['task'])
                result = {'ok':True,'message':text,'data':None}
            elif kind == 'task':
                run = self._agent.run(payload['task'].strip(), history=payload.get('history'), cancelled=self._chat_cancel.is_set)
                result = {'ok':run.ok,'message':run.summary,
                          'data':[{'step':step,'result':asdict(value)} for step,value in run.results]}
                for step,value in run.results:
                    if step['tool']=='list_files' and value.ok and isinstance(value.data,list):
                        self._workspace_count = len(value.data)
            else:
                value = self._tools.execute(payload['name'], payload.get('args',{}))
                result = asdict(value)
                if value.ok and payload['name']=='list_files' and isinstance(value.data,list):
                    self._workspace_count = len(value.data)
            if kind in {'task','draft'} and self._chat_cancel.is_set():
                result={'ok':False,'message':'Stopped. Any operation already in progress may have completed; inspect its effects before retrying.','data':None}
            if kind in {'task','draft'} and getattr(self._model,'last_finish_reason',None)=='length' and not self._chat_cancel.is_set():
                result['message']+='\n\nResponse reached the token limit. It may be incomplete. Raise the saved response limit or ask for a smaller answer.'
            self._audit.record('desktop_operation_finished',kind=kind,ok=result['ok'])
        except Exception as exc:
            result = {'ok':False,'message':f'{type(exc).__name__}: {exc}','data':None}
            try: self._audit.record('desktop_operation_error',error=repr(exc))
            except OSError:
                result['message'] += ' Audit storage is unavailable; inspect operation effects before retrying.'
        if kind in {'task','draft'} and payload.get('conversation_id'):
            try:
                with self._lock:
                    if self._chat_cancel.is_set():result={'ok':False,'message':'Stopped. Any operation already in progress may have completed; inspect its effects before retrying.','data':None}
                    store=self._conversation_store();row=store.get(payload['conversation_id'])
                    text=result['message']
                    if result.get('data'):text+='\n\n'+json.dumps(result['data'],ensure_ascii=False)
                    if len(text)>100000:text=text[:99900]+'\n[Saved output truncated; inspect tool output for full details.]'
                    store.update(row['id'],messages=row['messages']+[{'role':'assistant','text':text}])
            except (OSError,ValueError) as exc:
                result['message']+='\nConversation could not be saved: '+str(exc)
        with self._lock:
            self._last_duration = round(time.monotonic()-started,2)
            if self._job and self._job['id']==identifier:
                self._job['state']='finished'
                self._job['result']=result

    def _plugin_work(self,payload):
        if payload['name']=='list':data=self._plugins.list()
        elif payload['name']=='preview':data=self._plugins.preview(payload.get('plugin_id'),payload.get('inputs',{}))
        else:return self._plugins.execute(payload.get('review_id'),self._tools)
        return {'ok':True,'message':'Declarative plugin contract v1. Review tools and inputs before running.','data':data}

    def cancel_plugin(self):
        with self._lock:
            if not self._job or self._job['kind']!='plugin' or self._job['state']!='running':return {'ok':False,'message':'No plugin workflow is running.'}
            self._plugins.cancelled.set();self._tools.runner.cancel()
            if self._pending:
                self._pending['approved']=False;self._pending['event'].set();self._pending=None
        return {'ok':True,'message':'Cancellation requested; an active local model request may finish first.'}

    def _recovery_work(self,payload):
        name=payload['name']
        if name=='trust':
            from .release_trust import trust_report
            data=trust_report(self._app_dir)
            return {'ok':data['integrity']['status']!='blocked','message':'Local release evidence; publisher identity and Windows acceptance remain unverified.','data':data}
        if name=='readiness':
            data=release_readiness(self._app_dir)
            return {'ok':data['status']!='blocked','message':'Local candidate readiness checks; pending acceptance remains explicit.','data':data}
        if name=='list_backups':data=self._recovery.list()
        elif name=='backup':data=self._recovery.backup(self._config)
        elif name=='preview_restore':data=self._recovery.preview(payload.get('backup_id'),self._config)
        elif name=='preview_reset':data=self._recovery.preview(None,self._config,reset=True)
        else:
            if self._session_profile!='standard':raise PermissionError('Settings restore is disabled by this session profile.')
            token=payload.get('review_id');proposal=self._recovery.previews.get(token)
            if not proposal:raise ValueError('Prepare and review settings recovery first.')
            decision=self._permissions.check('restore_settings',{'review_id':token,**proposal['review']},require_approval=True)
            self._audit.record('permission_decision',tool='restore_settings',approved=decision.approved,policy=decision.policy)
            if not decision.approved:
                return {'ok':False,'message':'Settings recovery approval rejected.','data':None}
            restored=self._recovery.apply(token,self._config)
            with self._lock:
                self._config=restored['settings'];self._setup_core();self._workspace_count=None
            data={'rollback':restored['rollback']}
            self._audit.record('settings_restored',backup_id=proposal['backup_id'])
        return {'ok':True,'message':'Settings recovery operation complete.','data':data}

    def set_session_profile(self,profile):
        with self._lock:
            if not isinstance(profile,str) or profile not in PROFILES: return {'ok':False,'message':'Unknown session profile.'}
            if self._stop.is_set() or self._is_busy(): return {'ok':False,'message':'Wait for the active operation to finish.'}
            self._session_profile=profile
            self._team.reviews.clear()
            self._permissions.restricted=set(self._config.get('security',{}).get('denied_tools',[])) | PROFILES[profile]
            self._audit.record('session_scope_changed',profile=profile)
        return {'ok':True,'message':'Session scope updated. Base policies and mandatory approvals still apply.'}

    def manage_secret(self,operation,name,value=None):
        # Human desktop controls only. Models and tools never receive vault access.
        with self._lock:
            if self._stop.is_set() or self._is_busy(): return {'ok':False,'message':'Wait for the active operation to finish.'}
            if self._session_profile!='standard': return {'ok':False,'message':'Secret changes are disabled by this session scope.'}
            try:
                if operation=='save': result=self._secrets.save(name,value)
                elif operation=='delete': result=self._secrets.delete(name)
                else: raise ValueError('Unknown secret operation.')
                self._audit.record('secret_metadata_changed',operation=operation,name=result['name'])
                return {'ok':True,'message':'Secret metadata updated. Values are never returned.'}
            except Exception:
                return {'ok':False,'message':'Secret operation failed. Check the name, value length, and Windows DPAPI availability.'}

    def prepare_team(self, request=None, retry=False):
        if type(retry) is not bool:return {'ok':False,'message':'Retry must be an explicit boolean.'}
        with self._lock:
            if self._stop.is_set() or self._is_busy():return {'ok':False,'message':'Wait for the active operation to finish.'}
            try:
                plan=self._team.prepare(request,retry)
                return {'ok':True,'message':'Plan prepared. Review its fixed steps and limitations before starting.','data':plan}
            except (ValueError,TypeError) as exc:return {'ok':False,'message':str(exc)}

    def control_team(self, action):
        with self._lock:
            if not isinstance(action,str) or action not in {'pause','resume'}:return {'ok':False,'message':'Choose pause or resume.'}
            if not self._job or self._job['kind']!='team' or self._job['state']!='running':return {'ok':False,'message':'No active plan is running.'}
            ok=self._team.pause() if action=='pause' else self._team.resume()
            return {'ok':ok,'message':('Pause requested. The active tool or approval must finish before the next step pauses.' if action=='pause' else 'Resume requested. Existing permission gates remain active.') if ok else 'The current plan cannot use this control.'}

    def cancel_team(self):
        with self._lock:
            if not self._job or self._job['kind']!='team' or self._job['state']!='running':
                return {'ok':False,'message':'No team is running.'}
            self._team.cancel()
            if self._pending:
                self._pending['approved']=False
                self._pending['event'].set()
                self._pending=None
        return {'ok':True,'message':'Cancellation requested. An active model request finishes before stopping.'}

    def probe_model(self, inference=False):
        if type(inference) is not bool:
            return {'ok':False,'message':'Invalid connection-test request.'}
        with self._lock:
            if self._stop.is_set() or self._is_busy():
                return {'ok':False,'message':'Wait for the active operation to finish.'}
            model=dict(self._config['lm_studio'])
            if inference and not model['enabled']:
                return {'ok':False,'message':'Enable and save the local connector before testing inference.'}
            self._connection_busy=True
            self._connection=dict(self._connection,status='testing',error_code=None,started_at=time.time(),phase='inference' if inference else 'discovery',timeout_seconds=model['timeout_seconds'] if inference else 5,message='Testing selected model…' if inference else 'Requesting the local model list…')
        try:
            threading.Thread(target=self._probe_worker,args=(model,inference),daemon=True).start()
        except RuntimeError:
            with self._lock:
                self._connection_busy=False
                self._connection.update(status='error',message='Could not start the connection worker.',error_code='worker_start')
            return {'ok':False,'message':'Could not start the connection worker.'}
        return {'ok':True,'message':'Connection check started.'}

    def _probe_worker(self, model, inference):
        try:
            data=test_inference(model['endpoint'],model['model'],model['timeout_seconds']) if inference else discover_models(model['endpoint'])
            status='verified' if inference else 'server_ready'
            message='Selected model answered the test request.' if inference else 'Server reachable. Model listing does not prove inference is working.'
            if not data['models']:
                status='no_models';message='Server reachable, but it reported no available models.'
            result=dict(data,status=status,message=message,error_code=None)
        except (ConnectionFailure,ValueError,OSError) as exc:
            result=dict(getattr(exc,'details',{}),status='error',models=getattr(exc,'details',{}).get('models',[]),message=str(exc),error_code=getattr(exc,'code','invalid_endpoint'),checked_at=datetime.now(timezone.utc).isoformat())
        except Exception:
            result={'status':'error','models':[],'message':'Unexpected local connection error. Run startup diagnostics.','error_code':'unexpected','checked_at':None}
        with self._lock:
            result['phase']='inference' if inference else 'discovery'
            result['timeout_seconds']=model['timeout_seconds'] if inference else 5
            self._connection=result
            self._connection_busy=False
        self._audit.record('model_connection_test',inference=inference,status=result['status'],error_code=result.get('error_code'))

    def model_context(self):
        with self._lock:
            receipt=getattr(self._model,'last_request',None)
            return {'ok':True,'data':json.loads(json.dumps(receipt)) if isinstance(receipt,dict) else None,
                    'message':'No attempted model request is recorded in this connector session.' if not receipt else 'Last attempted model request; not proof of receipt or use.'}

    def model_diagnostics(self):
        """Local-only report: no network, project content, credential data or paths."""
        with self._lock:
            model=self._config['lm_studio']
            connection=self._connection or {}
            try:
                LMStudioClient(model['endpoint'],'diagnostics')
                endpoint=model['endpoint']
            except ValueError:endpoint='Invalid endpoint; update the local server address.'
            return {'ok':True,'data':{
                'enabled':model['enabled'],'endpoint':endpoint,'model':model['model'],
                'temperature':model['temperature'],'max_tokens':model['max_tokens'],
                'timeout_seconds':model['timeout_seconds'],'status':connection.get('status'),
                'phase':connection.get('phase'),'error_code':connection.get('error_code'),
                'checked_at':connection.get('checked_at'),'listed_models':connection.get('models',[]),
                'listing_latency_ms':connection.get('latency_ms'),'inference_latency_ms':connection.get('inference_ms'),
                'last_finish_reason':getattr(self._model,'last_finish_reason',None),
                'note':'Listing is not proof a model is loaded. Verification is the last tiny inference test, not continuous monitoring. No hardware or actual context-window telemetry is reported.'}}

    def save_settings(self, changes):
        if not isinstance(changes,dict):
            return {'ok':False,'message':'Settings must be an object.'}
        if set(changes)-{'lm_studio','permissions','project_memory','research','security'}:
            return {'ok':False,'message':'Unsupported setting.'}
        with self._lock:
            if self._stop.is_set() or self._is_busy():
                return {'ok':False,'message':'Wait for the task to finish before changing settings.'}
            try:
                candidate = json.loads(json.dumps(self._config))
                for key,value in changes.items():
                    if not isinstance(value,dict):
                        raise ValueError('Settings sections must be objects.')
                    if set(value)-set(candidate[key]):
                        raise ValueError(f'Unknown {key} setting.')
                    candidate[key].update(value)
                normalized = normalize_config(candidate,json.loads((self._app_dir/'config/default_config.json').read_text()))
                if self._persist:
                    self._recovery.backup(self._config,'Before settings change')
                    save_config(normalized,self._app_dir/'config/user_config.json')
                self._config = normalized
                self._setup_core()
                self._audit.record('settings_changed',interface='reference_webview')
                return {'ok':True,'message':'Settings saved.'}
            except Exception as exc:
                return {'ok':False,'message':str(exc)}

    def choose_workspace(self):
        with self._lock:
            if self._stop.is_set() or self._is_busy():
                return {'ok':False,'message':'Wait for the active task to finish.'}
            if not self._window:
                return {'ok':False,'message':'Folder selection requires the desktop window.'}
            import webview
            selected = self._window.create_file_dialog(webview.FileDialog.FOLDER)
            if not selected:
                return {'ok':True,'message':'Workspace unchanged.'}
            path = Path(selected[0]).resolve()
            candidate=json.loads(json.dumps(self._config))
            candidate['workspace']=str(path)
            try:
                if self._persist:
                    self._recovery.backup(self._config,'Before workspace change')
                    save_config(candidate,self._app_dir/'config/user_config.json')
            except (OSError,ValueError,RuntimeError) as exc:
                return {'ok':False,'message':f'Workspace settings were not changed: {exc}'}
            self._config=candidate
            self._setup_core()
            self._workspace_count = None
            self._audit.record('workspace_changed',workspace=str(path))
            return {'ok':True,'message':'Workspace selected.'}

    def cancel_tests(self):
        self._tools.runner.cancel()
        return {'ok':True,'message':'Test cancellation requested.'}

    def window_action(self, action):
        if not self._window:
            return {'ok':False,'message':'No native window.'}
        if action == 'minimize':
            self._window.minimize()
        elif action == 'maximize':
            if self._maximized:
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
        elif action == 'close':
            self._shutdown()
            self._window.destroy()
        else:
            return {'ok':False,'message':'Unknown window action.'}
        return {'ok':True}

    def _shutdown(self):
        self._stop.set()
        self._team.cancel()
        self._plugins.cancelled.set()
        with self._lock:
            if self._pending:
                self._pending['event'].set()
        self._tools.runner.cancel()
        if self._tools._git_agent is not None:self._tools._git_agent.cancel()


def run_desktop():
    with RuntimeLease(APP_DIR):
        return _run_desktop()


def _run_desktop():
    import webview
    from .display import enable_high_dpi
    enable_high_dpi()
    api = DesktopAPI()
    webview.settings['ALLOW_DOWNLOADS'] = False
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
    webview.settings['DRAG_REGION_DIRECT_TARGET_ONLY'] = True
    try:
        screen = webview.screens[0]
        width, height, minimum = window_geometry(screen.width, screen.height)
    except (IndexError, AttributeError):
        width, height, minimum = 1672, 1010, (800,500)
    window = webview.create_window(
        'Purple Dragon AI Agent', str(APP_DIR/'frontend/index.html'), js_api=api,
        width=width,height=height,min_size=minimum,**window_chrome(__import__('sys').platform),
        shadow=True,background_color='#02030B',text_select=True,zoomable=False,
    )
    api._window = window
    def maximized():
        api._maximized = True
    def restored():
        api._maximized = False
    window.events.maximized += maximized
    window.events.restored += restored
    window.events.closing += api._shutdown
    def watch_startup():
        if not api._ready.wait(30) and not api._stop.is_set():
            api._shutdown()
            window.destroy()
    watcher=threading.Thread(target=watch_startup,daemon=True)
    watcher.start()
    webview.start(gui='edgechromium' if __import__('sys').platform=='win32' else None,
                  private_mode=True,debug=False,icon=str(APP_DIR/'assets/purple_dragon_ai.ico'))

    if not api._ready.is_set():
        raise RuntimeError('The desktop window did not establish its UI bridge. Run Diagnose-Startup.bat; verify the WebView2 runtime and local frontend files.')
