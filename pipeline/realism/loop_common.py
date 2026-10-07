"""Hằng số, đường dẫn, ngoại lệ, lịch sử dùng chung giữa các mô-đun vòng lặp (loop.py, loop_generate.py,
loop_gate.py): tách ra để mỗi tệp dưới 200 dòng, không đổi hành vi so với loop.py một tệp trước đây."""
import json
from pathlib import Path

from . import knobs

PIPELINE = Path(__file__).resolve().parents[1]
STATE = Path(__file__).resolve().parent / "state"
HISTORY, STOP = STATE / "iterations.jsonl", STATE / "stop.flag"
BASELINE = PIPELINE.parent / "output" / "synthetic"
LOOP_OUT = PIPELINE.parent / "output" / "realism-loop"
BATCH_MAIN = PIPELINE / "batch_manager" / "batch-production-main.py"
DEFAULT_TYPES = ["crack", "porosity", "lack_of_penetration", "lack_of_fusion"]


class Stopped(Exception):
    pass


class GpuBusy(Exception):
    """GPU lease refused: another owner (an HMI batch or a different loop run) holds
    it. Like `Stopped`, a controlled abort, not a bug: caller logs the reason and
    exits cleanly instead of re-raising."""
    pass


def history():
    try:
        return [json.loads(x) for x in HISTORY.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def candidate():
    return knobs.values(knobs.resolve("candidate", use_env=False))


def other_batch_running(own_owner=None):
    """GPU bận vì lý do khác với phiên vòng lặp hiện tại: có batch do HMI khởi chạy
    đang sống, HOẶC phiếu GPU (plant_gpu_lease) đang thuộc một owner khác (phòng khi
    một tiến trình ngoài find_batch_processes() cũng giữ phiếu). `own_owner` là owner
    của chính phiên này nên không tự coi phiếu của mình là "bên khác"."""
    try:
        from plant_hmi import plant_host_readers as host
        if host.find_batch_processes():
            return True
    except Exception:
        return True                                            # không kiểm được thì coi như đang bận (an toàn)
    try:
        from plant_hmi import plant_gpu_lease as gpu_lease
        held = gpu_lease.current()
        return bool(held) and held.get("owner") != own_owner
    except Exception:
        return False
