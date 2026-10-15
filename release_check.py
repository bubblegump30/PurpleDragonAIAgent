"""Read-only release candidate integrity and acceptance report."""
import json
import argparse
from pathlib import Path
from purple_dragon_agent.recovery import release_readiness

def main():
    from runtime_version import require_runtime
    require_runtime()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--trust',action='store_true');args=parser.parse_args()
    from purple_dragon_agent.release_trust import trust_report
    report=(trust_report if args.trust else release_readiness)(__import__("purple_dragon_agent.config",fromlist=["APP_DIR"]).APP_DIR)
    print(json.dumps(report,indent=2))
    return 0 if report.get('integrity',report)['status']=='candidate_checks_passed' else 1
if __name__=='__main__':raise SystemExit(main())
