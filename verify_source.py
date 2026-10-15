"""Source verification with an explicit runtime gate before application imports."""
from pathlib import Path
import os
import unittest
from runtime_version import require_runtime

def main():
    try:
        result = require_runtime()
    except RuntimeError as exc:
        print('Source verification stopped: ' + str(exc))
        return 2
    root = Path(__file__).resolve().parent
    print('Selected Python: ' + result['python'], flush=True)
    print('Interpreter: ' + result['executable'], flush=True)
    os.chdir(str(root))
    suite = unittest.defaultTestLoader.discover(str(root/'tests'), top_level_dir=str(root/'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
