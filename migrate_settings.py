"""Explicit settings-only upgrade; source files are never modified."""
import argparse
from pathlib import Path
import json
from purple_dragon_agent.reliability import import_previous_settings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous_folder',nargs='?')
    args=parser.parse_args()
    try:
        source=args.previous_folder or input('Previous Purple Dragon release folder: ').strip().strip('"')
        if not source:raise ValueError('No folder selected; no changes made.')
        result=import_previous_settings(source,Path(__file__).resolve().parent)
        print(json.dumps(result,indent=2));return 0
    except (ValueError,OSError,TypeError,RuntimeError) as exc:
        print(f'Upgrade stopped: {exc}');return 1

if __name__=='__main__':raise SystemExit(main())
