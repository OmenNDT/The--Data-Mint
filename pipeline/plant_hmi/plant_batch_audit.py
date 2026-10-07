"""Append-only audit log for batch start/stop attempts (phase 6A), accepted or
refused alike. Same append-only JSONL pattern as `plant_setpoint_store.py`
(one `os.write` per line, code-anchored path, rule R6); no read-modify-write so
no lock is needed here.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

CONTROL_DIR = Path(__file__).resolve().parent / "control"  # code-anchored (rule R6)
AUDIT_PATH = CONTROL_DIR / "batch-audit.jsonl"


def append_audit(event: Dict) -> None:
    """Best-effort append; a logging failure must never fail the request that
    already started or stopped the real process (same trade-off as setpoints)."""
    try:
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        fd = os.open(AUDIT_PATH, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        logger.exception("plant batch control audit append failed: %s", event)


def read_audit(limit: int = 50) -> List[Dict]:
    """Newest-first audit entries, tolerant of corrupt/partial lines."""
    try:
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[Dict] = []
    for raw in reversed(lines):
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
        if len(out) >= limit:
            break
    return out
