"""Wait for parent process-group setup before running a fixed test module."""
import json
import os
import runpy
import sys


def main():
    request = json.loads(sys.stdin.readline(4096))
    module = request.get('module')
    args = request.get('args')
    if module not in {'unittest','pytest'} or not isinstance(args,list) or any(not isinstance(value,str) for value in args):
        raise ValueError('Invalid fixed test request.')
    sys.path.insert(0,os.getcwd())
    sys.argv = [module] + args
    runpy.run_module(module,run_name='__main__',alter_sys=True)


if __name__ == '__main__':
    main()
