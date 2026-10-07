"""Nhật ký một lượt của vòng độ thật: realism/state/runs/<run_id>/{events.jsonl, *.json}.

Mỗi dòng một os.write trên fd O_APPEND (dòng không vỡ khi nhiều luồng ghi); lỗi ghi bị nuốt, không bao giờ làm hỏng
việc đang chạy (luật R4 của skill software-plant-hmi). Loại bản ghi: config, stage, item, iteration, done, error.
"""
import json
import os
import time
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "state" / "runs"


class RunLog:
    def __init__(self, run_id):
        self.run_id = run_id
        self.dir = RUNS_DIR / run_id
        self._fd = None

    def emit(self, kind, **fields):
        try:
            if self._fd is None:
                self.dir.mkdir(parents=True, exist_ok=True)
                self._fd = os.open(self.dir / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            rec = {"ts": time.time(), "pid": os.getpid(), "run": self.run_id, "kind": kind, **fields}
            os.write(self._fd, (json.dumps(rec, ensure_ascii=False) + "\n").encode())
        except Exception:
            pass

    def write_json(self, name, obj):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / (name + ".tmp")
            tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.dir / name)
        except Exception:
            pass


def read_events(run_id):
    out = []
    try:
        with open(RUNS_DIR / run_id / "events.jsonl", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def read_json(run_id, name):
    try:
        return json.loads((RUNS_DIR / run_id / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_runs():
    if not RUNS_DIR.exists():
        return []
    return sorted((p.name for p in RUNS_DIR.iterdir() if p.is_dir()), key=lambda n: (RUNS_DIR / n).stat().st_mtime)
