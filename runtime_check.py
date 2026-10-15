"""Read-only startup report; no package installation or settings changes."""
from pathlib import Path
import json
import platform
import sys
from importlib.metadata import version,PackageNotFoundError


def main():
    root=__import__("purple_dragon_agent.config",fromlist=["APP_DIR"]).APP_DIR
    report={'platform':platform.platform(),'python':sys.version,'executable':sys.executable,'base_executable_exists':Path(getattr(sys,'_base_executable',sys.executable)).is_file(),'checks':[]}
    def check(name,callback):
        try:detail=callback();report['checks'].append({'name':name,'passed':True,'detail':detail})
        except Exception as exc:report['checks'].append({'name':name,'passed':False,'detail':str(exc)})
    check('webview_package',lambda:version('pywebview'))
    def settings():
        from purple_dragon_agent.config import normalize_config
        defaults=json.loads((root/'config/default_config.json').read_text())
        path=root/'config/user_config.json'
        saved=json.loads(path.read_text()) if path.exists() else {}
        return {'version':normalize_config(saved,defaults)['version'],'user_settings_present':path.exists()}
    check('settings_validation',settings)
    def assets():
        expected=('frontend/index.html','frontend/style.css','frontend/app.js','frontend/reference-ui.png')
        missing=[name for name in expected if not (root/name).is_file()]
        if missing:raise ValueError('Missing bundled UI files: '+', '.join(missing))
        return 'All bundled UI files present.'
    check('frontend_assets',assets)
    if sys.platform=='win32':
        def clr():
            import clr
            return 'Python/.NET bridge imported.'
        check('windows_dotnet_bridge',clr)
    state=root/'logs/startup-error.log'
    try:
        with state.open('rb') as log:
            log.seek(max(0,state.stat().st_size-8000))
            report['startup_error']=log.read(8000).decode('utf-8',errors='replace')
    except FileNotFoundError:
        report['startup_error']=None
    except OSError as exc:
        report['startup_error']='Startup log could not be read: '+str(exc)
    from purple_dragon_agent.release_trust import trust_report
    report['release_trust']=trust_report(root)
    report['status']='passed' if all(x['passed'] for x in report['checks']) and report['base_executable_exists'] else 'failed'
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
