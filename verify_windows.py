"""Native WebView startup, bridge and viewport verification in temporary data."""
import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
import threading
import time
import subprocess
import shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',default='windows-verification.json')
    options=parser.parse_args()
    report={'platform':platform.platform(),'windows_native':sys.platform=='win32','status':'failed','windows_acceptance':'pending_manual_checks','checks':[]}
    try:
        import webview
        from purple_dragon_agent import desktop
        root=Path(__file__).resolve().parent
        original_create=webview.create_window
        with tempfile.TemporaryDirectory(prefix='purple-dragon-webview-check-') as temp:
            data=Path(temp);(data/'config').mkdir()
            config=json.loads((root/'config/default_config.json').read_text())
            (data/'config/default_config.json').write_text(json.dumps(config))
            api=desktop.DesktopAPI(config,data,persist=False)
            (api._workspace.root/'verify.txt').write_text('Temporary verification file')
            # Materialize only packaged inputs into the isolated verification app folder.
            if (root/'RELEASE-MANIFEST.json').is_file():
                manifest=json.loads((root/'RELEASE-MANIFEST.json').read_text())
                for row in manifest['files']:
                    source=root/row['path'];target=data/row['path']
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                shutil.copy2(root/'RELEASE-MANIFEST.json',data/'RELEASE-MANIFEST.json')
            report['version']=config['version']
            def create(*args,**kwargs):
                window=original_create(*args,**kwargs)
                def check():
                    try:
                        if not api._ready.wait(5):
                            raise RuntimeError("UI bridge did not report ready")
                        state=window.evaluate_js("({bridge:typeof window.pywebview.api.state,composer:!!document.getElementById('prompt'),title:document.title})")
                        report['checks'].append({'name':'native_bridge','passed':state['bridge']=='function' and state['composer'],'data':state})
                        window.evaluate_js("document.getElementById('prompt').value='scan workspace';document.getElementById('send').click()")
                        deadline=time.monotonic()+5
                        while time.monotonic()<deadline:
                            time.sleep(.25)
                            if window.evaluate_js("document.getElementById('conversation').textContent.includes('verify.txt')"):
                                break
                        result=window.evaluate_js("document.getElementById('conversation').textContent.includes('verify.txt')")
                        report['checks'].append({'name':'real_workspace_task','passed':bool(result)})
                        original_execute=api._tools.execute
                        entered=threading.Event();release_step=threading.Event()
                        def delayed_execute(name,args):
                            if name=='security_review':entered.set();release_step.wait(5)
                            return original_execute(name,args)
                        api._tools.execute=delayed_execute
                        window.evaluate_js("view('agents',true);document.getElementById('team-task').value='Review selected file';document.getElementById('team-paths').value='verify.txt';document.querySelectorAll('[data-role]').forEach(e=>e.checked=e.dataset.role==='Security'||e.dataset.role==='Release');document.querySelector('[data-action=prepare-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null"):time.sleep(.1)
                        report['checks'].append({'name':'planning_preview_executes_no_tools_native','passed':not entered.is_set() and api.state()['team'] is None and bool(window.evaluate_js("$('team-plan-review').textContent.includes('security_review')"))})
                        window.evaluate_js("$('team-task').value='Edited goal';$('team-task').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-action=start-team]').click()")
                        report['checks'].append({'name':'planning_edited_form_requires_new_review_native','passed':api.state()['team'] is None})
                        window.evaluate_js("$('team-task').value='Review selected file';document.querySelector('[data-action=prepare-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null"):time.sleep(.1)
                        window.evaluate_js("document.querySelector('[data-action=start-team]').click()")
                        entered.wait(2);time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=pause-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not api.state()['team']['pause_requested']:time.sleep(.1)
                        release_step.set()
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['team']['state']!='paused':time.sleep(.1)
                        team=api.state()['team']
                        report['checks'].append({'name':'planning_pause_at_tool_boundary_native','passed':team['state']=='paused' and team['steps']==1 and not any(h['role']=='Release' for h in team['handoffs'])})
                        time.sleep(.7)
                        report['checks'].append({'name':'planning_paused_queue_status_native','passed':bool(window.evaluate_js("$('queue-pill').textContent==='1 PAUSED' && $('queue-state').textContent==='Paused'"))})
                        window.evaluate_js("document.querySelector('[data-action=resume-team]').click()")
                        deadline=time.monotonic()+5
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            team=api.state()['team']
                            if team and team['state']!='running':break
                        team=api.state()['team']
                        report['checks'].append({'name':'multi_agent_native_panel','passed':bool(team and team['state']=='completed' and team['steps']==2)})
                        time.sleep(.7)
                        visible=window.evaluate_js("document.getElementById('team-live').textContent.includes('Release → index_workspace')")
                        report['checks'].append({'name':'multi_agent_live_handoffs','passed':bool(visible)})
                        report['checks'].append({'name':'planning_step_progress_native','passed':bool(window.evaluate_js("$('team-progress').textContent.includes('3 / 3') && $('team-steps').textContent.includes('COMPLETED')"))})
                        entered.clear();release_step.clear()
                        window.evaluate_js("document.querySelector('[data-action=prepare-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null"):time.sleep(.1)
                        window.evaluate_js("document.querySelector('[data-action=start-team]').click()")
                        entered.wait(2);time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=pause-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not api.state()['team']['pause_requested']:time.sleep(.1)
                        release_step.set()
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['team']['state']!='paused':time.sleep(.1)
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=cancel-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        report['checks'].append({'name':'planning_cancel_paused_native','passed':api.state()['team']['state']=='cancelled' and api.state()['team']['steps']==1})
                        api._tools.execute=original_execute
                        api._permissions.set_policy('security_review','deny')
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=prepare-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null"):time.sleep(.1)
                        window.evaluate_js("document.querySelector('[data-action=start-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        api._permissions.set_policy('security_review','allow');time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=prepare-team-retry]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null && teamReviewRetry"):time.sleep(.1)
                        report['checks'].append({'name':'planning_retry_review_native','passed':bool(window.evaluate_js("$('team-plan-review').textContent.includes('Previous failure:')"))})
                        window.evaluate_js("document.querySelector('[data-action=retry-team]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        report['checks'].append({'name':'planning_retry_completes_native','passed':api.state()['team']['state']=='completed' and api.state()['team']['attempt']==2})

                        window.evaluate_js("view('chat',true)")
                        for width,height in ((1672,941),(1280,800),(1050,650)):
                            window.resize(width,height)
                            time.sleep(.25)
                            box=window.evaluate_js("(()=>{const r=document.getElementById('stage').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,w:innerWidth,h:innerHeight}})()")
                            fits=box['x']>=-1 and box['y']>=-1 and box['x']+box['width']<=box['w']+1 and box['y']+box['height']<=box['h']+1
                            report['checks'].append({'name':f'viewport_{width}x{height}','passed':fits,'data':box})
                            controls=window.evaluate_js("[...document.querySelectorAll('#prompt,#send,.composer-model,#composer-tools,#footer-workspace,#footer-memory')].map(el=>{const r=el.getBoundingClientRect();return {id:el.id||el.className,fits:r.top>=0&&r.bottom<=innerHeight+1&&r.left>=0&&r.right<=innerWidth+1}})")
                            report['checks'].append({'name':f'bottom_controls_{width}x{height}','passed':all(row['fits'] for row in controls),'data':controls})
                        window.evaluate_js("document.querySelector('.nav.settings').click()")
                        time.sleep(.2)
                        settings=window.evaluate_js("!!document.getElementById('lm-endpoint')")
                        report['checks'].append({'name':'settings_navigation','passed':bool(settings)})
                        window.evaluate_js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'2',ctrlKey:true,bubbles:true}))")
                        time.sleep(.2)
                        shortcut=window.evaluate_js("document.getElementById('route-title').textContent==='PURPLE DRAGON AI AGENT 2.0'")
                        report['checks'].append({'name':'ctrl_2_tools_shortcut','passed':bool(shortcut),'data':window.evaluate_js("({active:activeView,touched:formTouched,dirty:hasUnsavedForm(),dialog:$('unsaved-dialog').open,title:$('route-title').textContent})")})
                        window.evaluate_js("document.querySelector('.nav.chat').focus()")
                        focus=window.evaluate_js("document.activeElement.getAttribute('aria-label')==='Chat'")
                        report['checks'].append({'name':'navigation_keyboard_focus','passed':bool(focus)})
                        window.evaluate_js("document.querySelector('.bottom-workspace').click();document.getElementById('file-path').value='verify.txt';document.getElementById('file-content').value='replacement';document.querySelector('[data-action=stage-file]').click()")
                        deadline=time.monotonic()+5
                        while time.monotonic()<deadline:
                            time.sleep(.15)
                            if window.evaluate_js("document.getElementById('approval').open"):
                                break
                        approval=window.evaluate_js("document.getElementById('approval').open")
                        report['checks'].append({'name':'mandatory_approval_visible','passed':bool(approval)})
                        window.evaluate_js("document.getElementById('approval').dispatchEvent(new Event('cancel',{cancelable:true}))")
                        deadline=time.monotonic()+3
                        while api.state()['busy'] and time.monotonic()<deadline:
                            time.sleep(.1)
                        denied=api.state()['job']['result']
                        unchanged=(api._workspace.root/'verify.txt').read_text()=='Temporary verification file'
                        report['checks'].append({'name':'approval_cancel_rejects_without_writing','passed':unchanged and denied is not None and not denied['ok']})
                        class ModelFixture(BaseHTTPRequestHandler):
                            def log_message(self,*args):pass
                            def do_GET(self):
                                self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"fixture-chat"}]}')
                            def do_POST(self):
                                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                                content='OK'
                                if 'local coding assistant' in payload['messages'][0]['content']:
                                    request=json.loads(payload['messages'][1]['content'])
                                    content=json.dumps({'summary':'Update both source values','changes':[{'path':row['path'],'content':row['content'].replace('=1','=2'),'reason':'Requested value update'} for row in request['selected_files']]})
                                self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'choices':[{'message':{'content':content}}]}).encode())
                        fixture=ThreadingHTTPServer(('127.0.0.1',0),ModelFixture)
                        thread=threading.Thread(target=fixture.serve_forever,daemon=True);thread.start()
                        try:
                            window.evaluate_js("document.querySelector('.nav.settings').click()")
                            endpoint=f'http://127.0.0.1:{fixture.server_port}/v1/chat/completions'
                            window.evaluate_js("document.getElementById('lm-enabled').checked=true;document.getElementById('lm-endpoint').value="+json.dumps(endpoint)+";document.querySelector('[data-action=\"refresh-models\"]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if api.state()['connection']['status']=='server_ready':break
                            server_ready=api.state()['connection']['status']=='server_ready'
                            report['checks'].append({'name':'model_center_discovery','passed':server_ready})
                            time.sleep(.7)
                            window.evaluate_js("document.getElementById('available-models').value='fixture-chat';document.getElementById('available-models').dispatchEvent(new Event('change'));document.querySelector('[data-action=\"test-model\"]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if api.state()['connection']['status']=='verified':break
                            verified=api.state()['connection']['status']=='verified'
                            report['checks'].append({'name':'model_center_selected_inference','passed':verified})
                            time.sleep(.7)
                            label=window.evaluate_js("document.getElementById('model-value').textContent")
                            report['checks'].append({'name':'dashboard_verified_status','passed':label=='VERIFIED'})
                            window.evaluate_js("$('lm-temperature').value='0.6';$('lm-max-tokens').value='777';$('lm-timeout').value='150';document.querySelector('[data-action=model-profile-save]').click()")
                            deadline=time.monotonic()+3
                            while time.monotonic()<deadline and api._config['lm_studio']['max_tokens']!=777:time.sleep(.1)
                            time.sleep(.7)
                            options=api._config['lm_studio']
                            report['checks'].append({'name':'model_profile_save_native','passed':options['profiles'].get('fixture-chat')=={'temperature':.6,'max_tokens':777,'timeout_seconds':150} and api._model.max_tokens==777})
                            window.evaluate_js("$('lm-temperature').value='1';$('lm-max-tokens').value='1';document.querySelector('[data-action=model-profile-load]').click()")
                            report['checks'].append({'name':'model_profile_load_native','passed':bool(window.evaluate_js("$('lm-temperature').value==='0.6' && $('lm-max-tokens').value==='777'"))})
                            window.evaluate_js("document.querySelector('[data-action=model-diagnostics]').click()")
                            time.sleep(.5)
                            diagnostic=window.evaluate_js("$('model-diagnostics').textContent")
                            report['checks'].append({'name':'local_model_diagnostics_native','passed':json.loads(diagnostic)['max_tokens']==777 and 'workspace' not in json.loads(diagnostic)})
                            window.evaluate_js("$('lm-preset').value='creative';document.querySelector('[data-action=model-preset]').click()")
                            report['checks'].append({'name':'model_preset_is_unsaved_native','passed':bool(window.evaluate_js("$('lm-temperature').value==='0.8' && $('lm-max-tokens').value==='4096'")) and api._config['lm_studio']['max_tokens']==777})
                            window.evaluate_js("document.querySelector('[data-action=model-profile-delete]').click()")
                            time.sleep(.8)
                            report['checks'].append({'name':'model_profile_delete_preserves_active_native','passed':not api._config['lm_studio']['profiles'] and api._config['lm_studio']['max_tokens']==777})

                            window.evaluate_js("view('chat',true);$('prompt').value='Write a Python function that adds two numbers. Explain it without changing any files.';$('send').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                job=api.state()['job']
                                if job and job['state']!='running':break
                            time.sleep(.7)
                            result=job.get('result') or {}
                            chat_ok=window.evaluate_js("$('conversation').textContent.includes('OK') && !$('conversation').textContent.includes('relative/source.py')")
                            report['checks'].append({'name':'conversation_native_plain_answer','passed':bool(chat_ok and result.get('ok'))})
                            window.evaluate_js("showModelContext()")
                            time.sleep(.5)
                            report['checks'].append({'name':'knowledge_outgoing_receipt_native','passed':bool(window.evaluate_js("!$('model-context-panel').hidden && $('model-context-text').textContent.includes('EXACT SERIALIZED REQUEST') && $('model-context-text').textContent.includes('adds two numbers')"))})
                            for width,height in ((1672,941),(1280,800),(1050,650)):
                                window.resize(width,height);time.sleep(.2)
                                fits=window.evaluate_js("(()=>{let r=$('model-context-panel').getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})()")
                                report['checks'].append({'name':f'knowledge_receipt_viewport_{width}x{height}','passed':bool(fits)})
                            window.evaluate_js("$('model-context-close').click()")


                            api._tools.files.discard()
                            for name in ('validation_a.py','validation_b.py'):(api._workspace.root/name).write_text('value=1\n')
                            window.evaluate_js("view('coding',true);$('code-paths').value='validation_a.py\\nvalidation_b.py';$('code-instruction').value='Update both values to 2';document.querySelector('[data-action=analyze-code]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if window.evaluate_js("codingValidation!==null"):break
                            report['checks'].append({'name':'coding_preflight_native','passed':bool(window.evaluate_js("codingValidation!==null && $('coding-validation').textContent.includes('2 file(s)')"))})
                            (api._workspace.root/'validation_a.py').write_text('value=3\n')
                            window.evaluate_js("document.querySelector('[data-action=propose-code]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if api.state()['approval']:window.evaluate_js("$('allow').click()")
                                job=api.state()['job']
                                if job and job['state']=='finished' and job['label']=='propose_code_changes':break
                            report['checks'].append({'name':'coding_stale_preflight_refused_native','passed':bool(job and not job['result']['ok'] and 'stale' in job['result']['message'] and not api._tools.files.pending_path.exists())})
                            (api._workspace.root/'validation_a.py').write_text('value=1\n')
                            time.sleep(.7)
                            window.evaluate_js("document.querySelector('[data-action=analyze-code]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if window.evaluate_js("codingValidation!==null"):break
                            window.evaluate_js("document.querySelector('[data-action=propose-code]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if api.state()['approval']:window.evaluate_js("$('allow').click()")
                                job=api.state()['job']
                                if job and job['state']=='finished' and job['label']=='propose_code_changes':break
                            time.sleep(.7)
                            staged=job['result']['ok'] and len(job['result']['data']['review']['paths'])==2 and (api._workspace.root/'validation_a.py').read_text()=='value=1\n'
                            report['checks'].append({'name':'coding_multifile_staged_report_native','passed':bool(staged and window.evaluate_js("$('coding-proposal').textContent.includes('2 changed file(s)')"))})
                            window.evaluate_js("document.querySelector('[data-action=review]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if window.evaluate_js("lastReview!==null"):break
                            window.evaluate_js("document.querySelector('[data-action=apply]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                approval=api.state()['approval']
                                if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                                time.sleep(.1)
                            report['checks'].append({'name':'coding_apply_still_mandatory_native','passed':bool(api.state()['approval'] and api.state()['approval']['action']=='write_file')})
                            window.evaluate_js("$('allow').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                            (api._workspace.root/'tests').mkdir(exist_ok=True)
                            (api._workspace.root/'tests/test_validation.py').write_text('import unittest\nclass Checks(unittest.TestCase):\n    def test_failure(self): self.assertEqual(1,2)\n')
                            time.sleep(.7)
                            window.evaluate_js("view('terminal',true);$('test-framework').value='unittest';$('test-timeout').value='15';document.querySelector('[data-action=preview-tests]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if window.evaluate_js("testPreviewKey!==null"):break
                            window.evaluate_js("document.querySelector('[data-action=run-tests]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                approval=api.state()['approval']
                                if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                                time.sleep(.1)
                            report['checks'].append({'name':'validation_tests_require_approval_native','passed':bool(api.state()['approval'] and api.state()['approval']['action']=='run_tests'),'data':{'job':api.state()['job'],'ui':window.evaluate_js("({toast:$('toast').textContent,preview:testPreviewKey,key:testFormKey(),current:currentJob?.name})")}})
                            window.evaluate_js("$('allow').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                            time.sleep(.7)
                            summary=api.state()['runner']['summary']
                            report['checks'].append({'name':'validation_failed_test_summary_native','passed':bool(summary and summary['outcome']=='failed' and summary['counts']['run']==1 and window.evaluate_js("$('test-summary').textContent.includes('test_failure')")),'data':{'summary':summary,'job':api.state()['job']}})
                            window.evaluate_js("view('agents',true);$('team-task').value='Review failed tests';document.querySelectorAll('[data-role]').forEach(e=>e.checked=e.dataset.role==='QA');$('team-tests').checked=true;document.querySelector('[data-action=prepare-team]').click()")
                            deadline=time.monotonic()+3
                            while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null"):time.sleep(.1)
                            window.evaluate_js("document.querySelector('[data-action=start-team]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                approval=api.state()['approval']
                                if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                                time.sleep(.1)
                            first_test_approval=api.state()['approval']
                            window.evaluate_js("$('allow').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                            time.sleep(.7)
                            window.evaluate_js("document.querySelector('[data-action=prepare-team-retry]').click()")
                            deadline=time.monotonic()+3
                            while time.monotonic()<deadline and not window.evaluate_js("teamReview!==null && teamReviewRetry"):time.sleep(.1)
                            window.evaluate_js("document.querySelector('[data-action=retry-team]').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline:
                                approval=api.state()['approval']
                                if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                                time.sleep(.1)
                            retry_approval=api.state()['approval']
                            report['checks'].append({'name':'planning_host_test_retry_requires_fresh_approval_native','passed':bool(first_test_approval and retry_approval and retry_approval['action']=='run_tests' and retry_approval['id']!=first_test_approval['id'])})
                            window.evaluate_js("$('deny').click()")
                            deadline=time.monotonic()+4
                            while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                            report['checks'].append({'name':'planning_denied_retry_stops_native','passed':api.state()['team']['state']=='blocked' and api.state()['team']['attempt']==2})
                        finally:
                            fixture.shutdown();fixture.server_close();thread.join()
                        deadline=time.monotonic()+4
                        while time.monotonic()<deadline and window.evaluate_js("snapshot?.busy || currentJob!==null"):time.sleep(.1)
                        if shutil.which('git'):
                            repository=api._workspace.root/'git-fixture';repository.mkdir()
                            for command in (['init','-b','main'],['config','user.name','Verification'],['config','user.email','verify@example.invalid']):
                                subprocess.run(['git',*command],cwd=repository,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            (repository/'sample.txt').write_text('temporary repository')
                            for command in (['add','sample.txt'],['commit','-m','Verification fixture']):
                                subprocess.run(['git',*command],cwd=repository,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            window.evaluate_js("document.querySelector('.nav.tools').click();document.querySelector('[data-view=\"git\"]').click();document.getElementById('git-repo').value='git-fixture';document.getElementById('git-branch').value='ui-verification';document.querySelector('[data-action=\"git-preview\"]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                result=api.state()['job']
                                if result and result['state']=='finished' and result['result']['message'].startswith('Git operation prepared'):break
                            report['checks'].append({'name':'git_panel_preview','detail':{'job':result,'toast':window.evaluate_js("$('toast').textContent")},'passed':bool(result and result['result'] and result['result']['ok'] and result['result']['message'].startswith('Git operation prepared'))})
                            time.sleep(.7)
                            window.evaluate_js("document.querySelector('[data-action=\"git-execute\"]').click()")
                            deadline=time.monotonic()+5
                            while time.monotonic()<deadline:
                                time.sleep(.1)
                                if window.evaluate_js("document.getElementById('approval').open"):break
                            window.evaluate_js("document.getElementById('allow').click()")
                            deadline=time.monotonic()+5
                            while api.state()['busy'] and time.monotonic()<deadline:time.sleep(.1)
                            created=subprocess.run(['git','branch','--list','ui-verification'],cwd=repository,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
                            report['checks'].append({'name':'git_panel_approved_branch','passed':bool(created)})
                        else:
                            report['checks'].append({'name':'git_panel_preview','passed':False,'detail':'Git is unavailable; install it to verify the Git panel.'})
                        window.evaluate_js("view('security',true);document.getElementById('session-profile').value='read_only';document.querySelector('[data-action=\"session-profile\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['security']['profile']!='read_only':time.sleep(.1)
                        report['checks'].append({'name':'security_session_scope_ui','passed':api.state()['security']['profile']=='read_only'})
                        blocked=api._tools.execute('write_file',{'path':'blocked.txt','content':'no'})
                        report['checks'].append({'name':'security_scope_enforced','passed':not blocked.ok and not (api._workspace.root/'blocked.txt').exists()})
                        window.evaluate_js("document.getElementById('session-profile').value='standard';document.querySelector('[data-action=\"session-profile\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['security']['profile']!='standard':time.sleep(.1)
                        (api._workspace.root/'security-sample.py').write_text('eval(user_input)')
                        (api._workspace.root/'security-second.py').write_text('exec(user_input)')
                        window.evaluate_js("document.getElementById('security-paths').value='security-sample.py\\nsecurity-second.py';document.querySelector('[data-action=\"security-review\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='security_review':break
                        report['checks'].append({'name':'security_static_review_ui','passed':bool(job and job['result'] and job['result']['ok'] and job['result']['data']['findings'])})
                        report['checks'].append({'name':'multiline_selected_paths','passed':bool(job['result'] and job['result']['ok'] and len(job['result']['data']['files'])==2)})
                        (api._workspace.root/'.env').write_text('private-value')
                        denied=api._tools.execute('preview_file',{'path':'.env'})
                        report['checks'].append({'name':'security_protected_path','passed':not denied.ok})
                        time.sleep(.7)
                        live=window.evaluate_js("document.getElementById('security-live').textContent.includes('standard')")
                        report['checks'].append({'name':'security_live_status','passed':bool(live)})
                        window.evaluate_js("view('recovery',true);document.querySelector('[data-action=\"settings-backup\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='backup':break
                        backup=job['result']['data'] if job and job['result'] and job['result']['ok'] else None
                        report['checks'].append({'name':'settings_checkpoint_ui','passed':bool(backup and backup['id'])})
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=\"settings-backups\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='list_backups':break
                        time.sleep(.7)
                        selected=window.evaluate_js("(()=>{const b=document.querySelector('#settings-backup-list button');if(!b)return '';b.click();return document.getElementById('settings-backup-id').value;})()")
                        report['checks'].append({'name':'checkpoint_selector_ui','passed':selected==backup['id']})
                        window.evaluate_js("document.getElementById('settings-backup-id').value="+json.dumps(backup['id'])+";document.querySelector('[data-action=\"settings-preview\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='preview_restore':break
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=\"settings-restore\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            if api.state()['approval'] and window.evaluate_js("document.getElementById('approval').open && document.getElementById('approval-action').textContent.includes('restore settings')"):break
                            time.sleep(.1)
                        approval=api.state()['approval']
                        report['checks'].append({'name':'settings_restore_mandatory_approval','passed':bool(approval and approval['action']=='restore_settings')})
                        window.evaluate_js("document.getElementById('allow').click()")
                        deadline=time.monotonic()+3
                        while api.state()['busy'] and time.monotonic()<deadline:time.sleep(.1)
                        job=api.state()['job']
                        report['checks'].append({'name':'settings_restore_applied','message':(job.get('result') or {}).get('message'),'passed':bool(job['result'] and job['result']['ok'] and (data/'config/user_config.json').is_file())})
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=\"candidate-checks\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='readiness':break
                        report['checks'].append({'name':'candidate_integrity_ui','result':job.get('result'),'passed':bool(job['result'] and job['result']['ok'] and job['result']['data']['status']=='candidate_checks_passed')})
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and window.evaluate_js("snapshot?.busy===true"):time.sleep(.1)
                        window.evaluate_js("document.querySelector('[data-action=release-trust]').click()")
                        deadline=time.monotonic()+4
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['label']=='trust':break
                        report['checks'].append({'name':'release_trust_local_evidence_native','passed':bool(job and job['result'] and job['result']['ok'] and job['result']['data']['publisher_verification']['status']=='not_applicable_source')})
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('release-trust-report').textContent.includes('manifest_sha256')"):break
                        report['checks'].append({'name':'release_trust_visible_copy_native','passed':bool(window.evaluate_js("$('release-trust-report').textContent.includes('not_applicable_source') && !!document.querySelector('[data-action=copy-release-trust]')"))})
                        window.evaluate_js("view('plugins',true);document.querySelector('[data-action=\"plugin-preview\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1);job=api.state()['job']
                            if job and job['state']=='finished' and job['kind']=='plugin' and job['label']=='preview':break
                        plugin_ok=bool(job and job['kind']=='plugin' and job['result'] and job['result']['ok'] and isinstance(job['result']['data'],dict) and job['result']['data'].get('api_version')==1)
                        if not plugin_ok:raise RuntimeError('Plugin preview did not start/finish: '+json.dumps(job)+'; UI: '+str(window.evaluate_js("document.getElementById('toast').textContent")))
                        report['checks'].append({'name':'plugin_contract_review_ui','passed':plugin_ok})
                        time.sleep(.7)
                        window.evaluate_js("document.querySelector('[data-action=\"plugin-run\"]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            if api.state()['approval'] and window.evaluate_js("document.getElementById('approval').open && document.getElementById('approval-action').textContent.includes('plugin run')"):break
                            time.sleep(.1)
                        approval=api.state()['approval']
                        report['checks'].append({'name':'plugin_mandatory_approval_ui','passed':bool(approval and approval['action']=='plugin_run')})
                        window.evaluate_js("document.getElementById('allow').click()")
                        deadline=time.monotonic()+3
                        while api.state()['busy'] and time.monotonic()<deadline:time.sleep(.1)
                        job=api.state()['job']
                        report['checks'].append({'name':'plugin_workflow_real_tools','passed':bool(job['result'] and job['result']['ok'] and len(job['result']['data'])==2)})
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and window.evaluate_js("snapshot?.busy===true"):time.sleep(.1)
                        old_plugin_job=api.state()['job']['id']
                        window.evaluate_js("document.querySelector('[data-action=\"plugin-preview\"]').click();document.getElementById('plugin-id').value='source-review';document.getElementById('plugin-id').dispatchEvent(new Event('input'))")
                        deadline=time.monotonic()+3
                        while api.state()['busy'] and time.monotonic()<deadline:time.sleep(.1)
                        time.sleep(.8)
                        invalidated=window.evaluate_js("pluginReview===null") and api.state()['job']['id']!=old_plugin_job
                        report['checks'].append({'name':'edited_form_rejects_late_plugin_review','passed':bool(invalidated)})
                        window.evaluate_js("view('settings',true);document.getElementById('lm-model').value='unsaved-guide-check';document.dispatchEvent(new KeyboardEvent('keydown',{key:'F1',bubbles:true}))")
                        report['checks'].append({'name':'guide_context_f1','passed':bool(window.evaluate_js("!$('guide-panel').hidden && $('guide-title').textContent==='Settings & local model'"))})
                        window.evaluate_js("$('guide-search').value='sandbox';guideSearch()")
                        report['checks'].append({'name':'guide_offline_search','passed':bool(window.evaluate_js("$('guide-topics').textContent.includes('Security & Sandbox') && !$('guide-topics').textContent.includes('Chat & modes')"))})
                        window.evaluate_js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                        report['checks'].append({'name':'guide_preserves_unsaved_form','passed':bool(window.evaluate_js("$('guide-panel').hidden && activeView==='settings' && $('lm-model').value==='unsaved-guide-check'"))})
                        window.evaluate_js("openGuide('start',true);$('guide-next').click()")
                        report['checks'].append({'name':'guide_tour_navigation','passed':bool(window.evaluate_js("$('guide-title').textContent==='Chat & modes' && $('guide-progress').textContent.includes('2 of')"))})
                        for width,height in ((1672,941),(1280,800),(1050,650)):
                            window.resize(width,height);time.sleep(.2)
                            fits=window.evaluate_js("(()=>{let r=$('guide-panel').getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})()")
                            report['checks'].append({'name':f'guide_viewport_{width}x{height}','passed':bool(fits)})
                        window.evaluate_js("closeGuide();$('approval').showModal();openGuide('settings')")
                        report['checks'].append({'name':'guide_yields_to_approval','passed':bool(window.evaluate_js("$('guide-panel').hidden && $('approval').open"))})
                        window.evaluate_js("$('approval').close()")
                        window.evaluate_js("newConversation()")
                        time.sleep(.5)
                        cid=window.evaluate_js("conversationId")
                        saved=api._conversation_store().get(cid)
                        api._conversation_store().update(cid,title='Native saved chat',messages=[{'role':'user','text':'Find the dragon'},{'role':'assistant','text':'Example:\n```python\ndef add(a,b): return a+b\n```\n<img src=x onerror=alert(1)>'}])
                        window.evaluate_js("loadConversation(conversationId)");time.sleep(.5)
                        rendered=window.evaluate_js("$('conversation').querySelectorAll('pre code').length===1 && $('conversation').querySelectorAll('img').length===0 && $('conversation').textContent.includes('Copy code')")
                        report['checks'].append({'name':'saved_chat_safe_code_rendering','passed':bool(rendered)})
                        window.evaluate_js("$('chat-history').click();$('history-query').value='dragon';refreshConversations()")
                        time.sleep(.5)
                        report['checks'].append({'name':'conversation_history_fulltext_search','passed':bool(window.evaluate_js("$('history-list').textContent.includes('Native saved chat')"))})
                        window.evaluate_js("$('history-list').querySelector('input').value='Renamed conversation';[...$('history-list').querySelectorAll('button')].find(b=>b.textContent==='Rename').click()")
                        time.sleep(.5)
                        report['checks'].append({'name':'conversation_rename_native','passed':api._conversation_store().get(cid)['title']=='Renamed conversation'})
                        for width,height in ((1672,941),(1280,800),(1050,650)):
                            window.resize(width,height);time.sleep(.2)
                            fits=window.evaluate_js("(()=>{let r=$('conversation-panel').getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})()")
                            report['checks'].append({'name':f'conversation_viewport_{width}x{height}','passed':bool(fits)})
                        window.evaluate_js("[...$('history-list').querySelectorAll('button')].find(b=>b.textContent==='Delete').click()")
                        report['checks'].append({'name':'conversation_delete_requires_confirmation','passed':bool(api._conversation_store().get(cid) and window.evaluate_js("!!$('history-list').querySelector('.delete-confirm')"))})
                        window.evaluate_js("[...$('history-list').querySelectorAll('button')].find(b=>b.textContent==='Delete permanently').click()")
                        time.sleep(.5)
                        report['checks'].append({'name':'conversation_delete_native','passed':not any(r['id']==cid for r in api._conversation_store().list())})
                        window.evaluate_js("$('history-close').click()")
                        window.evaluate_js("view('workspace',true)")
                        (api._workspace.root/'nested').mkdir(exist_ok=True)
                        (api._workspace.root/'nested/example.py').write_text('value=1\n')
                        files=api._tools.execute('list_files',{}).data
                        window.evaluate_js("renderFiles("+json.dumps(files)+")")
                        window.evaluate_js("$('file-search').value='nested/';workspaceTree()")
                        report['checks'].append({'name':'workspace_tree_search','passed':bool(window.evaluate_js("$('files-list').textContent.includes('example.py') && $('file-list-summary').textContent.includes('1 matching')"))})
                        window.evaluate_js("$('files-list').querySelector('input[type=checkbox]').click();$('context-to-coding').click()")
                        report['checks'].append({'name':'workspace_selected_coding_context','passed':bool(window.evaluate_js("activeView==='coding' && $('code-paths').value==='nested/example.py'"))})
                        window.evaluate_js("$('code-instruction').value='Keep this instruction';$('code-instruction').dispatchEvent(new Event('input',{bubbles:true}));view('workspace')")
                        report['checks'].append({'name':'workspace_unsaved_navigation_guard','passed':bool(window.evaluate_js("$('unsaved-dialog').open && activeView==='coding'"))})
                        window.evaluate_js("$('unsaved-stay').click()")
                        report['checks'].append({'name':'workspace_keep_unsaved_form','passed':bool(window.evaluate_js("$('code-instruction').value==='Keep this instruction' && activeView==='coding'"))})
                        window.evaluate_js("view('workspace');$('unsaved-leave').click()")
                        report['checks'].append({'name':'workspace_confirm_navigation','passed':bool(window.evaluate_js("activeView==='workspace' && !$('unsaved-dialog').open"))})
                        api._tools.files.stage({'nested/example.py':'value=2\n'})
                        review=api._tools.files.review()
                        window.evaluate_js("renderWorkspaceReview("+json.dumps(review)+")")
                        report['checks'].append({'name':'workspace_structured_diff_review','passed':bool(window.evaluate_js("$('workspace-review').textContent.includes('MODIFY') && $('workspace-review').textContent.includes('nested/example.py') && $('workspace-review').textContent.includes('+value=2')"))})
                        for width,height in ((1672,941),(1280,800),(1050,650)):
                            window.resize(width,height);time.sleep(.2)
                            fits=window.evaluate_js("(()=>{let r=$('route-view').getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})()")
                            report['checks'].append({'name':f'workspace_viewport_{width}x{height}','passed':bool(fits)})
                        window.evaluate_js("$('file-path').value='nested/example.py';$('file-content').value='original';rememberForm();const originalEditorKey=workspaceEditorKey();$('file-content').value='new unsaved edit';currentJob={id:'native-late-read',name:'preview_file',view:'workspace',editorKey:originalEditorKey};handledJob=null;patchState({...snapshot,busy:false,job:{id:'native-late-read',state:'finished',result:{ok:true,message:'Read finished',data:'old file contents'}}})")
                        report['checks'].append({'name':'workspace_late_read_preserves_edits','passed':bool(window.evaluate_js("$('file-content').value==='new unsaved edit'"))})
                        window.evaluate_js("$('file-content').dispatchEvent(new Event('input',{bubbles:true}));view('coding');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                        report['checks'].append({'name':'workspace_escape_keeps_edits','passed':bool(window.evaluate_js("activeView==='workspace' && !$('unsaved-dialog').open && $('file-content').value==='new unsaved edit'"))})
                        (api._workspace.root/'comma,name.py').write_text('pass\n')
                        for number in range(9):(api._workspace.root/f'context{number}.py').write_text('pass\n')
                        files=api._tools.execute('list_files',{}).data
                        window.evaluate_js("view('workspace',true);workspaceSelected.clear();renderFiles("+json.dumps(files)+");$('file-search').value='context';workspaceTree();[...$('files-list').querySelectorAll('input')].forEach(e=>e.click())")
                        report['checks'].append({'name':'workspace_context_limit_eight','passed':bool(window.evaluate_js("workspaceSelected.size===8 && $('files-list').querySelectorAll('input:checked').length===8"))})
                        window.evaluate_js("workspaceSelected.clear();$('file-search').value='comma,name';workspaceTree();$('files-list').querySelector('input').click();$('context-to-coding').click()")
                        report['checks'].append({'name':'workspace_comma_filename_context','passed':window.evaluate_js("JSON.stringify(paths('code-paths'))")==json.dumps(['comma,name.py'],separators=(',',':'))})
                        window.evaluate_js("view('settings',true);$('research-enabled').checked=!$('research-enabled').checked;$('research-enabled').dispatchEvent(new Event('change',{bubbles:true}));$('lm-temperature').value='0.3';document.querySelector('[data-action=save-model-options]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api._config['lm_studio']['temperature']!=.3:time.sleep(.1)
                        time.sleep(.7)
                        report['checks'].append({'name':'workspace_partial_settings_save_preserves_other_dirty_fields','passed':bool(window.evaluate_js("hasUnsavedForm()")) and api._config['lm_studio']['temperature']==.3})
                        window.evaluate_js("view('chat',true);currentJob=null;handledJob=null;const fastResult={...snapshot,busy:false,job:{id:'native-fast-completion',state:'finished',result:{ok:true,message:'Fast result delivered',data:null}}};patchState(fastResult);const fastBody=addMessage('assistant','Waiting');currentJob={id:'native-fast-completion',name:'preview_file',view:'chat',body:fastBody};patchState(fastResult)")
                        report['checks'].append({'name':'validation_fast_completion_not_lost','passed':bool(window.evaluate_js("$('conversation').textContent.includes('Fast result delivered') && currentJob===null"))})
                        from datetime import datetime,timedelta,timezone
                        import hashlib,uuid
                        entry=api._tools.memory.save('note','Native memory','Original project knowledge')
                        with api._tools.memory.connection() as db:db.execute('UPDATE entries SET updated=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=45)).isoformat(),entry['id']))
                        window.evaluate_js("view('memory',true);document.querySelector('[data-action=list-memory]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('memory-list').textContent.includes('Native memory')"):break
                        report['checks'].append({'name':'knowledge_aged_memory_warning_native','passed':bool(window.evaluate_js("$('memory-list').textContent.includes('at least 30 days old')"))})
                        window.evaluate_js("[...$('memory-list').querySelectorAll('button')].find(b=>b.textContent==='Edit reviewed entry').click();$('memory-body').value='Updated project knowledge';$('memory-body').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-action=save-memory]').click()")
                        deadline=time.monotonic()+4
                        while time.monotonic()<deadline:
                            approval=api.state()['approval']
                            if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                            time.sleep(.1)
                        window.evaluate_js("$('allow').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        time.sleep(.7)
                        saved=api._tools.memory.get(entry['id'])
                        report['checks'].append({'name':'knowledge_revision_edit_save_native','passed':saved['revision']==2 and saved['body']=='Updated project knowledge'})
                        window.evaluate_js("[...$('memory-list').querySelectorAll('button')].find(b=>b.textContent==='Edit reviewed entry').click();document.querySelector('[data-action=save-memory]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        time.sleep(.7)
                        report['checks'].append({'name':'knowledge_stale_memory_edit_native','passed':api._tools.memory.get(entry['id'])['revision']==2 and api.state()['approval'] is None and 'changed since review' in api.state()['job']['result']['message']})
                        api.save_settings({'project_memory':{'use_context':True}})
                        window.evaluate_js("view('memory',true);$('memory-context-query').value='Native memory';document.querySelector('[data-action=memory-context]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('memory-context-preview').textContent.includes('Updated project knowledge')"):break
                        report['checks'].append({'name':'knowledge_memory_context_preview_native','passed':bool(window.evaluate_js("$('memory-context-preview').textContent.includes('Updated project knowledge')")) and api.model_context()['data'] is None})
                        api.save_settings({'lm_studio':{'enabled':False}})
                        text='Cached public research reference.'
                        source=api._tools.research.store({'id':uuid.uuid4().hex,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'title':'Native research source','url':'https://example.com/reference','retrieved_at':(datetime.now(timezone.utc)-timedelta(days=45)).isoformat(),'warnings':[]})
                        window.evaluate_js("view('research',true);document.querySelector('[data-action=list-sources]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('source-list').textContent.includes('Native research source')"):break
                        window.evaluate_js("$('source-list').querySelector('input[type=checkbox]').click();$('research-question').value='What does the reference state?';document.querySelector('[data-action=research-context]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and not window.evaluate_js("researchPreview!==null"):time.sleep(.1)
                        report['checks'].append({'name':'knowledge_research_context_preview_native','passed':bool(window.evaluate_js("$('research-context-preview').textContent.includes('Cached public research reference') && $('research-context-preview').textContent.includes('at least 30 days old')"))})
                        path=api._tools.research.path(source['id']);value=json.loads(path.read_text());value['title']='Changed source title';path.write_text(json.dumps(value))
                        window.evaluate_js("document.querySelector('[data-action=research-brief]').click()")
                        deadline=time.monotonic()+4
                        while time.monotonic()<deadline:
                            approval=api.state()['approval']
                            if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                            time.sleep(.1)
                        window.evaluate_js("$('allow').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        time.sleep(.7)
                        report['checks'].append({'name':'knowledge_stale_research_preview_native','passed':not api.state()['job']['result']['ok'] and 'changed since preview' in api.state()['job']['result']['message']})
                        window.evaluate_js("document.querySelector('[data-action=research-context]').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('research-context-preview').textContent.includes('Changed source title')"):break
                        window.evaluate_js("document.querySelector('[data-action=research-brief]').click()")
                        deadline=time.monotonic()+4
                        while time.monotonic()<deadline:
                            approval=api.state()['approval']
                            if approval and window.evaluate_js("pendingId==="+json.dumps(approval['id'])):break
                            time.sleep(.1)
                        window.evaluate_js("$('allow').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline and api.state()['busy']:time.sleep(.1)
                        time.sleep(.7)
                        report['checks'].append({'name':'knowledge_source_linked_draft_native','passed':bool(window.evaluate_js("$('research-draft').textContent.includes('Cached public research reference') && $('research-draft').querySelectorAll('button').length>=2"))})
                        window.evaluate_js("$('research-draft').querySelector('button').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('cached-source-detail').textContent.includes('https://example.com/reference')"):break
                        report['checks'].append({'name':'knowledge_citation_opens_cached_source_native','passed':bool(window.evaluate_js("$('cached-source-detail').textContent.includes('https://example.com/reference') && $('cached-source-detail').textContent.includes('SHA-256')"))})
                        window.evaluate_js("view('tools',true);$('desktop-options').click()")
                        report['checks'].append({'name':'desktop_options_modal_focus','passed':bool(window.evaluate_js("$('desktop-dialog').open && document.activeElement.id==='desktop-layout'"))})
                        window.evaluate_js("$('desktop-layout').value='large';$('desktop-contrast').checked=true;$('desktop-motion').checked=true;$('desktop-save').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("$('desktop-save-status').textContent.includes('saved.')"):break
                        report['checks'].append({'name':'desktop_preferences_saved_native','passed':api.desktop_preferences()=={'layout':'large','contrast':True,'reduce_motion':True}})
                        report['checks'].append({'name':'desktop_accessibility_styles_native','passed':bool(window.evaluate_js("document.documentElement.classList.contains('strong-contrast') && document.documentElement.classList.contains('reduced-motion') && getComputedStyle($('route-body')).backgroundColor==='rgb(11, 9, 17)'"))})
                        window.evaluate_js("$('desktop-close').click()")
                        deadline=time.monotonic()+1
                        while time.monotonic()<deadline and not window.evaluate_js("!$('desktop-dialog').open && document.activeElement.id==='desktop-options'"):time.sleep(.05)
                        report['checks'].append({'name':'desktop_dialog_returns_focus','passed':bool(window.evaluate_js("!$('desktop-dialog').open && document.activeElement.id==='desktop-options'"))})
                        for width,height in [(1050,650),(1280,800),(1920,1080)]:
                            window.resize(width,height);time.sleep(.2)
                            result=window.evaluate_js("(()=>{scaleUI();const r=stage.getBoundingClientRect();return r.width>=2090-1 && document.documentElement.scrollWidth>=r.width-1 && document.documentElement.scrollHeight>=r.height-1;})()")
                            report['checks'].append({'name':f'desktop_large_scroll_extent_{width}','passed':bool(result)})
                        window.evaluate_js("view('memory',true)")
                        report['checks'].append({'name':'desktop_route_keyboard_focus','passed':bool(window.evaluate_js("document.activeElement.id==='route-title' && $('chat-view').getAttribute('aria-hidden')==='true' && [...$('chat-view').querySelectorAll('button,input,textarea,select')].every(e=>e.tabIndex===-1)"))})
                        window.evaluate_js("$('memory-title').value='Unsaved keyboard draft';$('memory-title').dispatchEvent(new Event('input',{bubbles:true}));document.dispatchEvent(new KeyboardEvent('keydown',{key:'1',altKey:true,bubbles:true,cancelable:true}))")
                        report['checks'].append({'name':'desktop_shortcut_guards_unsaved','passed':bool(window.evaluate_js("$('unsaved-dialog').open && activeView==='memory' && $('memory-title').value==='Unsaved keyboard draft'"))})
                        window.evaluate_js("$('unsaved-stay').click();rememberForm()")
                        window.evaluate_js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'1',altKey:true,bubbles:true,cancelable:true}))")
                        report['checks'].append({'name':'desktop_keyboard_route_restores_chat','passed':bool(window.evaluate_js("activeView==='chat' && document.activeElement.id==='prompt' && $('prompt').tabIndex===0"))})
                        window.evaluate_js("$('desktop-options').click();$('desktop-reset').click()")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if api.desktop_preferences()['layout']=='fit':break
                        time.sleep(.2)
                        window.evaluate_js("$('desktop-close').click();view('tools',true)")
                        report['checks'].append({'name':'desktop_reset_defaults_native','passed':bool(window.evaluate_js("document.documentElement.dataset.layout==='fit' && !document.documentElement.classList.contains('strong-contrast')"))})
                        window.evaluate_js("$('desktop-options').click();patchState({...snapshot,approval:{id:'accessibility-test',action:'test_permission',context:{}}})")
                        report['checks'].append({'name':'desktop_approval_keeps_priority','passed':bool(window.evaluate_js("!$('desktop-dialog').open && $('approval').open && document.activeElement.id==='deny'"))})
                        window.evaluate_js("patchState({...snapshot,approval:null})")
                        window.evaluate_js("view('tools',true)")
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            time.sleep(.1)
                            if window.evaluate_js("document.querySelectorAll('#platform-features article').length===12"):break
                        report['checks'].append({'name':'platform_catalog_native','passed':bool(window.evaluate_js("document.querySelectorAll('#platform-features article').length===12 && $('route-title').textContent.includes('2.0')"))})
                        report['checks'].append({'name':'platform_session_matches_native','passed':bool(window.evaluate_js("$('platform-status').textContent.includes('2.0.0') && $('platform-status').textContent.includes('offline tools available') && $('platform-status').textContent.includes('Idle')"))})
                        before=api.state()['job']
                        window.evaluate_js("view('tools',true)")
                        time.sleep(.3)
                        report['checks'].append({'name':'platform_opening_is_passive_native','passed':api.state()['job']==before and api.state()['approval'] is None})
                        window.evaluate_js("document.querySelector('.platform-workflow button').click()")
                        report['checks'].append({'name':'platform_workflow_opens_workspace_native','passed':bool(window.evaluate_js("activeView==='workspace' && document.activeElement.id==='route-title'"))})
                        window.evaluate_js("view('tools',true);$('platform-guide').click()")
                        report['checks'].append({'name':'platform_guide_opens_native','passed':bool(window.evaluate_js("!$('guide-panel').hidden"))})
                        window.evaluate_js("closeGuide();view('tools',true);$('advanced-name').value='retrieve_memory';$('advanced-name').dispatchEvent(new Event('change',{bubbles:true}));view('workspace')")
                        report['checks'].append({'name':'platform_advanced_unsaved_guard_native','passed':bool(window.evaluate_js("$('unsaved-dialog').open && activeView==='tools'"))})
                        window.evaluate_js("$('unsaved-stay').click()")
                        window.evaluate_js("view('chat',true);scaleUI()")
                        report['checks'].append({'name':'ui_help_controls_inside_sidebar','passed':bool(window.evaluate_js("(()=>{const b=$('desktop-options').getBoundingClientRect(),g=$('guide-button').getBoundingClientRect(),stageRect=stage.getBoundingClientRect();return $('stage').contains($('desktop-options')) && b.top>g.bottom && b.left>=stageRect.left && b.right<=stageRect.left+220*(stageRect.width/1672);})()"))})
                        report['checks'].append({'name':'ui_guide_search_do_not_overlap','passed':bool(window.evaluate_js("(()=>{const a=$('guide-button').getBoundingClientRect(),b=$('search').getBoundingClientRect();return a.right<=b.left||a.left>=b.right||a.bottom<=b.top||a.top>=b.bottom;})()"))})
                        report['checks'].append({'name':'ui_mode_labels_integrated','passed':bool(window.evaluate_js("document.querySelectorAll('.mode-copy strong').length===5 && document.querySelectorAll('.mode-copy small').length===5 && !document.querySelector('.mode-subtitle')"))})
                        frame=window.evaluate_js("(()=>{patchState({...snapshot,native_window_frame:true});const okay=[...document.querySelectorAll('[data-window]')].every(e=>getComputedStyle(e).display==='none') && getComputedStyle(document.querySelector('.native-window-version')).display==='flex';patchState({...snapshot,native_window_frame:false});return okay;})()")
                        report['checks'].append({'name':'windows_native_frame_avoids_duplicate_controls','passed':bool(frame)})
                        window.resize(800,500);time.sleep(.3)
                        report['checks'].append({'name':'smaller_800_by_500_window_fits','passed':bool(window.evaluate_js("(()=>{scaleUI();const r=stage.getBoundingClientRect();return innerWidth<=820 && innerHeight<=520 && r.left>=-1 && r.top>=-1 && r.right<=innerWidth+1 && r.bottom<=innerHeight+1;})()"))})
                        report['checks'].append({'name':'chat_single_model_selector','passed':bool(window.evaluate_js("document.querySelectorAll('.model-select').length===1 && !document.querySelector('.composer-model')"))})
                        report['checks'].append({'name':'chat_compact_send_label','passed':bool(window.evaluate_js("$('send').textContent==='Send' && parseFloat(getComputedStyle($('send')).height)<=36 && !$('#send svg')".replace("!$('#send svg')","!document.querySelector('#send svg')")))})
                        report['checks'].append({'name':'chat_coherent_navigation_and_stat_surfaces','passed':bool(window.evaluate_js("document.querySelectorAll('nav[aria-label=\"Main navigation\"] button svg').length===6 && document.querySelectorAll('.dashboard-stat').length===6 && [...document.querySelectorAll('.dashboard-stat>div')].every(e=>getComputedStyle(e).backgroundColor==='rgba(0, 0, 0, 0)')"))})
                        report['display_metrics']=window.evaluate_js("({device_pixel_ratio:devicePixelRatio,screen_width:screen.width,screen_height:screen.height})")

                    except Exception as exc:
                        report['error']=repr(exc)
                    finally:
                        api._shutdown();window.destroy()
                window.events.loaded+=check
                timer=threading.Timer(75,window.destroy)
                timer.daemon=True
                timer.start()
                return window
            with patch.object(desktop,'DesktopAPI',return_value=api),patch.object(webview,'create_window',side_effect=create):
                desktop.run_desktop()
            if report['checks'] and all(row['passed'] for row in report['checks']) and 'error' not in report:
                report['status']='passed'
    except Exception as exc:
        report['error']=repr(exc)
    Path(options.report).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
