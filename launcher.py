"""Console and pythonw entry point with persistent startup diagnostics."""
from pathlib import Path
import sys
import traceback


def main():
    error_log = Path(__file__).resolve().parent / 'logs' / 'startup-error.log'
    try:
        from runtime_version import require_runtime
        require_runtime()
        from purple_dragon_agent.desktop import run_desktop
        run_desktop()
        try:
            error_log.unlink(missing_ok=True)
        except OSError:
            pass
        return 0
    except Exception:
        details = traceback.format_exc()
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            error_log.write_text(details, encoding='utf-8')
            message = f'Purple Dragon AI Agent could not start.\n\nDetails saved to:\n{error_log}\n\nRun Diagnose-Startup.bat to view the error.\nIf settings are damaged, close the app and run Recover-Settings.bat.'
        except OSError:
            message = f'Purple Dragon AI Agent could not start:\n\n{details}'
        if sys.stderr is not None:
            print(details, file=sys.stderr)
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, 'Purple Dragon AI — Startup Error', 0x10)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
