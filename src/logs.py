from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class Status(str, Enum):
    PENDING = "PENDING"
    CONTACT_FOUND = "CONTACT_FOUND"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


TERMINAL_STATUSES = {Status.SENT, Status.SKIPPED}


class LogEntry(BaseModel):
    name: str
    phone: str
    timestamp: datetime
    message: str
    status: Status
    reason: str | None = None


class RunLog:
    """Append-only JSON Lines log of per-contact processing results."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def already_processed_phones(self) -> set[str]:
        processed: set[str] = set()
        for entry in self.read_all():
            if entry.status in TERMINAL_STATUSES:
                processed.add(entry.phone)
        return processed

    def read_all(self) -> list[LogEntry]:
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(LogEntry.model_validate_json(line))
        return entries

    def record(
        self,
        name: str,
        phone: str,
        message: str,
        status: Status,
        reason: str | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            name=name,
            phone=phone,
            timestamp=datetime.now(timezone.utc),
            message=message,
            status=status,
            reason=reason,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry
