"""Pure permissive evaluation for batch start (phase 6A).

`evaluate_permissives(state)` has no I/O: callers (the route module) gather live
process lists, a ComfyUI probe result, host memory/swap readings and config
validity, then pass them in as a plain dict. Each permissive names the action an
operator must take when it blocks; `MAIN_SILO` is a warning only (`blocking:
False`) per the phase-6 spec, the rest block the start when `ok` is False.
"""

import time
from typing import Dict, List, Optional

TRAINING_SCRIPT_MARKER = "train_network"


def evaluate_permissives(state: Dict) -> List[Dict]:
    """state keys (all optional, missing/None means "unknown"):
      live_batch_count: int, comfy_ok: Optional[bool], training_pids: list,
      mem_low: Optional[bool], swap_thrash: Optional[bool],
      config_valid: Optional[bool], main_silo: bool, lora_missing: list,
      gpu_lease: Optional[dict] (plant_gpu_lease.current(), None means free).
    Unknown comfy/mem/config readings fail safe (block start, not silently pass)."""
    live_batch_count = state.get("live_batch_count") or 0
    comfy_ok = state.get("comfy_ok")
    training_pids = state.get("training_pids") or []
    mem_low = state.get("mem_low")
    swap_thrash = state.get("swap_thrash")
    config_valid = state.get("config_valid")
    main_silo = bool(state.get("main_silo"))
    lora_missing = state.get("lora_missing") or []
    gpu_lease = state.get("gpu_lease")

    out = [
        # checked before the lease is acquired (this call never holds it itself), so
        # any valid lease at all means someone else has the GPU right now (plan Bước 1)
        {"code": "GPU_FREE", "ok": gpu_lease is None, "blocking": True,
         "message": "GPU rảnh" if gpu_lease is None else
         f"GPU đang được {gpu_lease.get('owner')} giữ (mục đích: {gpu_lease.get('purpose') or '?'}) "
         f"từ {time.strftime('%H:%M:%S', time.localtime(gpu_lease.get('ts', 0)))}"},
        {"code": "NO_LIVE_BATCH", "ok": live_batch_count == 0, "blocking": True,
         "message": "đã có batch đang chạy (P-601 chỉ nhận một batch tại một thời điểm)"
         if live_batch_count else "không có batch nào đang chạy"},
        {"code": "COMFY_UP", "ok": comfy_ok is True, "blocking": True,
         "message": "ComfyUI đang chạy" if comfy_ok is True
         else ("ComfyUI chưa trả lời, không thể khởi chạy batch" if comfy_ok is False
               else "trạng thái ComfyUI chưa rõ, chặn để an toàn")},
        {"code": "NO_TRAINING", "ok": not training_pids, "blocking": True,
         "message": f"có tiến trình train LoRA đang chạy (pid {', '.join(map(str, training_pids))}), "
                    "tranh GPU với batch" if training_pids else "không có tiến trình train LoRA nào"},
        {"code": "MEM_OK", "ok": mem_low is False and swap_thrash is False, "blocking": True,
         "message": _mem_message(mem_low, swap_thrash)},
        {"code": "CONFIG_VALID", "ok": config_valid is True, "blocking": True,
         "message": "config đọc được, có paths/output_base_dir" if config_valid is True
         else "config không đọc được hoặc thiếu paths.output_base_dir"},
        {"code": "LORA_PRESENT", "ok": not lora_missing, "blocking": True,
         "message": "tất cả defect trọng số > 0 đều có LoRA + mask generator" if not lora_missing
         else f"thiếu LoRA hoặc mask generator cho: {', '.join(lora_missing)}"},
        # each HMI start writes to its own folder output/synthetic/<YYYY-MM-DD_HHMMSS>_<config>/
        # (plant_batch_run_dirs), so the main silo is never mixed: informational only
        {"code": "RUN_DIR", "ok": True, "blocking": False,
         "message": "mỗi lần chạy ghi vào thư mục riêng output/synthetic/<ngày_giờ>_<tên config>/"},
    ]
    return out


def _mem_message(mem_low: Optional[bool], swap_thrash: Optional[bool]) -> str:
    if mem_low is None or swap_thrash is None:
        return "RAM/swap chưa đọc được, chặn để an toàn"
    if mem_low:
        return "RAM khả dụng quá thấp (MEM_LOW)"
    if swap_thrash:
        return "swap đang thrash (SWAP_THRASH)"
    return "RAM/swap bình thường"


def blocking_failures(permissives: List[Dict]) -> List[Dict]:
    """Permissives that block the start right now (blocking and not ok)."""
    return [p for p in permissives if p["blocking"] and not p["ok"]]
