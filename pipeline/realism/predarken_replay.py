"""Bước 4 (độ nhạy từng núm): tính lại ảnh sau bước làm tối (post_darkening.darken) từ ảnh
trước-làm-tối đã lưu (*_predarken.npz, xem batch_manager/batch-production-main.py), dùng núm bất
kỳ, hoàn toàn bằng CPU (không gọi lại ComfyUI). Dùng cho các nhóm núm "replay" trong
sensitivity_groups.GROUPS: núm chỉ tác động bước làm tối sau khi SD đã vẽ xong, nên không cần sinh
lại ảnh để đo hiệu ứng của chúng.

replay(src_dir, dst_dir, knobs, types) tái tạo đúng những gì batch-production-main.py sẽ sinh ra nếu
chạy với bộ núm đó (cùng phép làm tròn/clip, cùng cách lưu PNG mode "L"), nên realism.evaluate.run
đo được thư mục đích y như một thư mục sinh thật bằng GPU.
"""
import json
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import knobs
from .post_darkening import darken

PREDARKEN_SUFFIX = "_predarken.npz"


def _save_png(out_path, arr):
    """Lưu đúng cách apply_dark_defect_convention lưu ảnh ra (clip 0..255, uint8, mode L)."""
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L").save(str(out_path))


def _replay_one(npz_path, dst_type_dir, knobs_dict):
    """Tính lại một ảnh từ .npz trước-làm-tối; chép kèm mặt nạ chú thích và metadata nếu có."""
    data = np.load(npz_path, allow_pickle=False)
    img, bg_raw, mask_arr = data["img"], data["bg"], data["mask"]
    strength, key = float(data["strength"]), str(data["key"])
    bg = bg_raw if bg_raw.size else None
    defect_type = npz_path.parent.name             # thư mục ảnh mang tên loại lỗi (organize_by_defect)
    result = darken(img, bg, mask_arr, strength, knobs_dict, key, defect_type)
    base = npz_path.name[: -len(PREDARKEN_SUFFIX)]
    _save_png(dst_type_dir / f"{base}.png", result)
    src_dir = npz_path.parent
    for suffix in ("_mask.png", ".json"):
        src = src_dir / f"{base}{suffix}"
        if src.exists():
            shutil.copy2(src, dst_type_dir / f"{base}{suffix}")


def _write_knobs_pv(dst_dir, knobs_dict):
    """Bản PV núm đã dùng, cùng lược đồ knobs.freeze_for_batch ghi (nguồn LOCAL: núm thử của biến thể)."""
    pv = {"ts": time.time(), "knobs": {k: {"value": v, "source": "LOCAL"} for k, v in knobs_dict.items()}}
    (dst_dir / knobs.PV_NAME).write_text(json.dumps(pv, ensure_ascii=False, indent=1), encoding="utf-8")


def replay(src_dir, dst_dir, knobs_dict, types):
    """Tính lại ảnh (bước 2, làm tối) từ .npz trước-làm-tối trong src_dir/<loại>, ghi sang
    dst_dir/<loại> cùng tên tệp; chép fixed-jobs.json (ghép cặp case_id khi đo) và ghi bản PV núm."""
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for t in types:
        src_type_dir, dst_type_dir = src_dir / t, dst_dir / t
        if not src_type_dir.is_dir():
            continue
        dst_type_dir.mkdir(parents=True, exist_ok=True)
        for npz_path in sorted(src_type_dir.glob(f"*{PREDARKEN_SUFFIX}")):
            _replay_one(npz_path, dst_type_dir, knobs_dict)
    fixed_jobs = src_dir / "fixed-jobs.json"
    if fixed_jobs.exists():
        shutil.copy2(fixed_jobs, dst_dir / "fixed-jobs.json")
    _write_knobs_pv(dst_dir, knobs_dict)
