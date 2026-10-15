from __future__ import annotations
from pathlib import Path
import os

IGNORED_DIRECTORIES = {'conversation-data', '.git', '.svn', 'node_modules', '__pycache__', '.venv', 'venv', 'logs', '.build-venv'}

class WorkspaceViolation(PermissionError):
    pass

class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.security_options = None
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str | Path) -> Path:
        original = self.root / relative
        for path in (original, *original.parents):
            if path == self.root:
                break
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                raise WorkspaceViolation('Linked workspace paths are unavailable.')
        candidate = original.resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceViolation(f"Path escapes workspace: {relative}") from exc
        if self.security_options is not None:
            from .security import protected_path
            if protected_path(candidate.relative_to(self.root).as_posix(), self.security_options):
                raise WorkspaceViolation("File is protected by Security Center scope.")
        if candidate.is_file() and candidate.stat().st_nlink > 1:
            raise WorkspaceViolation("Linked workspace files are unavailable.")
        return candidate

    def list_files(self, limit: int = 1000) -> list[str]:
        if type(limit) is not int or not 0 <= limit <= 1000:
            raise ValueError('File listing limit must be between 0 and 1000.')
        if not limit:
            return []
        results = []
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRECTORIES
                             and not (Path(directory) / name).is_symlink()
                             and not getattr(Path(directory) / name, 'is_junction', lambda: False)())
            for name in sorted(names):
                relative = (Path(directory) / name).relative_to(self.root)
                try:
                    file = self.resolve(relative)
                    if not file.is_file():
                        continue
                except (WorkspaceViolation, OSError):
                    continue
                results.append(relative.as_posix())
                if len(results) >= limit:
                    return sorted(results)
        return sorted(results)

    def read_text(self, relative: str, max_bytes: int = 1_000_000) -> str:
        path = self.resolve(relative)
        with path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"File is larger than {max_bytes} bytes.")
        return data.decode("utf-8", errors="replace")

    def write_text(self, relative: str, content: str) -> Path:
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        # The workspace API preserves the caller's bytes on every OS.
        # Default Windows text translation would silently turn LF into CRLF.
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        return path
