"""Núm vặn độ thật của bộ sinh: sổ đăng ký, giải giá trị trong tiến trình sinh, hai kho SP, nhật ký, bản PV.

Mặc định của mọi núm = hành vi cũ của bộ sinh, nên thêm module này không đổi đợt sinh nào khi chưa ai vặn.
Hai kho: "production" (realism/state/knobs.json, mọi đợt sinh của launcher đọc) và "candidate" (candidate-knobs.json,
núm thử của vòng lặp). Vòng lặp chỉ ghi kho thử và truyền núm thử cho đợt sinh của nó qua env REALISM_KNOBS; muốn đưa
vào sản xuất phải bấm "Đưa vào sản xuất" trên HMI (promote). Thứ tự giải trong tiến trình sinh (luật R1):
env REALISM_KNOBS (LOCAL) > kho sản xuất (REMOTE) > mặc định; giải một lần, đóng băng cả đợt (R3), ghi PV (R2).
"""
import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent / "state"
FILES = {"production": "knobs.json", "candidate": "candidate-knobs.json"}
PV_NAME = "realism-knobs-used.json"
FROZEN_ENV = "REALISM_KNOBS_FROZEN"

# tên → (vấn đề, nhãn, min, max, mặc định = hành vi cũ, giá trị sửa đề xuất)
REGISTRY = {
    "post_depth_min": (1, "Độ sâu làm tối, cận dưới (× hệ số cũ)", 0.2, 1.0, 1.0, 0.45),
    "post_depth_max": (1, "Độ sâu làm tối, cận trên (× hệ số cũ)", 0.2, 1.0, 1.0, 0.65),
    "post_modulation": (1, "Độ thay đổi độ sâu dọc lỗi (0 là đều)", 0.0, 0.9, 0.0, 0.65),
    "post_modulation_sigma": (1, "Cỡ vệt thay đổi độ sâu (điểm ảnh)", 2.0, 20.0, 6.0, 6.0),
    "post_edge_blur_sigma": (1, "Độ nhoè mép vùng làm tối (σ, điểm ảnh)", 1.0, 5.0, 2.0, 3.0),
    "crack_transverse_share": (2, "Tỉ lệ vết nứt đứng", 0.0, 0.8, 0.0, 0.42),
    "crack_widen_px": (2, "Làm dày vệt nứt tối đa (điểm ảnh)", 0.0, 4.0, 0.0, 2.0),
    "pore_aspect_min": (3, "Tỉ lệ trục lỗ khí, cận dưới", 1.0, 3.0, 1.0, 1.5),
    "pore_aspect_max": (3, "Tỉ lệ trục lỗ khí, cận trên", 1.0, 3.0, 1.0, 2.1),
    "pore_axis_jitter_deg": (3, "Độ lệch trục lỗ khí quanh phương ngang (độ)", 0.0, 90.0, 25.0, 25.0),
    "pore_irregularity_px": (3, "Độ gồ ghề mép lỗ khí (điểm ảnh)", 0.0, 4.0, 0.0, 2.0),
    # Rỗ khí CHUỖI có núm riêng (người dùng duyệt 5/10): kéo thuôn mạnh cùng phương làm các lỗ sát nhau dính thành dải
    # liền, nhìn như xỉ/không thấu. Mặc định = hành vi cũ (tròn); sản xuất đặt bằng giá trị chuỗi đang dùng khi tách.
    "linear_pore_aspect_min": (3, "Rỗ khí chuỗi: tỉ lệ trục lỗ, cận dưới", 1.0, 3.0, 1.0, 1.28),
    "linear_pore_aspect_max": (3, "Rỗ khí chuỗi: tỉ lệ trục lỗ, cận trên", 1.0, 3.0, 1.0, 1.28),
    "linear_pore_irregularity_px": (3, "Rỗ khí chuỗi: độ gồ ghề mép lỗ (điểm ảnh)", 0.0, 4.0, 0.0, 0.0),
    "lop_tilt_max_deg": (4, "Độ nghiêng tối đa dải không thấu (độ)", 0.0, 8.0, 0.0, 4.0),
    "lop_wave_amp_px": (4, "Biên độ lượn dải không thấu (điểm ảnh)", 0.0, 6.0, 0.0, 2.5),
    "lop_gap_max": (4, "Số khoảng đứt tối đa dải không thấu", 0.0, 5.0, 0.0, 3.0),
    # Độ bám mask của ControlNet (ảnh điều khiển = mask): cao thì mép in đúng mask nhị phân (sắc), thấp thì SD tự do
    # hơn nhưng lỗi có thể lệch nhãn. Mặc định = 0,8 cố định trong workflow. Vòng lặp tự chỉnh (người dùng duyệt
    # 2026-10-02): vòng đầu 0,7; độ dốc biên còn trượt thì −0,05; vùng chạm lỗi tụt dưới 0,7 thì +0,05 (issues._rule).
    # Độ sâu làm tối RIÊNG cho 3 loại rỗ khí (người dùng duyệt 6/10, đo thước mới W0003: rỗ khí cần đậm hơn hẳn,
    # 0,80–1,00 tốt lên mọi độ đo; nứt/không thấu/không ngấu chỉ cần 0,50–0,70). 0 = dùng độ sâu chung (hành vi cũ).
    "pore_post_depth_min": (1, "Rỗ khí: độ sâu làm tối, cận dưới (0 là dùng độ sâu chung)", 0.0, 1.0, 0.0, 0.8),
    "pore_post_depth_max": (1, "Rỗ khí: độ sâu làm tối, cận trên (0 là dùng độ sâu chung)", 0.0, 1.0, 0.0, 1.0),
    # Pha 2 thước mới (người dùng duyệt 6/10, chạy song song nhiều nhánh): nối dây trước, mặc định = hành vi cũ.
    # Độ sâu riêng rỗ khí cụm / rỗ khí chuỗi (0 là dùng độ sâu rỗ khí pore_post_depth_*): cụm thật nhạt, chuỗi thật đậm.
    "clustered_post_depth_min": (3, "Rỗ khí cụm: độ sâu làm tối, cận dưới (0 là dùng độ sâu rỗ khí)", 0.0, 1.0, 0.0, 0.0),
    "clustered_post_depth_max": (3, "Rỗ khí cụm: độ sâu làm tối, cận trên (0 là dùng độ sâu rỗ khí)", 0.0, 1.0, 0.0, 0.0),
    "linear_post_depth_min": (3, "Rỗ khí chuỗi: độ sâu làm tối, cận dưới (0 là dùng độ sâu rỗ khí)", 0.0, 1.0, 0.0, 0.0),
    "linear_post_depth_max": (3, "Rỗ khí chuỗi: độ sâu làm tối, cận trên (0 là dùng độ sâu rỗ khí)", 0.0, 1.0, 0.0, 0.0),
    # Xỉ: thật to gấp ~8 lần, dài, méo (realism/mask_shaping_slag.py).
    "slag_scale": (6, "Xỉ: phóng diện tích vùng (lần)", 1.0, 12.0, 1.0, 1.0),
    "slag_elongation": (6, "Xỉ: kéo dài theo trục (tỉ lệ trục)", 1.0, 6.0, 1.0, 1.0),
    "slag_irregularity_px": (6, "Xỉ: độ méo mép (điểm ảnh)", 0.0, 8.0, 0.0, 0.0),
    # Rỗ khí kéo dài: thật nằm xiên ~60°, sinh luôn nằm ngang (realism/mask_shaping_ecav.py).
    "ecav_tilt_max_deg": (6, "Rỗ khí kéo dài: góc xiên tối đa (độ)", 0.0, 60.0, 0.0, 0.0),
    # Không ngấu: thật nhỏ và mảnh hơn, đứt đoạn (realism/mask_shaping_lof.py).
    "lof_length_scale": (6, "Không ngấu: tỉ lệ chiều dài dải", 0.2, 1.0, 1.0, 1.0),
    "lof_width_scale": (6, "Không ngấu: tỉ lệ bề dày dải", 0.3, 1.0, 1.0, 1.0),
    "lof_gap_max": (6, "Không ngấu: số khoảng đứt tối đa", 0.0, 5.0, 0.0, 0.0),
    "controlnet_strength": (1, "Độ bám mask của ControlNet (strength)", 0.3, 1.0, 0.8, 0.7),
}
INT_KNOBS = {"lop_gap_max", "lof_gap_max"}
DEFAULTS = {k: s[4] for k, s in REGISTRY.items()}


