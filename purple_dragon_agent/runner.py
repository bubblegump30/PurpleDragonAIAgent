"""Approval-gated fixed test commands; host execution is explicitly NOT isolation."""
import importlib.util
import os
import json
import re
from copy import deepcopy
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

OUTPUT_LIMIT = 100_000


def console_python():
    if getattr(sys, "frozen", False):
        raise RuntimeError("Host tests need the source installation with a normal Python interpreter. The packaged app executable cannot run Python test commands.")
    path = Path(sys.executable).resolve()
    if path.name.lower() == 'pythonw.exe':
        path = path.with_name('python.exe')
    if not path.is_file():
        raise RuntimeError('A console Python interpreter was not found.')
    return str(path)


def clean_environment():
    allowed = ('SystemRoot','WINDIR','COMSPEC','TEMP','TMP','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','LANG','LC_ALL','PATH')
    env = {key:os.environ[key] for key in allowed if key in os.environ}
    env.update(PYTHONUNBUFFERED='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    return env


class TestRunner:
    __test__ = False  # Avoid accidental pytest collection of the application class.
    def __init__(self, workspace):
        self.workspace = workspace
        self._run_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancel = threading.Event()
        self._output = bytearray()
        self._state = 'idle'
        self._process = None
        self._job = None
        self._argv = []
        self._total = 0
        self._started = None
        self._finished = None
        self._exit_code = None
        self._summary = None

    def detect(self):
        root = self.workspace.root
        pytest_config = any((root/name).is_file() for name in ('pytest.ini','conftest.py'))
        if (root/'pyproject.toml').is_file():
            pytest_config |= '[tool.pytest' in self.workspace.read_text('pyproject.toml', max_bytes=100_000)
        available = importlib.util.find_spec('pytest') is not None
        return {'recommended':'pytest' if pytest_config and available else 'unittest',
                'pytest_available':available,'pytest_config_detected':pytest_config,
                'test_directory':'tests' if (root/'tests').is_dir() else '.',
                'isolation':'none — trusted host tests only',
                'execution_available':not getattr(sys,'frozen',False),
                'supported':['unittest'] + (['pytest'] if available else [])}

    def preview(self, framework='auto', timeout_seconds=120):
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
            raise ValueError('Timeout must be an integer between 1 and 600 seconds.')
        if framework not in {'auto','unittest','pytest'}:
            raise ValueError('Choose auto, unittest, or pytest. Arbitrary commands are unavailable.')
        detected = self.detect()
        if framework == 'auto': framework = detected['recommended']
        if framework == 'pytest' and not detected['pytest_available']:
            raise ValueError('pytest is not installed in this interpreter. Use unittest or install it yourself.')
        argv = [console_python(), '-u', '-m', framework]
        if framework == 'unittest': argv += ['discover','-s',detected['test_directory'],'-v']
        else: argv += ['-v','--tb=short','-p','no:cacheprovider']
        return {'argv':argv,'command':subprocess.list2cmdline(argv),'cwd':str(self.workspace.root),
                'framework':framework,'timeout_seconds':timeout_seconds,
                'warning':'HOST execution: project tests run with your user-account access and can modify files or use the network. This is not an OS sandbox. Only approve trusted projects.'}

    def snapshot(self):
        with self._state_lock:
            return {'state':self._state,'output':bytes(self._output).decode('utf-8',errors='replace'),
                    'summary':deepcopy(self._summary),'truncated':self._total > OUTPUT_LIMIT,'bytes_seen':self._total,
                    'argv':list(self._argv),'exit_code':self._exit_code,
                    'execution_available':not getattr(sys,'frozen',False),
                    'elapsed_seconds':round((self._finished or time.monotonic())-self._started,2) if self._started else 0}

    def cancel(self):
        with self._state_lock:
            active = self._state in {'starting','running'}
        if active: self._cancel.set()
        return active

    def abort(self):
        self._cancel.set()
        with self._state_lock:
            process = self._process
        if process is not None:
            self._stop_tree(process)

    def _stop_tree(self, process):
        if sys.platform == 'win32' and self._job is not None:
            self._job.close()
        elif sys.platform == 'win32':
            # Fixed system utility path; no shell or user-supplied command text.
            taskkill = Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/taskkill.exe'
            try:
                subprocess.run([str(taskkill),'/PID',str(process.pid),'/T','/F'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=False)
            except (OSError,subprocess.TimeoutExpired):
                pass
        else:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        if process.poll() is None: process.kill()

    def run(self, preview):
        # Rebuild from fixed framework/timeout rather than trusting supplied argv/cwd.
        checked = self.preview(preview['framework'],preview['timeout_seconds'])
        if checked != preview:
            raise ValueError('Test command changed since approval; review it again.')
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError('A test process is already running.')
        process = None
        reader = None
        try:
            self._cancel.clear()
            with self._state_lock:
                self._output = bytearray();self._total=0;self._state='starting'
                self._argv=list(checked['argv']);self._summary=None;self._exit_code=None;self._started=time.monotonic();self._finished=None
            kwargs = {'cwd':self.workspace.root,'stdin':subprocess.PIPE,'stdout':subprocess.PIPE,
                      'stderr':subprocess.STDOUT,'env':clean_environment(),'shell':False}
            if sys.platform == 'win32': kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            else: kwargs['start_new_session'] = True
            bootstrap = Path(__file__).with_name('runner_bootstrap.py')
            process = subprocess.Popen([checked['argv'][0],'-u',str(bootstrap)],**kwargs)
            if sys.platform == 'win32':
                from .winjob import WindowsJob
                self._job = WindowsJob(process)
            # The bootstrap cannot run project tests before lifetime controls are ready.
            request = {'module':checked['framework'],'args':checked['argv'][4:]}
            process.stdin.write((json.dumps(request)+'\n').encode('utf-8'))
            process.stdin.close()
            with self._state_lock: self._process=process;self._state='running'
            def read_output():
                try:
                    while True:
                        chunk = process.stdout.read1(4096)
                        if not chunk: break
                        with self._state_lock:
                            self._total += len(chunk)
                            self._output.extend(chunk)
                            if len(self._output) > OUTPUT_LIMIT:
                                del self._output[:-OUTPUT_LIMIT]
                except (OSError,ValueError):
                    pass
                finally:
                    process.stdout.close()
            reader = threading.Thread(target=read_output,daemon=True);reader.start()
            outcome = 'finished'
            while process.poll() is None:
                if self._cancel.wait(.05):
                    outcome='cancelled';self._stop_tree(process);break
                if time.monotonic()-self._started >= checked['timeout_seconds']:
                    outcome='timed_out';self._stop_tree(process);break
            process.wait(timeout=5)
            if self._job is not None:
                self._job.close()
            # Kill remaining children in the process group (POSIX) on parent exit.
            if sys.platform != 'win32':
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
            reader.join(timeout=2)
            if reader.is_alive():
                outcome='output_incomplete' if outcome == 'finished' else outcome
            with self._state_lock:
                self._exit_code=process.returncode;self._state=outcome;self._finished=time.monotonic()
            result = self.snapshot()
            result.update(framework=checked['framework'],command=checked['command'],cwd=checked['cwd'])
            result['triage']=triage(result)
            result['summary']=summarize_tests(result)
            with self._state_lock:self._summary=deepcopy(result['summary'])
            return result
        except Exception:
            if process is not None and process.poll() is None: self._stop_tree(process)
            with self._state_lock: self._state='failed';self._finished=time.monotonic()
            raise
        finally:
            if process is not None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.stdout and (reader is None or not reader.is_alive()):
                    process.stdout.close()
            if self._job is not None:
                self._job.close();self._job=None
            with self._state_lock: self._process=None
            self._run_lock.release()


def triage(result):
    output=result['output']
    if result['state']=='cancelled': return 'Cancelled by user; no automatic retry.'
    if result['state']=='timed_out': return 'Timeout: inspect hanging tests or slow setup before retrying.'
    if result['state']=='output_incomplete': return 'A child process kept output open; completion could not be verified.'
    if 'ModuleNotFoundError' in output: return 'Missing dependency: inspect the named module. Packages are not installed automatically.'
    if 'Ran 0 tests' in output or 'no tests ran' in output: return 'No tests discovered; check the framework and test directory.'
    if 'SyntaxError' in output: return 'Syntax failure: review the referenced source in Coding.'
    if result.get('truncated'): return 'Output was truncated; inspect available output and rerun a smaller test suite if needed. Counts and failures may be incomplete.'
    if result['exit_code'] == 0: return 'Command completed successfully. Review test counts; an exit code alone does not prove coverage.'
    return 'Test failure: inspect the traceback/assertions before proposing a repair in Coding.'


def summarize_tests(result):
    """Parse bounded output heuristically. This never authorizes edits or execution."""
    output=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',str(result.get('output',''))[-OUTPUT_LIMIT:])
    def count(value):return int(value) if len(value)<=9 else None
    counts={'run':None,'collected':None,'passed':None,'failed':None,'errors':None,'skipped':None,'expected_failures':None,'unexpected_successes':None}
    ran=re.findall(r'^Ran (\d+) tests? in ',output,re.M)
    if ran:counts['run']=count(ran[-1])
    collected=re.findall(r'collected (\d+) items?',output)
    if collected:counts['collected']=count(collected[-1])
    for line in output.splitlines():
        if re.match(r'^(FAILED|OK)(?:\s*\(|$)',line):
            for name,target in [('failures','failed'),('errors','errors'),('skipped','skipped'),('expected failures','expected_failures'),('unexpected successes','unexpected_successes')]:
                match=re.search(re.escape(name)+r'=(\d+)',line)
                if match:counts[target]=count(match.group(1))
        if re.search(r'\bin \d+(?:\.\d+)?s\b',line):
            for name,target in [('passed','passed'),('failed','failed'),('errors?','errors'),('skipped','skipped')]:
                match=re.search(r'(\d+) '+name+r'\b',line)
                if match:counts[target]=count(match.group(1))
    failures=[]
    for line in output.splitlines():
        if re.match(r'^(FAIL:|ERROR:|UNEXPECTED SUCCESS:|FAILED (?!\()|ERROR )',line):
            value=line[:500]
            if value not in failures:failures.append(value)
    state=result.get('state');exit_code=result.get('exit_code')
    no_tests=counts['run']==0 or counts['collected']==0 or 'no tests ran' in output.lower()
    if state in {'cancelled','timed_out'}:outcome=state
    elif state!='finished' or result.get('truncated'):outcome='incomplete'
    elif no_tests and exit_code in (0,5):outcome='no_tests'
    elif exit_code!=0:outcome='failed'
    elif counts['run'] is not None or counts['passed'] is not None:outcome='passed'
    else:outcome='unverified'
    return {'outcome':outcome,'counts':counts,'failures':failures[:20],'failure_list_truncated':len(failures)>20,
            'output_truncated':bool(result.get('truncated')),
            'note':'Counts and failure names are parsed from process output and can be incomplete or misleading. Exit status, raw output and manual review remain necessary. Tests run files on disk, not unapplied staged proposals.'}
