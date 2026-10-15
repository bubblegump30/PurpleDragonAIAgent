"""Public v1 declarative plugin contract. No imports, scripts, shell or policy access."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid

API_VERSION=1
TOOLS={
    'list_files':{},'index_workspace':{},'preview_file':{'path':'path'},
    'analyze_code':{'paths':'paths'},'security_review':{'paths':'paths'},
    'detect_test_framework':{},'preview_tests':{},'run_tests':{},
    'propose_code_changes':{'paths':'paths','instruction':'text'},
}
ID=re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
INPUT_TYPES={'text','path','paths'}

def validate_value(value,kind):
    if kind=='paths':
        if not isinstance(value,list) or not 1<=len(value)<=8:raise ValueError('Use one to eight selected paths.')
        for path in value:validate_value(path,'path')
    elif not isinstance(value,str) or not value.strip() or len(value)>(512 if kind=='path' else 4000):raise ValueError('Invalid bounded text/path input.')
    elif kind=='path' and ('\x00' in value or '\\' in value or ':' in value or value.startswith('/') or any(x in value.split('/') for x in ('','..','.'))):raise ValueError('Paths must be explicit relative files, without aliases or traversal.')
    return copy.deepcopy(value)

def validate_manifest(value):
    if not isinstance(value,dict) or set(value)!={'api_version','id','name','version','description','inputs','steps'}:raise ValueError('Manifest must use the exact v1 fields.')
    if type(value['api_version']) is not int or value['api_version']!=API_VERSION:raise ValueError('Unsupported plugin API version.')
    if not isinstance(value['id'],str) or not ID.fullmatch(value['id']):raise ValueError('Invalid plugin identifier.')
    for key,limit in (('name',80),('version',40),('description',1000)):
        if not isinstance(value[key],str) or not value[key].strip() or len(value[key])>limit:raise ValueError('Invalid plugin metadata.')
    inputs=value['inputs'];steps=value['steps']
    if not isinstance(inputs,dict) or len(inputs)>8:raise ValueError('At most eight explicit inputs are supported.')
    for name,kind in inputs.items():
        if not isinstance(name,str) or not ID.fullmatch(name) or not isinstance(kind,str) or kind not in INPUT_TYPES:raise ValueError('Unsupported input declaration.')
    if not isinstance(steps,list) or not 1<=len(steps)<=8:raise ValueError('A plugin needs one to eight fixed steps.')
    for step in steps:
        if not isinstance(step,dict) or set(step)!={'tool','args'} or not isinstance(step['tool'],str) or step['tool'] not in TOOLS:raise ValueError('Plugin tool is outside the v1 contract.')
        schema=TOOLS[step['tool']];args=step['args']
        if not isinstance(args,dict) or set(args)!=set(schema):raise ValueError('Plugin tool arguments do not match its contract.')
        for key,kind in schema.items():
            arg=args[key]
            if isinstance(arg,dict):
                if set(arg)!={'$input'} or not isinstance(arg['$input'],str) or inputs.get(arg['$input'])!=kind:raise ValueError('Input reference must match its declared type.')
            else:validate_value(arg,kind)
    return copy.deepcopy(value)

class PluginCatalog:
    def __init__(self,folder):self.folder=Path(folder);self.reviews={};self.cancelled=threading.Event()
    def _read(self,identifier):
        if not isinstance(identifier,str) or not ID.fullmatch(identifier):raise ValueError('Unknown plugin.')
        path=self.folder/(identifier+'.json')
        if self.folder.is_symlink() or path.is_symlink():raise PermissionError('Linked plugin manifests are refused.')
        with path.open('rb') as stream:data=stream.read(64001)
        if len(data)>64000:raise ValueError('Plugin manifest exceeds 64 KB.')
        manifest=validate_manifest(json.loads(data))
        if manifest['id']!=identifier:raise ValueError('Plugin ID must match the filename.')
        return manifest,hashlib.sha256(data).hexdigest()
    def list(self):
        rows=[]
        if self.folder.is_symlink():return [{'id':'catalog','valid':False,'error':'Linked plugin folder refused.'}]
        for path in sorted(self.folder.glob('*.json'))[:32]:
            try:
                manifest,digest=self._read(path.stem)
                rows.append({'id':manifest['id'],'name':manifest['name'],'version':manifest['version'],'description':manifest['description'],'inputs':manifest['inputs'],'tools':[step['tool'] for step in manifest['steps']],'valid':True})
            except (OSError,ValueError,TypeError,RecursionError) as exc:rows.append({'id':path.stem,'valid':False,'error':str(exc)[:200]})
        return rows
    def preview(self,identifier,inputs):
        manifest,digest=self._read(identifier)
        if not isinstance(inputs,dict) or set(inputs)!=set(manifest['inputs']):raise ValueError('Supply exactly the declared plugin inputs.')
        inputs={key:validate_value(inputs[key],kind) for key,kind in manifest['inputs'].items()}
        steps=[]
        for step in manifest['steps']:
            args={key:copy.deepcopy(inputs[value['$input']] if isinstance(value,dict) else value) for key,value in step['args'].items()}
            steps.append({'tool':step['tool'],'args':args})
        review={'id':uuid.uuid4().hex,'plugin_id':identifier,'api_version':API_VERSION,'manifest_sha256':digest,'steps':steps,'created':time.monotonic(),'warning':'Fixed sequential tool workflow. Every step retains its own permission, approval and workspace checks. No code plugins or remote loading.'}
        self.reviews={review['id']:review};return copy.deepcopy(review)
    def execute(self,token,tools):
        if not isinstance(token,str) or token not in self.reviews:raise ValueError('Prepare a current plugin review.')
        review=self.reviews.pop(token)
        if time.monotonic()-review['created']>300:raise ValueError('Plugin review expired.')
        _,digest=self._read(review['plugin_id'])
        if digest!=review['manifest_sha256']:raise ValueError('Plugin manifest changed since review.')
        if self.cancelled.is_set():return {'ok':False,'message':'Plugin cancelled.','data':[]}
        decision=tools.permissions.check('plugin_run',copy.deepcopy(review),require_approval=True)
        tools.audit.record('plugin_permission',plugin=review['plugin_id'],approved=decision.approved,policy=decision.policy)
        if not decision.approved:return {'ok':False,'message':'Plugin execution denied.','data':[]}
        # Check again after approval; a manifest update never changes approved steps.
        if self._read(review['plugin_id'])[1]!=digest:raise ValueError('Plugin changed during approval.')
        if time.monotonic()-review['created']>300:raise ValueError('Plugin review expired during approval.')
        rows=[]
        for step in review['steps']:
            if self.cancelled.is_set():return {'ok':False,'message':'Plugin cancelled before the next step.','data':rows}
            result=tools.execute(step['tool'],step['args'])
            serialized=json.dumps(asdict(result),default=str,ensure_ascii=False)
            rows.append({'tool':step['tool'],'ok':result.ok,'output':serialized[:24000],'truncated':len(serialized)>24000})
            tools.audit.record('plugin_step',plugin=review['plugin_id'],tool=step['tool'],ok=result.ok)
            if self.cancelled.is_set():return {'ok':False,'message':'Plugin cancelled after the active tool finished; completed tool effects are retained.','data':rows}
            if not result.ok:return {'ok':False,'message':'Plugin stopped at a denied or failed tool.','data':rows}
        return {'ok':True,'message':'Reviewed plugin workflow completed.','data':rows}
