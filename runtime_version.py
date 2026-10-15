"""Minimal version/AST preflight, usable before importing the application."""
import ast
import platform
import sys

MINIMUM = (3, 10)
REQUIRED_AST = ('MatchAs', 'MatchStar', 'MatchMapping')

def require_runtime(version=None, ast_module=ast):
    current = tuple(sys.version_info[:2]) if version is None else tuple(version[:2])
    if current < MINIMUM:
        raise RuntimeError('Python 3.10+ is required; selected %s.%s. Run Run-PurpleDragonAI.bat to prepare a compatible private environment.' % current)
    missing = [name for name in REQUIRED_AST if not hasattr(ast_module, name)]
    if missing:
        raise RuntimeError('The selected Python ast module is missing %s. Use a standard Python 3.10+ installation.' % ', '.join(missing))
    return {'python':platform.python_version(), 'executable':sys.executable}

def main():
    try:
        result = require_runtime()
    except RuntimeError as exc:
        print('Runtime check failed: ' + str(exc))
        return 2
    print('Selected Python: ' + result['python'])
    print('Interpreter: ' + result['executable'])
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
