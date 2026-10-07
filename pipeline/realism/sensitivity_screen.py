"""Bước 4 của plan `plans/261002-1430-realism-knob-sensitivity-screening/`: đo độ nhạy từng nhóm núm
(realism/sensitivity_groups.py) quanh điểm gốc (núm sản xuất hiện tại), trên bộ đề thi cố định.

    python3 -m realism.sensitivity_screen --run-id sens-<ts> [--n-per-type 20] [--groups g1,g2] [--pilot]

Lượt gốc sinh trên GPU (lưu kèm ảnh trước-làm-tối, REALISM_SAVE_PREDARKEN=1). Mỗi biến thể: nhóm
"replay" tính lại bằng CPU từ ảnh trước-làm-tối của lượt gốc (realism/predarken_replay.py), nhóm
"generate" sinh lại bằng GPU, chỉ cho các loại núm đó chạm tới. Mỗi biến thể đo rồi ghép cặp với lượt
gốc trên ca chung (realism/paired_stats.compare_paired) → hiệu ứng từng mục tiêu + C2ST.

--pilot: lượt gốc + mọi biến thể "replay" + controlnet_strength"+" (một biến thể "generate" để kiểm
replay có trùng điểm ảnh với lượt gốc không); không ghi bản PV sản xuất realism/state/sensitivity.json.

Xin phiếu GPU (plant_gpu_lease) bằng pid chính tiến trình này, giữ suốt phiên (gồm cả do_generate bên
trong), nhả trong finally. Tôn trọng state/stop.flag giữa và trong khi sinh (giết cả nhóm tiến trình,
như realism/loop_generate.py).
"""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import evaluate, knobs, predarken_replay, sensitivity_groups
from . import sensitivity_screen_effects as effects_mod
from . import sensitivity_screen_gen as gen
from .loop_common import GpuBusy, STATE, STOP, Stopped
from .runlog import RunLog


class _RunLogProxy(RunLog):
    """Kết quả đo (evaluate.run) ghi vào thư mục riêng của lượt đo; tiến độ báo chung vào nhật ký của
    phiên đo độ nhạy (cùng cách realism/loop.py tách RunLogProxy cho do_evaluate)."""

    def __init__(self, parent, run_id):
        super().__init__(run_id)
        self.parent = parent

    def emit(self, kind, **fields):
        self.parent.emit(kind, **fields)


def _self_check_replay(base_dir, base_knobs):
    """Replay với đúng núm gốc phải ra ảnh TRÙNG TỪNG ĐIỂM ẢNH với ảnh lượt gốc: nếu không, biến thể
    "replay" không dùng được để đo độ nhạy (mã làm tối lại đã lệch cách sinh gốc)."""
    base_dir, n, max_diff = Path(base_dir), 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        predarken_replay.replay(base_dir, tmp, base_knobs, sensitivity_groups.ALL_TYPES)
        tmp_dir = Path(tmp)
        for t in sensitivity_groups.ALL_TYPES:
            for p in sorted((tmp_dir / t).glob("*[0-9].png")):
                orig = base_dir / t / p.name
                if not orig.exists():
                    continue
                a = np.asarray(Image.open(p), dtype=np.int32)
                b = np.asarray(Image.open(orig), dtype=np.int32)
                max_diff = max(max_diff, int(np.max(np.abs(a - b))))
                n += 1
    return {"n": n, "max_diff": max_diff}


def _generate_base(log, run_id, base_dir, base_knobs, n):
    cfg_path, total, host = gen.build_config(run_id, "base", sensitivity_groups.ALL_TYPES, n, base_dir)
    log.emit("stage", stage="base", state="start", total=total, output=str(base_dir), comfyui=host)
    env = {"REALISM_KNOBS": json.dumps(base_knobs), "REALISM_SAVE_PREDARKEN": "1"}
    gen.run_batch_subprocess(cfg_path, base_dir, sensitivity_groups.ALL_TYPES, total, env, log, "generate-base")
    log.emit("stage", stage="base", state="end")


def _generate_variant(log, run_id, vid, var_dir, vknobs, types, n):
    slug = gen.sanitize(vid)
    cfg_path, total, host = gen.build_config(run_id, slug, types, n, var_dir)
    log.emit("stage", stage=vid, state="gen_start", total=total, output=str(var_dir), comfyui=host)
    env = {"REALISM_KNOBS": json.dumps(vknobs), "REALISM_SAVE_PREDARKEN": "1"}   # cho phép tính lại sau này
    gen.run_batch_subprocess(cfg_path, var_dir, types, total, env, log, f"generate-{slug}")
    log.emit("stage", stage=vid, state="gen_end")


def _write_production_copy(sensitivity):
    """Bản PV mới nhất, ghi đè atomically (tệp tạm + đổi tên); chỉ gọi khi chạy đủ, không pilot."""
    STATE.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(sensitivity, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE / "sensitivity.json")


def pick_variants(base_knobs, groups_filter, pilot):
    out = sensitivity_groups.variants(base_knobs)
    if groups_filter:
        out = [v for v in out if v[1] in groups_filter]
    if pilot:
        out = [v for v in out if sensitivity_groups.GROUPS[v[1]]["mode"] == "replay" or v[0] == "controlnet_strength+"]
    return out


