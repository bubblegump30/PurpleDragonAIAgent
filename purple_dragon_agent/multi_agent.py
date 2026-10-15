"""Bounded sequential specialists. Every tool uses the existing permission gateway."""
from dataclasses import asdict
import json
import threading
import time
import uuid

ROLES = ('Coding', 'Research', 'QA', 'Security', 'Release')

def validate_request(request):
    if not isinstance(request, dict) or set(request) - {'task','paths','source_ids','roles','propose','tests'}:
        raise ValueError('Invalid team request.')
    task = request.get('task', '')
    if not isinstance(task, str) or not task.strip() or len(task) > 4000:
        raise ValueError('Enter a goal of 1–4,000 characters.')
    roles = request.get('roles', list(ROLES))
    if not isinstance(roles, list) or not roles or len(roles)>5 or any(not isinstance(r,str) or r not in ROLES for r in roles) or len(set(roles))!=len(roles):
        raise ValueError('Select one to five known specialists.')
    result = {'task':task.strip(), 'roles':[r for r in ROLES if r in roles]}
    for key in ('paths','source_ids'):
        rows = request.get(key, [])
        if not isinstance(rows,list) or len(rows)>8 or any(not isinstance(v,str) or not v.strip() or len(v)>512 for v in rows):
            raise ValueError('Select at most eight paths or source IDs.')
        result[key] = list(dict.fromkeys(v.strip() for v in rows))
    for key in ('propose','tests'):
        value=request.get(key,False)
        if type(value) is not bool: raise ValueError('Options must be explicit booleans.')
        result[key]=value
    if result['propose'] and ('Coding' not in roles or not result['paths']):
        raise ValueError('Coding proposals require Coding and selected files.')
    if 'Research' in roles and len(result['source_ids'])>5:raise ValueError('Research briefs accept at most five cached sources.')
    if result['tests'] and 'QA' not in roles: raise ValueError('Test execution requires QA.')
    return result

def build_steps(request):
    """Deterministic preview only. Does not read source, contact models or execute tools."""
    steps=[]
    def tool(role,name,args):steps.append({'role':role,'tool':name,'args':args})
    def report(role,text,skip=False):steps.append({'role':role,'tool':'report','args':{},'note':text,'skip':skip})
    for role in request['roles']:
        if role=='Coding':
            if request['paths']:
                tool(role,'analyze_code',{'paths':request['paths']})
                if request['propose']:tool(role,'propose_code_changes',{'paths':request['paths'],'instruction':request['task']})
            else:report(role,'No selected files; coding skipped.',True)
        elif role=='Research':
            for source in request['source_ids']:tool(role,'read_web_source',{'source_id':source})
            if request['source_ids']:tool(role,'create_research_brief',{'source_ids':request['source_ids'],'question':request['task']})
            else:report(role,'No selected cached sources; research skipped. Fetch sources in Research first.',True)
        elif role=='QA':
            tool(role,'detect_test_framework',{})
            tool(role,'preview_tests',{'framework':'auto','timeout_seconds':120})
            if request['tests']:tool(role,'run_tests',{'framework':'auto','timeout_seconds':120})
            else:report(role,'Tests previewed only. Staged edits are not tested until separately applied.')
        elif role=='Security':
            if request['paths']:tool(role,'security_review',{'paths':request['paths']})
            else:report(role,'No selected files; security review skipped. Static heuristics are not certification.',True)
        elif role=='Release':
            tool(role,'index_workspace',{})
            report(role,'Readiness checklist: review staged diffs, apply separately with approval, test applied files, verify Windows manually and use reviewed Git tools for publication. No publication performed.')
    for index,step in enumerate(steps):step['id']='step-'+str(index+1)
    return steps

