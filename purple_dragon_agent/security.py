"""Restrictive scope controls and bounded, value-free static security reports."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys

PROFILES={
    'standard':set(),
    'read_only':{'export_sandbox_tests','write_file','stage_changes','propose_code_changes','rename_python_function','apply_changes','restore_snapshot','discard_changes','snapshot_workspace','save_memory','delete_memory','clear_memory','create_research_brief','clear_web_sources','run_tests','network_access','fetch_web','git_execute','git_branch','git_commit','git_push','github_create_pr','publish_release','github_network'},
    'sandbox_only':{'write_file','stage_changes','propose_code_changes','rename_python_function','apply_changes','restore_snapshot','discard_changes','snapshot_workspace','save_memory','delete_memory','clear_memory','create_research_brief','clear_web_sources','run_tests','network_access','fetch_web','git_execute','git_branch','git_commit','git_push','github_create_pr','publish_release','github_network'},
}

SCOPE_ACTIONS={'apply_changes','git_execute'}

def normalize_security(value, known_tools):
    known_tools=set(known_tools) | SCOPE_ACTIONS
    if not isinstance(value,dict) or set(value)-{'protect_secret_files','denied_paths','denied_tools'}:
        raise ValueError('Invalid security settings.')
    protect=value.get('protect_secret_files',True)
    if type(protect) is not bool:raise ValueError('File protection must be a boolean.')
    paths=value.get('denied_paths',[]);tools=value.get('denied_tools',[])
    if not isinstance(paths,list) or len(paths)>64:raise ValueError('Use at most 64 denied paths.')
    clean=[]
    for path in paths:
        if not isinstance(path,str) or not path or len(path)>512 or '\\' in path or PureWindowsPath(path).drive or PurePosixPath(path).is_absolute() or any(x in path.split('/') for x in ('','..','.')):
            raise ValueError('Denied paths must be exact relative files or folder prefixes, without wildcards or traversal.')
        if any(x in path for x in ('*','?','[','\x00',':')):raise ValueError('Invalid denied path.')
        clean.append(path)
    if not isinstance(tools,list) or len(tools)>128 or any(not isinstance(x,str) or x not in known_tools for x in tools):
        raise ValueError('Denied tools must be known permission actions.')
    return {'protect_secret_files':protect,'denied_paths':list(dict.fromkeys(clean)),'denied_tools':list(dict.fromkeys(tools))}

def protected_path(relative,options):
    name=str(relative).replace('\\','/').casefold()
    parts=name.split('/')
    if any(name==p.casefold() or name.startswith(p.casefold()+'/') for p in options.get('denied_paths',[])):return True
    if 'private-secrets' in parts or name.endswith('.secret'):return True
    if not options.get('protect_secret_files',True):return False
    return any(p=='.env' or p.startswith('.env.') or p in {'.ssh','.aws','.azure','id_rsa','id_ed25519','credentials'} or p.endswith(('.pem','.key','.pfx','.p12')) for p in parts)

PATTERNS=[('dynamic_code',re.compile(r'\b(?:eval|exec)\s*\(')),('shell_execution',re.compile(r'shell\s*=\s*True')),('unsafe_deserialization',re.compile(r'\b(?:pickle\.loads?|yaml\.load)\s*\(')),('tls_verification_disabled',re.compile(r'verify\s*=\s*False')),('possible_embedded_secret',re.compile(r'(?:api[_-]?key|password|secret|token)\s*[:=]\s*[\"\'][^\"\']{8,}',re.I)),('private_key_material',re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'))]

def review(tools,paths):
    if not isinstance(paths,list) or not paths or len(paths)>8 or any(not isinstance(p,str) or len(p)>512 for p in paths):raise ValueError('Select one to eight source files.')
    findings=[];files=[];total=0
    for path in list(dict.fromkeys(paths)):
        result=tools.execute('preview_file',{'path':path})
        if not result.ok:raise PermissionError(result.message)
        text=result.data
        total+=len(text.encode('utf-8'))
        if total>80000:raise ValueError('Security review exceeds the 80 KB context limit.')
        files.append(path)
        for line_number,line in enumerate(text.splitlines(),1):
            for category,pattern in PATTERNS:
                if pattern.search(line):
                    findings.append({'path':path,'line':line_number,'category':category,'severity':'review_required'})
                    if len(findings)>=100:return {'files':files,'findings':findings,'truncated':True,'limitations':'Static heuristics only. Values and source snippets are omitted. Not a certification.'}
    return {'files':files,'findings':findings,'truncated':False,'limitations':'Static heuristics only; false positives and missed issues are possible. No code executed; not a certification.'}

def sandbox_status():
    return {'windows':sys.platform=='win32','executable_present':sys.platform=='win32' and shutil.which('WindowsSandbox.exe') is not None,'feature_enabled':'not verified','host_tests':'Fixed commands on the host; approvals do not provide isolation.','sandbox_tests':'Export only; manually open the .wsb file on a supported configured Windows PC.','networking':'disabled in exported configuration','clipboard':'disabled in exported configuration','host_writable':'Only the exported session Results folder; output is untrusted.'}

def check_git_scope(workspace, git_agent=None, relative='.'):
    """Git subprocesses can bypass Workspace.resolve: refuse protected repositories."""
    import os
    options=workspace.security_options
    if options is None:return
    count=0
    for directory,dirs,names in os.walk(workspace.root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in {'.git','.venv','node_modules','__pycache__'}]
        for name in names:
            count+=1
            if count>10000:raise PermissionError('Git scope preflight exceeds 10,000 files; choose a smaller workspace.')
            file_relative=(Path(directory)/name).relative_to(workspace.root).as_posix()
            if protected_path(file_relative,options):raise PermissionError('Git unavailable while protected files exist in this workspace. Use an external Git client or explicitly revise protected path settings.')

    if git_agent is not None:
        repo=git_agent._repo(relative)
        if protected_path((repo/'.git').relative_to(workspace.root).as_posix(),options):
            raise PermissionError('Git metadata is protected by path scope.')
        names=git_agent._git(repo,['ls-files','--cached','-z'])+'\x00'+git_agent._git(repo,['log','--all','--format=','--name-only','-z'],accepted=(0,128))
        for name in names.split('\x00'):
            name=name.strip('\n')
            if not name:continue
            path=(repo/name).relative_to(workspace.root).as_posix()
            if protected_path(path,options):raise PermissionError('Git index/history contains protected paths; use an external Git client or explicitly revise protection settings.')
