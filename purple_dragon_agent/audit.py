from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import threading

class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, event: str, **details) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tail(self, limit: int = 250) -> list[dict]:
        """Read recent valid records without loading a growing log into memory."""
        if type(limit) is not int or limit < 0 or limit > 1000:
            raise ValueError('Audit tail limit must be between 0 and 1000.')
        if not limit or not self.path.exists():
            return []
        chunks = []
        size = 0
        with self._lock, self.path.open('rb') as stream:
            stream.seek(0, 2)
            position = stream.tell()
            while position and size < 2_000_000:
                amount = min(position, 65_536, 2_000_000 - size)
                position -= amount
                stream.seek(position)
                chunks.append(stream.read(amount))
                size += amount
                # Allow corrupt/scalar rows without starving the requested valid tail.
                if b''.join(reversed(chunks)).count(b'\n') > limit * 4 + 32:
                    break
        lines = b''.join(reversed(chunks)).splitlines()
        if position:
            lines = lines[1:]  # The first row may be a partial record.
        records = []
        for line in reversed(lines):
            try:
                entry = json.loads(line.decode('utf-8'))
            except (ValueError, UnicodeError, RecursionError):
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get('event'), str) or not isinstance(entry.get('timestamp'), str):
                continue
            records.append(entry)
            if len(records) == limit:
                break
        return list(reversed(records))
