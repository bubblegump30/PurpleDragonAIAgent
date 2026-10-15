"""Windows Sandbox export for fixed unittest runs; no host command execution."""
from pathlib import Path
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

CONFIG_DOC = 'https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file'


def configuration(project, python, scripts, results):
    root=ET.Element('Configuration')
    for tag in ('Networking','ClipboardRedirection','AudioInput','VideoInput','PrinterRedirection','vGPU'):
        ET.SubElement(root,tag).text='Disable'
    ET.SubElement(root,'ProtectedClient').text='Enable'
    maps=ET.SubElement(root,'MappedFolders')
    for host,guest,readonly in ((project,r'C:\PD\Input',True),(python,r'C:\PD\Python',True),(scripts,r'C:\PD\Scripts',True),(results,r'C:\PD\Results',False)):
        entry=ET.SubElement(maps,'MappedFolder')
        ET.SubElement(entry,'HostFolder').text=str(Path(host).resolve())
        ET.SubElement(entry,'SandboxFolder').text=guest
        ET.SubElement(entry,'ReadOnly').text='true' if readonly else 'false'
    command=ET.SubElement(root,'LogonCommand')
    ET.SubElement(command,'Command').text=r'powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\PD\Scripts\Run-Tests.ps1'
    return ET.tostring(root,encoding='unicode')


SCRIPT = r'''$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path C:\PD\Work | Out-Null
Copy-Item -Path C:\PD\Input\* -Destination C:\PD\Work -Recurse -Force
Set-Location C:\PD\Work
& C:\PD\Python\python.exe C:\PD\Scripts\Sandbox-Run.py
Read-Host 'Close Windows Sandbox when finished; results are in the exported Results folder'
'''

HELPER = r'''import json
from pathlib import Path
from purple_dragon_agent.runner import TestRunner
class Workspace:
    root = Path(r'C:\PD\Work')
    def read_text(self, name, max_bytes):
        with (self.root/name).open('rb') as stream:
            data = stream.read(max_bytes+1)
        if len(data)>max_bytes: raise ValueError('Config file too large')
        return data.decode('utf-8',errors='replace')
results = Path(r'C:\PD\Results')
try:
    runner = TestRunner(Workspace())
    report = runner.run(runner.preview('unittest',TIMEOUT_SECONDS))
    output = report.pop('output')
    (results/'output.log').write_text(output,encoding='utf-8')
    (results/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report['state'],report['exit_code'],report['triage'])
except Exception as exc:
    (results/'result.json').write_text(json.dumps({'state':'failed','error':str(exc)}),encoding='utf-8')
    print(exc)
''' 


def export_session(files, timeout_seconds=120):
    if sys.platform != 'win32':
        raise RuntimeError('Windows Sandbox export requires Windows and a normal Python installation.')
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
        raise ValueError('Timeout must be between 1 and 600 seconds.')
    python=Path(sys.base_prefix).resolve()
    if not (python/'python.exe').is_file():
        raise RuntimeError('Sandbox export requires python.exe under the base Python installation. Store/embedded installations are not supported.')
    index=files.index()
    if index['truncated']:
        raise ValueError('Sandbox input exceeds 1000 indexed files; export refused.')
    session=files.storage/'sandbox-sessions'/uuid.uuid4().hex
    project=session/'Input';scripts=session/'Scripts';results=session/'Results'
    total=0
    try:
        for folder in (project,scripts,results):folder.mkdir(parents=True,exist_ok=True)
        for row in index['files']:
            source=files._path(row['path'])
            with source.open('rb') as stream:data=stream.read(5_000_001)
            total+=len(data)
            if len(data)>5_000_000 or total>50_000_000:
                raise ValueError('Sandbox inputs exceed the 5 MB per-file or 50 MB total limit.')
            target=project/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        (scripts/'Run-Tests.ps1').write_text(SCRIPT,encoding='utf-8-sig')
        (scripts/'Sandbox-Run.py').write_text(HELPER.replace('TIMEOUT_SECONDS',str(timeout_seconds)),encoding='utf-8')
        package=scripts/'purple_dragon_agent';package.mkdir()
        (package/'__init__.py').write_text('',encoding='utf-8')
        for name in ('runner.py','runner_bootstrap.py','winjob.py'):
            shutil.copy2(Path(__file__).with_name(name),package/name)
        path=session/'Run-Unittest.wsb'
        path.write_text(configuration(project,python,scripts,results),encoding='utf-8')
        (session/'README.txt').write_text('Double-click Run-Unittest.wsb on a PC with Windows Sandbox enabled.\nInputs and Python are mapped read-only. Only this session Results folder is host-writable.\nTests use a disposable copy and network/clipboard are disabled. Base Python dependencies only; virtualenv packages are not copied.\nClose Windows Sandbox to cancel all sandbox work. Logs/results are untrusted output: do not execute files placed in Results.\nStreaming/timeout cancellation of the Sandbox window is manual in this release.\n'+CONFIG_DOC,encoding='utf-8')
        return {'configuration':str(path),'results_folder':str(results),'input_files':len(index['files']),
                'sandbox_executable_present':shutil.which('WindowsSandbox.exe') is not None,
                'status':'exported, not launched or verified','documentation':CONFIG_DOC}
    except Exception:
        shutil.rmtree(session,ignore_errors=True)
        raise