class MultiAgentSystem:
    def __init__(self, tools):
        self.tools=tools
        self.cancelled=threading.Event()
        self.pause_requested=threading.Event()
        self.lock=threading.RLock()
        self.execution_lock=threading.Lock()
        self.current=None
        self.reviews={}

    def snapshot(self):
        with self.lock:return json.loads(json.dumps(self.current)) if self.current else None

    def prepare(self,request=None,retry=False):
        with self.lock:
            if self.execution_lock.locked():raise ValueError('Wait for the active plan to finish.')
            previous=self.snapshot() if retry else None
            if retry:
                if request is not None:raise ValueError('Retry uses the blocked plan inputs. Prepare a new plan to change them.')
                if not previous or previous['state']!='blocked':raise ValueError('Only a blocked plan can prepare a failed-step retry.')
                if previous.get('attempt',1)>=4:raise ValueError('Three reviewed retries have been used. Inspect the evidence and prepare a new plan.')
                request=previous['request']
                failed=next((i for i,s in enumerate(previous['plan']) if s['state']=='failed'),None)
                if failed is None:raise ValueError('No failed tool step is available for retry. Prepare a new plan.')
                steps=[{k:v for k,v in s.items() if k not in {'state','error'}} for s in previous['plan'][failed:]]
                # Fresh context/command preparation is part of the reviewed retry.
                if steps[0]['tool']=='propose_code_changes':
                    steps.insert(0,{'id':'retry-source-check','role':'Coding','tool':'analyze_code','args':{'paths':request['paths']}})
                elif steps[0]['tool']=='run_tests':
                    steps.insert(0,{'id':'retry-test-preview','role':'QA','tool':'preview_tests','args':{'framework':'auto','timeout_seconds':120}})
            else:
                request=validate_request(request)
                steps=build_steps(request)
            token=uuid.uuid4().hex
            plan={'id':token,'request':request,'steps':steps,'retry_of':previous['id'] if previous else None,
                  'previous_error':previous['message'][:2000] if previous else None,
                  'warning':'Sequential work only. Every tool retains its policies and approvals. Proposals stage only; tests run current files on the host. Retry may repeat effects of a failed operation; inspect evidence first. Pause/cancel cannot undo an active tool.',
                  'expires_in_seconds':300}
            now=time.monotonic()
            self.reviews={k:v for k,v in self.reviews.items() if v['deadline']>now}
            if len(self.reviews)>=8:self.reviews.clear()
            self.reviews[token]={'deadline':now+300,'plan':json.loads(json.dumps(plan))}
            return json.loads(json.dumps(plan))

    def consume(self,token):
        if not isinstance(token,str):raise ValueError('Select a reviewed plan.')
        with self.lock:
            review=self.reviews.pop(token,None)
            if not review or review['deadline']<=time.monotonic():raise ValueError('Plan review expired or was already used. Prepare it again.')
            plan=review['plan']
            if plan['retry_of'] and (not self.current or self.current['id']!=plan['retry_of'] or self.current['state']!='blocked'):
                raise ValueError('The failed run changed. Prepare a fresh retry review.')
            return plan

    def pause(self):
        with self.lock:
            if not self.current or self.current['state'] not in {'running','pausing'}:return False
            self.pause_requested.set();self.current['pause_requested']=True;self.current['state']='pausing'
            return True

    def resume(self):
        with self.lock:
            if not self.current or self.current['state'] not in {'pausing','paused'}:return False
            self.pause_requested.clear();self.current['pause_requested']=False;self.current['state']='running'
            return True

    def cancel(self):
        with self.lock:
            if self.current and self.current['state'] in {'running','pausing','paused'}:self.current['state']='cancelling'
        self.cancelled.set()
        self.pause_requested.clear()
        self.tools.runner.cancel()

    def run(self,request):
        request=validate_request(request)
        return self.run_prepared({'id':uuid.uuid4().hex,'request':request,'steps':build_steps(request),'retry_of':None})

    def run_prepared(self,plan):
        if not self.execution_lock.acquire(blocking=False):return {'ok':False,'message':'Another plan is running.','data':self.snapshot()}
        request=plan['request'];previous=self.snapshot() if plan.get('retry_of') else None
        prior=[]
        if previous:
            prior=previous.get('prior_attempts',[])+[{'id':previous['id'],'state':previous['state'],'message':previous['message'][:2000],'steps':previous['steps']}]
        with self.lock:
            self.reviews.clear()
            self.current={'id':plan['id'],'state':'running','goal':request['task'],'request':request,'active':'Coordinator',
                          'roles':request['roles'],'handoffs':[],'steps':0,'attempt':previous.get('attempt',1)+1 if previous else 1,
                          'prior_attempts':prior[-3:],'pause_requested':False,
                          'plan':[dict(s,state='pending') for s in json.loads(json.dumps(plan['steps']))]}
        start=time.monotonic();source_hashes=None;current_step=None
        state='blocked';message='Plan did not complete.'
        def checkpoint():
            while True:
                if self.cancelled.is_set():raise InterruptedError('Cancelled. Active tool effects, if any, are retained; no further steps will start.')
                if time.monotonic()-start>900:raise InterruptedError('Plan wall-clock budget expired, including paused time. Inspect effects before restarting.')
                if not self.pause_requested.is_set():break
                with self.lock:self.current.update(state='paused',active=None)
                self.cancelled.wait(.1)
        try:
            for step in self.current['plan']:
                current_step=step
                checkpoint()
                with self.lock:
                    self.current.update(state='pausing' if self.pause_requested.is_set() else 'running',active=step['role'])
                    step['state']='running'
                role,name=step['role'],step['tool']
                if name=='report':
                    self.note(role,step['note'])
                    with self.lock:step['state']='skipped' if step.get('skip') else 'completed'
                    continue
                if self.current['steps']>=32:raise InterruptedError('Plan tool-call budget reached. Inspect results before preparing a new plan.')
                args=json.loads(json.dumps(step['args']))
                if name=='propose_code_changes':
                    if not isinstance(source_hashes,dict):raise ValueError('Fresh source validation is unavailable. Prepare a new coding plan.')
                    args['expected_hashes']=source_hashes
                self.tools.audit.record('team_specialist_started',role=role)
                value=self.tools.execute(name,args)
                with self.lock:
                    self.current['steps']+=1
                    data=json.dumps(asdict(value),ensure_ascii=False,default=str)
                    self.current['handoffs'].append({'step_id':step['id'],'role':role,'tool':name,'ok':value.ok,'output':data[:24000],'truncated':len(data)>24000})
                    step['state']='completed' if value.ok else 'failed'
                    if not value.ok:step['error']=str(value.message)[:2000]
                self.tools.audit.record('team_handoff',role=role,tool=name,ok=value.ok)
                if self.cancelled.is_set():checkpoint()
                if not value.ok:raise RuntimeError(value.message)
                if name=='analyze_code' and isinstance(value.data,dict):source_hashes=value.data.get('source_hashes')
            checkpoint()
            state='completed';message='Plan completed. Review evidence and skipped work; completion does not certify release readiness.'
        except InterruptedError as exc:
            state='cancelled';message=str(exc)
            if current_step and current_step['state']=='running':current_step['state']='interrupted'
        except Exception as exc:
            state='blocked';message=str(exc)
            if current_step:
                with self.lock:current_step.update(state='failed',error=message[:2000])
        finally:
            self.pause_requested.clear()
            with self.lock:self.current.update(state=state,active=None,pause_requested=False,message=message)
            self.execution_lock.release()
        try:self.tools.audit.record('team_finished',state=state,steps=self.current['steps'])
        except OSError:
            with self.lock:self.current['message']+=' Audit storage is unavailable; inspect operation effects before retrying.'
        return {'ok':state=='completed','message':self.current['message'],'data':self.snapshot()}

    def note(self,role,message,data=None):
        with self.lock:self.current['handoffs'].append({'role':role,'tool':'report','ok':True,'output':message,'data':data})
