from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from .files import FileAgent, atomic_bytes
import json
import uuid
from .coding import CodingAgent
from .git_agent import GitAgent
from .runner import TestRunner
from .memory import ProjectMemory
from .research import ResearchAgent, fetch_page, validate_url, MAX_SOURCES
from .sandbox import export_session


from .workspace import Workspace
from .permissions import PermissionEngine
from .audit import AuditLog

@dataclass
class ToolResult:
    ok: bool
    message: str
    data: object = None

class ToolRegistry:
    def __init__(self, workspace: Workspace, permissions: PermissionEngine, audit: AuditLog, storage: Path | None = None):
        self.workspace = workspace
        self.permissions = permissions
        self.audit = audit
        self.storage = storage or (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "PurpleDragonAIAgent" / "recovery")
        self._files = None
        self.model = None
        self.runner = TestRunner(workspace)
        self.memory_options = {'use_context':False,'record_history':True}
        self._memory = None
        self.research_options={'enabled':False,'allowed_domains':[],'denied_domains':[]}
        self._research=None
        self._git_agent=None

    @property
    def files(self):
        if self._files is None:
            self._files = FileAgent(self.workspace, self.storage)
        return self._files

    @property
    def memory(self):
        if self._memory is None:
            self._memory = ProjectMemory(self.files.storage,self.workspace.root)
        return self._memory

    def project_context(self,query):
        if not self.memory_options.get('use_context',False):
            return {'enabled':False,'entries':[],'bytes':0}
        result=self.execute('retrieve_memory',{'query':query})
        if not result.ok:
            return {'enabled':True,'entries':[],'bytes':0,'error':result.message}
        return dict(result.data,enabled=True)

    def record_history(self,task,results):
        if not self.memory_options.get('record_history',True):return
        try:
            decision=self.permissions.check('record_task_history',{'tool':'record_task_history','args':{'task_label':str(task).split(' :: ',1)[0][:500]}})
            if decision.approved:
                entry=self.memory.record_history(task,results)
                self.audit.record('task_history_recorded',entry_id=entry)
        except Exception as exc:
            try:self.audit.record('task_history_error',error=repr(exc))
            except Exception:pass

    @property
    def research(self):
        if self._research is None:self._research=ResearchAgent(self.files.storage)
        return self._research

    @property
    def git_agent(self):
        if self._git_agent is None:self._git_agent=GitAgent(self.workspace)
        return self._git_agent

    def execute(self, name: str, args: dict | None = None) -> ToolResult:
        args = {} if args is None else args
        handlers = {
            "security_review": self._security_review, "sandbox_status": self._sandbox_status,
            "git_status": self._git_status, "git_diff": self._git_diff,
            "git_preview": self._git_preview, "git_execute": self._git_execute,
            "list_files": self._list_files, "read_file": self._read_file,
            "write_file": self._write_file, "run_tests": self._run_tests,
            "run_command": self._run_command, "index_workspace": self._index,
            "preview_file": self._preview, "stage_changes": self._stage,
            "review_changes": self._review, "apply_changes": self._apply,
            "discard_changes": self._discard, "snapshot_workspace": self._snapshot,
            "list_snapshots": self._snapshots, "prepare_restore": self._prepare_restore,
            "restore_snapshot": self._apply,
            "analyze_code": self._analyze_code,
            "propose_code_changes": self._propose_code,
            "rename_python_function": self._rename_code,
            "detect_test_framework": self._detect_tests,
            "preview_tests": self._preview_tests,
            "export_sandbox_tests": self._export_sandbox,
            "list_memory": self._list_memory,
            "retrieve_memory": self._retrieve_memory,
            "preview_project_context": self._preview_project_context,
            "save_memory": self._save_memory,
            "delete_memory": self._delete_memory,
            "clear_memory": self._clear_memory,
            "preview_web": self._preview_web,
            "fetch_web": self._fetch_web,
            "list_web_sources": self._list_web,
            "read_web_source": self._read_web,
            "preview_research_context": self._preview_research_context,
            "create_research_brief": self._brief_web,
            "clear_web_sources": self._clear_web,
        }
        if name not in handlers:
            self.audit.record("tool_unknown", tool=name)
            return ToolResult(False, f"Unknown or unavailable tool: {name}")
        if not isinstance(args, dict):
            return ToolResult(False, "Tool arguments must be an object.")
        if name == "run_command":
            self.audit.record("tool_blocked", tool=name, reason="Isolated runner unavailable")
            return ToolResult(False, "Arbitrary commands are unavailable until an isolated runner exists.")
        if name in self.permissions.restricted:
            self.audit.record('tool_scope_denied',tool=name)
            return ToolResult(False,'Blocked by Security Center tool scope.')
        try:
            if name.startswith("git_"):
                from .security import check_git_scope
                check_git_scope(self.workspace,self.git_agent,self.git_agent.review(args.get("proposal_id"))["repo"] if name=="git_execute" else args.get("repo","."))
            context = {"tool":name, "args":dict(args)}
            policy_action = {'preview_project_context':'retrieve_memory','preview_research_context':'read_web_source'}.get(name,name)
            mandatory = name in {"run_tests", "apply_changes", "restore_snapshot", "save_memory", "delete_memory", "clear_memory", "create_research_brief", "clear_web_sources", "export_sandbox_tests"}
            if name=='create_research_brief':
                read=self.permissions.check('read_web_source',{'tool':name,'source_ids':args.get('source_ids')})
                if not read.approved:return ToolResult(False,'Cached-source reading is blocked by policy.')
                context['warning']='Summarize only selected cached sources. A configured local model may receive bounded page excerpts and the question. This creates a draft only; it cannot run tools or apply file changes.'
            if name=='clear_web_sources':
                context['warning']='Clear the reviewed cached source records for this workspace. Exported briefs, workspace files, audit logs and snapshots remain.'
            if name == "delete_memory":
                row=self.memory.get(args.get('entry_id'))
                if type(args.get('expected_revision')) is not int or row['revision']!=args['expected_revision']:raise ValueError('Entry changed since review; reload before deleting.')
                context['args']={'entry_id':row['id'],'title':row['title'],'kind':row['kind'],'expected_revision':args.get('expected_revision')}
                context['warning']='Delete this local project-memory entry? This does not remove files, audit logs, or snapshots.'
            if name == "clear_memory":
                state=self.memory.list()
                scope=args.get('scope')
                selected=sum(1 for row in state['entries'] if scope=='all' or scope=='saved' and row['kind'] in {'note','decision'} or scope=='history' and row['kind']=='history')
                context['args']={'scope':scope,'selected_entries':selected,'expected_generation':args.get('expected_generation')}
                context['warning']='Clear only the selected memory scope for this workspace. Files, snapshots, test-result files and audit logs remain.'
            if name == "save_memory":
                if args.get('entry_id') is not None:
                    row=self.memory.get(args['entry_id'])
                    if row['kind']=='history' or type(args.get('expected_revision')) is not int or row['revision']!=args['expected_revision']:raise ValueError('Entry changed since review; reload before saving.')
                context['warning']='Save local reference data only. This entry cannot change policies or approve actions.'
            if name == "propose_code_changes":
                context['warning'] = "Selected source files and instructions will be sent to your configured local LM Studio model. Generated edits stage only and need separate diff review and approval."
            if name == 'git_execute':
                proposal=self.git_agent.review(args.get('proposal_id'))
                policy_action=proposal['policy'];mandatory=True
                context={'tool':name,'args':proposal,'warning':'Review this exact Git operation and destination. Repository state is checked again before execution. Remote writes cannot be automatically retried.'}
            execution_args = dict(args)
            if name == "run_tests":
                preview = self.runner.preview(args.get('framework','auto'), args.get('timeout_seconds',120))
                context['args'] = preview
                context['warning'] = preview['warning']
                execution_args['_approved_preview'] = preview
            if name == "export_sandbox_tests":
                context['warning'] = "Copies bounded project inputs outside the workspace and creates a Windows Sandbox configuration. It does not launch anything. Base Python is mapped read-only; only the session Results folder is writable. Windows Sandbox must be enabled separately."
            if name in {"apply_changes", "restore_snapshot"}:
                review = self.files.review()
                expected_kind = "restore" if name == "restore_snapshot" else "change"
                if review['id'] != args.get('proposal_id') or review['kind'] != expected_kind:
                    return ToolResult(False, "Review the current proposal before applying it.")
                policy_action = "write_file" if name == "apply_changes" else "restore_snapshot"
                context['args'] = {"proposal_id":review['id'], "paths":review['paths'], "diff":review['diff'][:12000]}
                context['warning'] = "This changes workspace files. Review the full diff in the Workspace page. Restore can remove files created by the selected change set."
            if name == "write_file":
                context['warning'] = "This stages a proposal only. No workspace file changes until you review and apply it."
            if name in {"write_file", "stage_changes", "preview_file", "snapshot_workspace", "export_sandbox_tests", "git_status", "git_diff", "git_preview", "git_execute"}:
                read_decision = self.permissions.check("read_file", {"tool":name, "args":args, "warning":"This operation reads existing workspace files."})
                self.audit.record("permission_decision", tool=name, capability="read_file", policy=read_decision.policy, approved=read_decision.approved, reason=read_decision.reason)
                if not read_decision.approved:
                    return ToolResult(False, "Reading existing files is blocked by the read-file policy.")
            decision = self.permissions.check(policy_action, context, require_approval=mandatory)
            self.audit.record("permission_decision", tool=name, policy=decision.policy, approved=decision.approved, reason=decision.reason)
            if not decision.approved:
                return ToolResult(False, f"{name}: {decision.reason}")
            if name=='fetch_web':
                preview=validate_url(args.get('url'),self.research_options)
                network=self.permissions.check('network_access',{'tool':name,'args':preview,'warning':'Read-only public HTTPS request; page content will be retained locally as untrusted source data. Redirects, credentials, proxies and private-network destinations are blocked.'},require_approval=True)
                self.audit.record('permission_decision',tool=name,capability='network_access',policy=network.policy,approved=network.approved,reason=network.reason)
                if not network.approved:return ToolResult(False,'Web request blocked by Network Access policy or rejected approval.')
            if name=='git_execute' and proposal['operation'] in {'push','pr','release'}:
                network=self.permissions.check('github_network',{'tool':name,'destination':proposal['destination'],'operation':proposal['operation'],'warning':'Use the locally authenticated GitHub CLI account to contact github.com. This is an external write.'},require_approval=True)
                self.audit.record('permission_decision',tool=name,capability='github_network',approved=network.approved,policy=network.policy)
                if not network.approved:return ToolResult(False,'GitHub network approval was rejected or denied.')
            result = handlers[name](execution_args)
            self.audit.record("tool_result", tool=name, ok=result.ok, message=result.message)
            return result
        except Exception as exc:
            self.audit.record("tool_error", tool=name, error=repr(exc))
            return ToolResult(False, f"{type(exc).__name__}: {exc}")

    def _security_review(self,args):
        from .security import review
        return ToolResult(True,'Static security review; no source values included.',review(self,args.get('paths')))

    def _sandbox_status(self,args):
        from .security import sandbox_status
        return ToolResult(True,'Execution boundary report; feature availability is not verified.',sandbox_status())

    def _git_status(self,args):
        return ToolResult(True,'Repository inspected without external diff helpers or hooks.',self.git_agent.inspect(args.get('repo','.')))

    def _git_diff(self,args):
        return ToolResult(True,'Repository diff; external diff and textconv are disabled.',self.git_agent.diff(args.get('repo','.'),args.get('staged',False)))

    def _git_preview(self,args):
        return ToolResult(True,'Git operation prepared for review; no write was performed.',self.git_agent.preview(args))

    def _git_execute(self,args):
        return ToolResult(True,'Approved Git operation completed.',self.git_agent.execute(args.get('proposal_id')))

    def _preview_web(self,args):
        return ToolResult(True,'URL policy preview passed; no DNS lookup or network request performed.',validate_url(args.get('url'),self.research_options))

    def _fetch_web(self,args):
        if len(self.research.list())>=MAX_SOURCES:raise ValueError('Source cache is full; review and clear it before another fetch.')
        source=self.research.store(fetch_page(args.get('url'),self.research_options))
        self.audit.record('web_source_retained',source_id=source['id'],url=source['url'],sha256=source['sha256'])
        return ToolResult(True,'Read-only source fetched and retained. Treat its contents as untrusted data.',source)

    def _list_web(self,args):
        return ToolResult(True,'Cached sources for this workspace.',self.research.list())

    def _read_web(self,args):
        return ToolResult(True,'Cached source; no network request.',self.research.get(args.get('source_id')))

    def _preview_research_context(self,args):
        data=self.research.preview_context(args.get('source_ids'),args.get('question'))
        data['model_enabled']=self.model is not None
        return ToolResult(True,'Research context preview; no model or network request.',data)

    def _preview_project_context(self,args):
        if not self.memory_options.get('use_context',False):data={'enabled':False,'entries':[],'bytes':0}
        else:data=dict(self._retrieve_memory(args).data,enabled=True)
        return ToolResult(True,'Project-memory context snapshot for this exact query. Actual requests recompute it; inspect the outgoing receipt for what was attempted.',data)

    def _brief_web(self,args):
        result=self.research.brief(args.get('source_ids'),args.get('question'),self.model,args.get('expected_fingerprint'))
        self.audit.record('research_brief_created',source_ids=[source['id'] for source in result['sources']],model_used=self.model is not None)
        return ToolResult(True,'Research draft created. Review citations and limitations before staging/exporting.',result)

    def _clear_web(self,args):
        self.research.clear(args.get('expected_ids'))
        return ToolResult(True,'Reviewed source cache cleared.')

    def _list_memory(self,args):
        data=self.memory.list(args.get('query',''),args.get('kind','all'))
        return ToolResult(True,f"Found {data['count']} project-memory entries.",data)

    def _retrieve_memory(self,args):
        data=self.memory.retrieve(args.get('query',''))
        self.audit.record('project_context_retrieved',entry_ids=[row['id'] for row in data['entries']],bytes=data['bytes'])
        return ToolResult(True,f"Retrieved {len(data['entries'])} saved context entries.",data)

    def _save_memory(self,args):
        data=self.memory.save(args.get('kind'),args.get('title'),args.get('body'),args.get('entry_id'),args.get('expected_revision'))
        return ToolResult(True,'Project memory saved.',data)

    def _delete_memory(self,args):
        self.memory.delete(args.get('entry_id'),args.get('expected_revision'))
        return ToolResult(True,'Selected memory entry deleted.')

    def _clear_memory(self,args):
        data=self.memory.clear(args.get('scope'),args.get('expected_generation'))
        message='Selected project-memory scope cleared.'
        if not data['compacted']:message+=' Database compaction was deferred.'
        return ToolResult(True,message,data)

    def _analyze_code(self, args):
        data = CodingAgent(self, self.model).analyze(args.get('paths'))
        return ToolResult(True, "Static source analysis complete; project code was not executed.", data)

    def _propose_code(self, args):
        data = CodingAgent(self, self.model).propose(args.get('paths'), args.get('instruction'), args.get('expected_hashes'))
        return ToolResult(True, "Coding proposal staged. Review its diff in Workspace before applying.", data)

    def _rename_code(self, args):
        data = CodingAgent(self).rename_python_function(args.get('path'), args.get('old'), args.get('new'))
        return ToolResult(True, "Python rename staged; review external references before applying.", data)

    def _index(self, args):
        result = self.files.index()
        return ToolResult(True, f"Indexed {result['count']} file(s)." + (" Index limited to 1000 files." if result['truncated'] else ""), result)

    def _preview(self, args):
        return ToolResult(True, "UTF-8 file preview.", self.files.preview(args.get('path')))

    def _stage(self, args):
        review = self.files.stage(args.get('changes'), args.get('expected_hashes'))
        return ToolResult(True, "Changes staged. Review and apply from Workspace; files are unchanged.", review)

    def _review(self, args):
        return ToolResult(True, "Pending change review.", self.files.review())

    def _apply(self, args):
        result = self.files.apply(args.get('proposal_id'))
        return ToolResult(True, "Reviewed changes applied; recovery snapshot saved.", result)

    def _discard(self, args):
        self.files.discard()
        return ToolResult(True, "Pending proposal discarded; workspace unchanged.")

    def _snapshot(self, args):
        result = self.files.snapshot()
        return ToolResult(True, f"Snapshot saved: {result['files']} UTF-8 file(s); {len(result['skipped'])} unsupported file(s) skipped.", result)

    def _snapshots(self, args):
        return ToolResult(True, "Workspace snapshots.", self.files.snapshots())

    def _prepare_restore(self, args):
        return ToolResult(True, "Restore staged for review; no workspace changes.", self.files.prepare_restore(args.get('snapshot_id')))

    def _list_files(self, args: dict) -> ToolResult:
        files = self.workspace.list_files()
        return ToolResult(True, f"Found {len(files)} file(s).", files)

    def _read_file(self, args: dict) -> ToolResult:
        path = str(args.get("path", "")).strip()
        if not path:
            return ToolResult(False, "Missing path.")
        text = self.workspace.read_text(path)
        return ToolResult(True, f"Read {path}.", text)

    def _write_file(self, args: dict) -> ToolResult:
        path = str(args.get("path", "")).strip()
        content = str(args.get("content", ""))
        if not path:
            return ToolResult(False, "Missing path.")
        return self._stage({"changes":{path:content}})

    def _detect_tests(self, args):
        return ToolResult(True, "Detected supported Python test frameworks.", self.runner.detect())

    def _preview_tests(self, args):
        return ToolResult(True, "Test command preview; no code executed.", self.runner.preview(args.get('framework','auto'),args.get('timeout_seconds',120)))

    def _export_sandbox(self, args):
        data = export_session(self.files,args.get('timeout_seconds',120))
        return ToolResult(True, "Windows Sandbox session exported; not launched or verified.", data)

    def _run_tests(self, args: dict) -> ToolResult:
        preview = args.get('_approved_preview')
        if preview is None:
            return ToolResult(False, "An approved command preview is required.")
        storage = self.files.storage / 'test-runs'
        data = self.runner.run(preview)
        try:
            path = storage / (uuid.uuid4().hex + '.json')
            atomic_bytes(path,json.dumps(data,indent=2).encode('utf-8'))
            data['saved_result'] = str(path)
        except OSError as exc:
            data['history_error'] = str(exc)
        self.audit.record('test_run_completed',framework=data['framework'],state=data['state'],exit_code=data['exit_code'],elapsed_seconds=data['elapsed_seconds'],truncated=data['truncated'])
        ok = data['summary']['outcome'] == 'passed' and 'Ran 0 tests' not in data['output'] and 'no tests ran' not in data['output']
        return ToolResult(ok, f"Tests {data['state']}; exit code {data['exit_code']}. {data['triage']}", data)

    def _run_command(self, args: dict) -> ToolResult:
        return ToolResult(False, "Arbitrary command runner unavailable.")
