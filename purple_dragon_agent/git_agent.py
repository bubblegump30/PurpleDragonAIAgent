"""Fixed Git commands and reviewed GitHub writes; no arbitrary shell surface."""
from pathlib import Path
from urllib.parse import urlsplit,quote
import hashlib,json,os,re,shutil,signal,subprocess,sys,tempfile,threading,time,uuid

POLICIES={'branch':'git_branch','commit':'git_commit','push':'git_push','pr':'github_create_pr','release':'publish_release'}


class GitAgent:
    def __init__(self,workspace):
        self.workspace=workspace;self.pending=None;self._process=None;self._mutex=threading.Lock();self._closing=False
        self.git=shutil.which('git.exe' if sys.platform=='win32' else 'git')
        self.gh=shutil.which('gh.exe' if sys.platform=='win32' else 'gh')

    def _env(self):
        env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','SSH_')) and k not in {'GH_DEBUG','GH_HTTP_UNIX_SOCKET'}}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0',GH_PROMPT_DISABLED='1',GH_HOST='github.com',LC_ALL='C')
        return env

    def _command(self,argv,cwd,env=None,input_data=None,timeout=20,accepted=(0,),secret=None):
        if self._closing:raise RuntimeError('Git operation cancelled because the app is closing.')
        with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err,tempfile.TemporaryFile() as stdin:
            if input_data is not None:stdin.write(input_data);stdin.seek(0)
            options={'cwd':cwd,'env':env or self._env(),'stdin':stdin,'stdout':out,'stderr':err,'shell':False}
            if sys.platform=='win32':options['creationflags']=subprocess.CREATE_NO_WINDOW
            else:options['start_new_session']=True
            job=None
            process=subprocess.Popen(argv,**options)
            with self._mutex:self._process=process
            try:
                if sys.platform=='win32':
                    from .winjob import WindowsJob
                    try:job=WindowsJob(process)
                    except OSError:
                        if process.poll() is None:raise
                deadline=time.monotonic()+timeout
                while process.poll() is None:
                    if self._closing or time.monotonic()>deadline or os.fstat(out.fileno()).st_size+os.fstat(err.fileno()).st_size>1_000_000:
                        self._kill(process);raise RuntimeError('Git command cancelled, timed out, or exceeded the output limit. Inspect repository state before retrying.')
                    time.sleep(.02)
                out.seek(0);err.seek(0)
                text=out.read(1_000_001).decode('utf-8','replace');error=err.read(1_000_001).decode('utf-8','replace')
                if len(text.encode())+len(error.encode())>1_000_000:raise ValueError('Git output is too large to review safely.')
                if secret:text=text.replace(secret,'[redacted]');error=error.replace(secret,'[redacted]')
                if process.returncode not in accepted:raise RuntimeError((error or text or f'Command failed ({process.returncode})')[:8000])
                return text.strip()
            finally:
                if process.poll() is None:self._kill(process)
                process.wait()
                if job:job.close()
                with self._mutex:
                    if self._process is process:self._process=None

    def _kill(self,process):
        try:
            if sys.platform=='win32':process.kill()
            else:os.killpg(process.pid,signal.SIGKILL)
        except (OSError,ProcessLookupError):pass

    def cancel(self):
        self._closing=True
        with self._mutex:
            if self._process:self._kill(self._process)

    def _git(self,repo,args,accepted=(0,),env=None,timeout=20,secret=None):
        if not self.git:raise RuntimeError('Git is not installed or is not on PATH.')
        with tempfile.TemporaryDirectory(prefix='pd-git-hooks-') as hooks:
            flags=['--no-pager','-c','core.fsmonitor=false','-c',f'core.hooksPath={hooks}','-c','core.pager=cat','-c','commit.gpgSign=false','-c','core.attributesFile='+os.devnull,'-c','credential.helper=','-c','http.proxy=','-c','http.sslVerify=true','-c','http.followRedirects=false','-c','http.extraHeader=','-c','http.cookieFile=','-c','http.saveCookies=false']
            return self._command([self.git,*flags,*args],repo,env,timeout=timeout,accepted=accepted,secret=secret)

    def _repo(self,relative):
        if not isinstance(relative,str):raise ValueError('Repository path must be a workspace-relative string.')
        repo=self.workspace.resolve(relative or '.')
        metadata=repo/'.git'
        if not metadata.is_dir() or metadata.is_symlink():raise ValueError('Select a repository root with a regular .git directory inside the workspace. Linked worktrees are not supported.')
        for i,item in enumerate(metadata.rglob('*')):
            if i>10000:raise ValueError('Repository metadata exceeds the inspection limit.')
            if item.is_symlink():
                try:item.resolve().relative_to(repo)
                except ValueError:raise ValueError('Repository metadata links outside the selected workspace.')
        if (metadata/'objects/info/alternates').exists():raise ValueError('Repositories with external alternate object stores are not supported.')
        for name in ('config','config.worktree'):
            config=metadata/name
            if config.exists():
                if config.stat().st_size>262144:raise ValueError('Repository configuration is too large.')
                text=config.read_text(errors='replace')
                if re.search(r'^\s*\[\s*(include|includeif|url|http|credential)\b',text,re.I|re.M):
                    raise ValueError('Repository configuration contains includes, URL rewrites, or custom HTTP/credential rules. Review those externally before using this Git agent.')
        top=self._git(repo,['rev-parse','--show-toplevel'])
        if Path(top).resolve()!=repo:raise ValueError('Git resolves this repository outside the selected root.')
        return repo

    def _ref(self,repo,value):
        if not isinstance(value,str) or not value or len(value)>200 or value.startswith('-'):raise ValueError('Invalid branch or tag name.')
        checked=self._git(repo,['check-ref-format','--branch',value])
        if checked!=value:raise ValueError('Use a literal branch or tag name; Git branch shorthand is not supported.')
        return value

    def _capture(self,repo):
        head=self._git(repo,['rev-parse','--verify','HEAD'],accepted=(0,128))
        if not re.fullmatch(r'[0-9a-f]{40,64}',head):head=None
        branch=self._git(repo,['symbolic-ref','--quiet','--short','HEAD'],accepted=(0,1)) or None
        raw=self._git(repo,['diff','--cached','--raw','--abbrev=64','--full-index','--no-ext-diff','--no-textconv','--ignore-submodules=none','--submodule=short'])
        return {'head':head,'branch':branch,'index_digest':hashlib.sha256(raw.encode()).hexdigest()}

    def inspect(self,relative='.'):
        repo=self._repo(relative)
        return dict(self._capture(repo),repo=str(repo),status=self._git(repo,['status','--short','--untracked-files=normal','--ignore-submodules=all']),branches=self._git(repo,['branch','--list']),log=self._git(repo,['log','-12','--format=%h %s'],accepted=(0,128)),github_cli_available=bool(self.gh))

    def diff(self,relative='.',staged=False):
        if type(staged) is not bool:raise ValueError('Staged must be a boolean.')
        repo=self._repo(relative)
        return self._git(repo,['diff',*(['--cached'] if staged else []),'--no-ext-diff','--no-textconv','--ignore-submodules=none' if staged else '--ignore-submodules=all','--submodule=short','--no-color'])

    def _destination(self,repo):
        raw=self._git(repo,['config','--local','--get','remote.origin.url'],accepted=(0,1))
        if raw.startswith('git@github.com:'):path=raw[len('git@github.com:'):]
        else:
            parsed=urlsplit(raw)
            if parsed.scheme!='https' or parsed.hostname!='github.com' or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:raise ValueError('origin must be a credential-free github.com HTTPS or git@github.com repository URL.')
            path=parsed.path.lstrip('/')
        if path.endswith('.git'):path=path[:-4]
        if not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}',path):raise ValueError('Invalid GitHub repository destination.')
        return path

    def preview(self,args):
        operation=args.get('operation');repo=self._repo(args.get('repo','.'));state=self._capture(repo)
        if operation not in POLICIES:raise ValueError('Choose branch, commit, push, pr or release.')
        values={};destination=None
        if operation=='branch':
            values['name']=self._ref(repo,args.get('name'))
            if not state['head']:raise ValueError('Create the initial commit externally before creating a branch.')
            if self._git(repo,['branch','--list',values['name']]):raise ValueError('That branch already exists.')
        elif operation=='commit':
            message=args.get('message')
            if not isinstance(message,str) or not message.strip() or len(message)>4000 or '\x00' in message:raise ValueError('Enter a commit message of 1–4000 characters.')
            values['message']=message
            identity={key:self._git(repo,['config','--local','--get',f'user.{key}'],accepted=(0,1)) for key in ('name','email')}
            if not identity['name'] or not identity['email']:
                raise ValueError('Set repository-local Git user.name and user.email in your Git client before committing. Global identity files are not read by this agent.')
            values['identity']=identity
            if not self._git(repo,['diff','--cached','--name-only']):raise ValueError('No staged changes. Stage the intended files using your Git client first.')
        else:
            if not state['head'] or not state['branch']:raise ValueError('A committed, attached branch is required.')
            destination=self._destination(repo)
            if operation=='push' and self._git(repo,['grep','-l','-E',r'filter[[:space:]]*=[[:space:]]*lfs','HEAD','--','*.gitattributes'],accepted=(0,1,128)):
                raise ValueError('Git LFS upload hooks are not supported by this agent. Push this repository with your Git client.')
            if operation=='pr':
                values.update(base=self._ref(repo,args.get('base','main')),title=self._text(args,'title',200),body=self._text(args,'body',20000,empty=True))
                base_sha=self._git(repo,['rev-parse','--verify','refs/heads/'+values['base']],accepted=(0,128))
                if not re.fullmatch(r'[0-9a-f]{40,64}',base_sha):
                    base_sha=self._git(repo,['rev-parse','--verify','refs/remotes/origin/'+values['base']],accepted=(0,128))
                if not re.fullmatch(r'[0-9a-f]{40,64}',base_sha):raise ValueError('Fetch the PR base branch externally before preparing a review.')
                values['base_sha']=base_sha
                values['committed_diff']=self._git(repo,['diff','--no-ext-diff','--no-textconv','--no-color',base_sha+'...'+state['head']])
            elif operation=='release':
                draft=args.get('draft',True)
                if type(draft) is not bool:raise ValueError('Draft must be a boolean.')
                values.update(tag=self._ref(repo,args.get('tag')),title=self._text(args,'title',200),body=self._text(args,'body',20000,empty=True),draft=draft)
        proposal=dict(id=uuid.uuid4().hex,operation=operation,repo=args.get('repo','.'),state=state,args=values,destination=destination,policy=POLICIES[operation],staged_diff=self.diff(args.get('repo','.'),True),note='Commit uses the staged index only. Branch creation does not switch branches. No force push or hook execution. Remote operations require a separate GitHub-network approval.')
        self.pending=json.loads(json.dumps(proposal));return proposal

    def _text(self,args,key,limit,empty=False):
        value=args.get(key,'')
        if not isinstance(value,str) or len(value)>limit or '\x00' in value or not empty and not value.strip():raise ValueError(f'Invalid {key}.')
        return value

    def review(self,identifier):
        if not self.pending or self.pending['id']!=identifier:raise ValueError('Preview the current operation before executing it.')
        return json.loads(json.dumps(self.pending))

    def _github(self,repo,path,payload=None):
        if not self.gh:raise RuntimeError('GitHub CLI (gh) is required. Authenticate it externally with your GitHub account first.')
        args=[self.gh,'api','--hostname','github.com','--method','POST' if payload is not None else 'GET',path]
        data=None
        if payload is not None:args.extend(['--input','-']);data=json.dumps(payload).encode()
        result=self._command(args,repo,input_data=data,timeout=90)
        return json.loads(result)

    def execute(self,identifier):
        proposal=self.review(identifier);repo=self._repo(proposal['repo']);state=self._capture(repo)
        if state!=proposal['state']:raise ValueError('Repository HEAD, branch or staged index changed after preview. Preview and approve again.')
        operation=proposal['operation'];args=proposal['args']
        if operation in ('push','pr','release') and self._destination(repo)!=proposal['destination']:raise ValueError('GitHub destination changed. Preview and approve again.')
        # Consume before invoking a write. Failure must never automatically retry an ambiguous remote write.
        self.pending=None
        if operation=='branch':return {'output':self._git(repo,['branch','--no-track',args['name'],state['head']]),'branch':args['name'],'switched':False}
        if operation=='commit':return {'output':self._git(repo,['-c','user.name='+args['identity']['name'],'-c','user.email='+args['identity']['email'],'commit','--no-verify','--no-gpg-sign','-m',args['message']]),'head':self._capture(repo)['head']}
        destination=proposal['destination']
        if operation=='push':return self._push(repo,destination,state)
        if operation=='pr':
            remote=self._github(repo,f'repos/{destination}/git/ref/heads/{quote(state["branch"],safe="")}')
            if remote['object']['sha']!=state['head']:raise ValueError('Push the reviewed HEAD before creating this PR; the remote branch differs.')
            base=self._github(repo,f'repos/{destination}/git/ref/heads/{quote(args["base"],safe="")}')
            if base['object']['sha']!=args['base_sha']:raise ValueError('Remote base branch changed since the local PR preview. Fetch externally and preview again.')
            result=self._github(repo,f'repos/{destination}/pulls',{'head':state['branch'],'base':args['base'],'title':args['title'],'body':args['body']})
            return {'number':result['number'],'url':result['html_url']}
        commit=self._github(repo,f'repos/{destination}/commits/{state["head"]}')
        if commit['sha']!=state['head']:raise ValueError('Reviewed commit is not available on GitHub.')
        # A pre-existing tag must resolve to the reviewed commit; never silently publish another target.
        try:tag=self._github(repo,f'repos/{destination}/git/ref/tags/{quote(args["tag"],safe="")}')
        except RuntimeError as exc:
            if '404' not in str(exc):raise
            tag=None
        if tag:
            obj=tag['object']
            for _ in range(4):
                if obj['type']=='commit':break
                if obj['type']!='tag':raise ValueError('Release tag has an unsupported target.')
                obj=self._github(repo,f'repos/{destination}/git/tags/{obj["sha"]}')['object']
            if obj['type']!='commit' or obj['sha']!=state['head']:raise ValueError('Existing release tag does not point to the reviewed commit.')
        result=self._github(repo,f'repos/{destination}/releases',{'tag_name':args['tag'],'target_commitish':state['head'],'name':args['title'],'body':args['body'],'draft':args['draft']})
        return {'url':result['html_url'],'draft':result['draft'],'tag':result['tag_name']}

    def _push(self,repo,destination,state):
        if not self.gh:raise RuntimeError('GitHub CLI authentication is required for a guarded HTTPS push.')
        token=self._command([self.gh,'auth','token','--hostname','github.com'],repo,timeout=15).strip()
        if not token or '\n' in token:raise RuntimeError('No usable GitHub CLI authentication token.')
        with tempfile.TemporaryDirectory(prefix='pd-git-auth-') as temp:
            helper=Path(temp)/'askpass.py';helper.write_text("import os,sys\nprint('x-access-token' if 'username' in sys.argv[1].lower() else os.environ['PD_GIT_AUTH'])\n")
            if sys.platform=='win32':
                launcher=Path(temp)/'askpass.bat';launcher.write_text(f'@"{sys.executable}" "{helper}" %*\n');askpass=str(launcher)
            else:
                helper.write_text(f'#!{sys.executable}\n'+helper.read_text());helper.chmod(0o700);askpass=str(helper)
            env=self._env();env.update(GIT_ASKPASS=askpass,PD_GIT_AUTH=token)
            output=self._git(repo,['push','--porcelain','--no-verify','--no-follow-tags',f'https://github.com/{destination}.git',f'{state["head"]}:refs/heads/{state["branch"]}'],env=env,timeout=120,secret=token)
            return {'output':output,'destination':destination,'branch':state['branch'],'commit':state['head']}