def do_screen(run_id, n_per_type=20, groups_filter=None, pilot=False, log=None):
    """Chạy một phiên đo độ nhạy đầy đủ; trả về dict sensitivity (cũng ghi runs/<run_id>/sensitivity.json)."""
    log = log or RunLog(run_id)
    n = gen.clamp_n(n_per_type)
    if n != n_per_type:
        log.emit("stage", stage="screen", state="n_clamped", requested=n_per_type, used=n,
                 note="bộ đề thi cố định chỉ có per_type ca, kẹp n_per_type")
    base_knobs = knobs.values(knobs.resolve("production", use_env=False))
    variant_list = pick_variants(base_knobs, groups_filter, pilot)
    log.emit("config", run_id=run_id, n_per_type=n, groups=groups_filter, pilot=pilot, base_knobs=base_knobs,
             variants=[v[0] for v in variant_list])

    owner = f"realism-sensitivity:{run_id}"
    from plant_hmi import plant_gpu_lease as gpu_lease
    ok, holder = gpu_lease.acquire(owner, "đo độ nhạy từng núm", os.getpid())
    if not ok:
        who = (holder or {}).get("owner", "không rõ")
        raise GpuBusy(f"GPU đang được {who} giữ, không xin được phiếu")
    try:
        run_dir = gen.OUT_ROOT / run_id
        base_dir = run_dir / "base"
        _generate_base(log, run_id, base_dir, base_knobs, n)
        if STOP.exists():
            raise Stopped("dừng theo yêu cầu sau lượt gốc")

        replay_check = _self_check_replay(base_dir, base_knobs)
        if replay_check["n"] == 0:                        # không ảnh nào để so: không được coi là đạt (review M4)
            raise RuntimeError("lượt gốc không có ảnh trước-làm-tối nào, không kiểm được replay")
        if replay_check["max_diff"] != 0:
            raise RuntimeError(f"replay không trùng điểm ảnh với lượt gốc (lệch tối đa {replay_check['max_diff']}), "
                                "không dùng được để đo độ nhạy")

        base_eval_run = f"{run_id}-eval-base"
        base_result = evaluate.run(base_dir, base_eval_run, workers=16, log=_RunLogProxy(log, base_eval_run))

        total_variants = len(variant_list)
        variants_meta, effects, ok_count = [], {}, 0
        for i, (vid, group, sign, vknobs) in enumerate(variant_list, start=1):
            if STOP.exists():
                raise Stopped("dừng theo yêu cầu giữa các biến thể")
            mode, types = sensitivity_groups.GROUPS[group]["mode"], sensitivity_groups.GROUPS[group]["types"]
            log.emit("variant", id=vid, index=i, total=total_variants, mode=mode, state="start")
            try:
                var_dir = run_dir / vid
                if mode == "replay":
                    predarken_replay.replay(base_dir, var_dir, vknobs, types)
                else:
                    _generate_variant(log, run_id, vid, var_dir, vknobs, types, n)
                eval_run = f"{run_id}-eval-{gen.sanitize(vid)}"
                var_result = evaluate.run(var_dir, eval_run, workers=16, log=_RunLogProxy(log, eval_run))
                changed = {k: [base_knobs[k], vknobs[k]] for k in sensitivity_groups.GROUPS[group]["knobs"]
                           if vknobs[k] != base_knobs[k]}
                variants_meta.append({"id": vid, "group": group, "sign": sign, "mode": mode, "types": types,
                                       "knobs": vknobs, "changed": changed, "eval_run": eval_run})
                effects[vid] = effects_mod.assemble_effects(base_result, var_result, types)
                ok_count += 1
                log.emit("variant", id=vid, index=i, total=total_variants, mode=mode, state="end")
            except Stopped:
                raise
            except Exception as e:
                log.emit("variant", id=vid, index=i, total=total_variants, mode=mode, state="error")
                log.emit("error", variant=vid, message=f"{type(e).__name__}: {e}"[:300])
                continue

        sensitivity = {"run_id": run_id, "finished": True, "pilot": pilot, "n_per_type": n, "base_knobs": base_knobs,
                       "base_eval_run": base_eval_run, "variants": variants_meta, "effects": effects,
                       "replay_check": replay_check}
        log.write_json("sensitivity.json", sensitivity)
        if not pilot and variant_list and ok_count == len(variant_list):
            _write_production_copy(sensitivity)
        return sensitivity
    finally:
        gpu_lease.release(owner)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", default=time.strftime("sens-%Y%m%d-%H%M%S"))
    ap.add_argument("--n-per-type", type=int, default=20)
    ap.add_argument("--groups", default=None)
    ap.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    groups_filter = [g for g in a.groups.split(",") if g] if a.groups else None
    log = RunLog(a.run_id)
    STOP.unlink(missing_ok=True)
    try:
        do_screen(a.run_id, a.n_per_type, groups_filter, a.pilot, log=log)
        log.emit("done")
    except Stopped as e:
        log.emit("error", message=str(e), stopped=True)
    except GpuBusy as e:
        log.emit("error", message=str(e))
    except Exception as e:
        log.emit("error", message=f"{type(e).__name__}: {e}"[:300])
        raise
    finally:
        STOP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
