"""Bộ nhớ hướng vặn mỗi núm cho cổng nghiệm thu (bước 3): vòng bị loại ghi lại hướng + bước đã thử; đề xuất lần
sau cho núm đó dùng bước giảm nửa cùng hướng; bị loại LẦN HAI cùng hướng (đã nửa bước) thì đổi hướng, về bước
đầy đủ. Vòng được nhận xoá bộ nhớ của núm đã đổi (đã tìm được hướng tốt, không cần nhớ nữa).

realism/state/tuning-memory.json: {tên núm: {"direction": 1|-1, "scale": float}}. "direction" là hướng CẦN DÙNG
cho đề xuất kế tiếp (không phải hướng đã bị loại) — apply_to_proposal dùng trực tiếp, không phải đoán ngược.
"""
import json
from pathlib import Path

from . import knobs

PATH = Path(__file__).resolve().parent / "state" / "tuning-memory.json"


def read():
    try:
        d = json.loads(PATH.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(mem):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PATH)


def record_rejection(best_knobs, rejected_knobs):
    """best_knobs/rejected_knobs: {tên: giá trị thô} (không phải {"value":...}). Với mỗi núm đã đổi trong vòng bị
    loại: lần đầu theo một hướng → nhớ nửa bước cùng hướng; đã nửa bước rồi mà vẫn bị loại cùng hướng → đổi hướng,
    về bước đầy đủ; đang ở hướng ngược (đã đổi hướng một lần) mà vẫn bị loại → nửa bước tiếp (không đổi hướng mãi)."""
    mem = read()
    for k in knobs.REGISTRY:
        bv, rv = best_knobs.get(k), rejected_knobs.get(k)
        if bv is None or rv is None or rv == bv:
            continue
        tried_dir = 1 if rv > bv else -1                        # hướng vừa thử (vừa bị loại)
        prev = mem.get(k)
        if prev and prev.get("direction") == tried_dir and prev.get("scale", 1.0) <= 0.5:
            mem[k] = {"direction": -tried_dir, "scale": 1.0}     # nửa bước cùng hướng cũng bị loại: đổi hướng
        elif prev and prev.get("direction") == tried_dir:
            mem[k] = {"direction": tried_dir, "scale": prev.get("scale", 1.0) / 2}
        else:
            mem[k] = {"direction": tried_dir, "scale": 0.5}      # lần đầu theo hướng này: nửa bước, giữ hướng
    _write(mem)
    return mem


def clear(knob_names):
    """Vòng được nhận: xoá bộ nhớ của các núm vừa đổi thành công (không cần nhớ hướng đã thử nữa)."""
    mem = read()
    changed = False
    for k in knob_names:
        if mem.pop(k, None) is not None:
            changed = True
    if changed:
        _write(mem)
    return mem


def apply_to_proposal(current, proposed, mem=None):
    """Áp bộ nhớ vào đề xuất thô của issues.propose: núm có bộ nhớ dùng ĐÚNG hướng + bước đã ghi (scale × độ lớn
    bước thô) thay cho hướng/bước rule tự tính — core logic bước 3 "nửa bước / đổi hướng". Núm rule không đề xuất
    đổi (proposed[k] == current[k]) thì bỏ qua, không tự áp bộ nhớ khi không có vấn đề nào đang gọi tới núm đó."""
    mem = mem if mem is not None else read()
    out = dict(proposed)
    for k, m in mem.items():
        if k not in out or k not in current:
            continue
        raw_delta = out[k] - current[k]
        if raw_delta == 0:
            continue
        magnitude = abs(raw_delta) * m.get("scale", 1.0)
        new_delta = magnitude * m.get("direction", 1 if raw_delta > 0 else -1)
        lo, hi = knobs.REGISTRY[k][2], knobs.REGISTRY[k][3]
        out[k] = min(max(current[k] + new_delta, lo), hi)
    return out
