"""Read-only status assembly for the realism loop job (plan Bước 1). Split out of
`plant_realism_routes.py` purely to keep that file under the 200-line guideline;
both change together. The loop itself runs under `systemd-run --user` as unit
`tdm-realism-<run_id>` (deterministic name, no in-memory table needed to find it
again after a tdm-backend restart).
"""
import subprocess
from pathlib import Path

from realism.runlog import RUNS_DIR, list_runs, read_events

from .plant_batch_process_ops import is_unit_active
from .plant_host_readers import find_batch_processes


def unit_for(run_id: str) -> str:
    """Deterministic from run_id alone: survives a tdm-backend restart between
    launching the loop and later stopping it."""
    return "tdm-realism-" + run_id


def alive(pid, marker):
    try:
        return marker in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="ignore")
    except OSError:
        return False


def log_tail(rid, n=6):
    """Before the loop has written its own events.jsonl (crash at import time, bad
    venv, ...), fall back to the unit's own journal (stdout/stderr no longer go to
    a plain log file once the loop runs under systemd-run)."""
    try:
        out = subprocess.run(["journalctl", "--user", "-u", unit_for(rid), "--no-pager", "-n", str(n), "-o", "cat"],
                              capture_output=True, text=True, timeout=4)
        return " | ".join(out.stdout.strip().splitlines()) or None
    except (OSError, subprocess.SubprocessError):
        return None


def job():
    """Lượt vòng lặp gần nhất: trạng thái suy từ nhật ký (done/error) và pid còn sống; tiến độ từ bản ghi cuối."""
    runs = [r for r in list_runs() if r.startswith("loop-") and "-eval-" not in r]
    if not runs:
        return {"state": "idle"}
    rid, ev = runs[-1], read_events(runs[-1])
    if not ev:                                               # chưa ghi được dòng nào: đang khởi động hay đã chết ngay
        if is_unit_active(unit_for(rid)):
            return {"run_id": rid, "state": "running", "stage": "khởi động"}
        return {"run_id": rid, "state": "failed", "error": f"vòng lặp dừng khi khởi động: {log_tail(rid) or 'không có nhật ký'}"}
    cfg = next((e for e in ev if e["kind"] == "config"), {})
    last = {e["kind"]: e for e in ev}
    err = last.get("error")
    state = "done" if "done" in last else "stopped" if err and err.get("stopped") else "failed" if err else \
        "running" if alive(ev[0]["pid"], "realism.loop") else "dead"
    stage = next((e for e in reversed(ev) if e["kind"] == "stage"), {})
    item, gen, child = last.get("item", {}), last.get("gen_progress", {}), last.get("child", {})
    return {"run_id": rid, "state": state, "action": cfg.get("action"), "started": ev[0]["ts"],
            "n_per_type": cfg.get("n_per_type"), "types": cfg.get("types"), "max_iter": cfg.get("max_iter"),
            "stage": stage.get("stage"), "stage_state": stage.get("state"), "why": stage.get("why"),
            "reason": stage.get("reason"), "eval_done": item.get("done"), "eval_total": item.get("total"),
            "gen_done": gen.get("done"), "gen_total": gen.get("total"), "gen_iter": gen.get("iter"),
            "child_pid": child.get("pid"), "error": err.get("message") if err else None, "last_ts": ev[-1]["ts"]}


def batch_running():
    """Có đợt sinh nào đang chạy (GPU bận) không. Kiểm không được thì coi như đang bận (an toàn)."""
    try:
        return bool(find_batch_processes())
    except Exception:
        return True
