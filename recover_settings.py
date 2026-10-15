"""Offline settings recovery; independent of desktop configuration loading."""
import argparse,json
from pathlib import Path
from purple_dragon_agent.recovery import RecoveryCenter
from purple_dragon_agent.reliability import RuntimeLease

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-release',action='store_true');parser.add_argument('--list',action='store_true');parser.add_argument('--backup-id');parser.add_argument('--reset',action='store_true');args=parser.parse_args()
    root=__import__("purple_dragon_agent.config",fromlist=["APP_DIR"]).APP_DIR
    try:
        if args.check_release:
            from purple_dragon_agent.recovery import release_readiness
            report=release_readiness(root);print(json.dumps(report,indent=2));return 0 if report['status']=='candidate_checks_passed' else 1
        with RuntimeLease(root):
            center=RecoveryCenter(root)
            if args.list:print(json.dumps(center.list(),indent=2));return 0
            backup=args.backup_id
            reset=args.reset
            if not backup and not reset:
                print(json.dumps(center.list(),indent=2));selection=input('Backup ID, or RESET to restore default policies while retaining a readable workspace setting: ').strip()
                if selection=='RESET':reset=True
                else:backup=selection
            try:current=json.loads(center.current_bytes())
            except (ValueError,OSError):current=None
            if not isinstance(current,dict):current=None
            preview=center.preview(backup,current,reset)
            print(json.dumps(preview,indent=2))
            if input('Type RESTORE to apply this exact settings review: ').strip()!='RESTORE':print('No changes made.');return 1
            result=center.apply(preview['id'],current);print(result['message']);return 0
    except Exception as exc:print('Recovery stopped: '+str(exc));return 1
if __name__=='__main__':raise SystemExit(main())