def store_path(store="production"):
    return STATE_DIR / FILES[store]


def validate(name, value):
    """Giá trị đã chuẩn hoá hoặc ValueError (tuyến HTTP trả 422)."""
    if name not in REGISTRY:
        raise ValueError(f"không có núm '{name}'")
    if isinstance(value, bool):
        raise ValueError(f"{name} phải là số")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} phải là số") from None
    lo, hi = REGISTRY[name][2], REGISTRY[name][3]
    if not lo <= v <= hi:
        raise ValueError(f"{name} phải trong {lo}..{hi}")
    return int(round(v)) if name in INT_KNOBS else round(v, 4)


def read_store(store="production"):
    try:
        d = json.loads(store_path(store).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _entry_value(d):
    return d.get("value") if isinstance(d, dict) else None


def _json_env(var):
    try:
        d = json.loads(os.environ.get(var, "") or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def resolve(store="production", use_env=True):
    """{tên: {"value", "source"}}. Đã đóng băng cho đợt (FROZEN_ENV) thì trả nguyên bản đó. Không bao giờ ném lỗi."""
    frozen = _json_env(FROZEN_ENV) if use_env else {}
    if frozen and all(isinstance(frozen.get(k), dict) and "value" in frozen[k] for k in REGISTRY):
        return frozen
    env = _json_env("REALISM_KNOBS") if use_env else {}
    st, out = read_store(store), {}
    for name, spec in REGISTRY.items():
        val, src = spec[4], "default"
        for cand, s in ((env.get(name), "LOCAL"), (_entry_value(st.get(name)), "REMOTE")):
            if cand is None:
                continue
            try:
                val, src = validate(name, cand), s
                break
            except ValueError:
                continue
        out[name] = {"value": val, "source": src}
    for a, b in (("post_depth_min", "post_depth_max"), ("pore_aspect_min", "pore_aspect_max"),
                 ("linear_pore_aspect_min", "linear_pore_aspect_max"), ("pore_post_depth_min", "pore_post_depth_max"),
                 ("clustered_post_depth_min", "clustered_post_depth_max"), ("linear_post_depth_min", "linear_post_depth_max")):
        if out[a]["value"] > out[b]["value"]:                  # cận dưới vượt cận trên: đổi chỗ, không ném lỗi
            out[a], out[b] = out[b], out[a]
    return out


def values(resolved=None):
    return {k: v["value"] for k, v in (resolved or resolve()).items()}


def freeze_for_batch(output_dir=None):
    """Gọi một lần ở đầu đợt sinh: giải núm (kho sản xuất, env đè), đóng băng qua env cho tiến trình con, ghi PV."""
    r = resolve("production")
    os.environ[FROZEN_ENV] = json.dumps(r)
    if output_dir:
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            (Path(output_dir) / PV_NAME).write_text(json.dumps({"ts": time.time(), "knobs": r}, ensure_ascii=False,
                                                               indent=1), encoding="utf-8")
        except OSError:
            pass
    return r


@contextmanager
def _locked():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_DIR / "knobs.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)                         # HMI (nhiều luồng) và tiến trình vòng lặp cùng ghi
        yield


def write_many(changes, who, reason, store="production"):
    """Ghi nhiều núm một lượt (khoá, ghi tệp tạm rồi đổi tên) và nhật ký. changes: {tên: giá trị}. Trả về kho mới."""
    clean = {k: validate(k, v) for k, v in changes.items()}
    with _locked():
        st = read_store(store)
        now, lines = time.time(), []
        for k, v in clean.items():
            old = _entry_value(st.get(k))
            st[k] = {"value": v, "ts": now, "who": str(who)[:40], "reason": str(reason)[:200]}
            lines.append({"ts": now, "store": store, "name": k, "old": old, "new": v, "who": str(who)[:40],
                          "reason": str(reason)[:200]})
        fd, tmp = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        os.replace(tmp, store_path(store))
        try:
            with open(STATE_DIR / "knobs-audit.jsonl", "a", encoding="utf-8") as f:
                f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in lines)
        except OSError:
            pass
    return st


def audit_tail(n=20):
    try:
        lines = (STATE_DIR / "knobs-audit.jsonl").read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(x) for x in reversed(lines) if x.strip()]
    except (OSError, ValueError):
        return []


def read_pv(output_dir):
    try:
        return json.loads((Path(output_dir) / PV_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
