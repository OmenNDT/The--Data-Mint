"""Bước 4 (độ nhạy): dựng cấu hình batch riêng và chạy batch-production-main.py làm tiến trình con cho
một lượt sinh (gốc hoặc một biến thể "generate"), cùng cách làm với realism/loop_generate.py nhưng ghi
vào thư mục output/realism-sensitivity thay vì output/realism-loop. Tách khỏi sensitivity_screen.py
để mỗi tệp dưới 200 dòng."""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

from . import exam_set, knobs
from .loop_common import BATCH_MAIN, PIPELINE, STATE, STOP, Stopped

OUT_ROOT = PIPELINE.parent / "output" / "realism-sensitivity"
CFG_DIR = PIPELINE / "config" / "_generated"
CKPT_ROOT = STATE / "checkpoints"


def sanitize(variant_id):
    """Tên biến thể dùng trong tên tệp/eval_run: "+"/"-" không an toàn trong mọi hệ tệp hay tên run."""
    return variant_id.replace("+", "p").replace("-", "m")


def _reachable(host, port):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/system_stats", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def _host_port():
    cfg = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text(encoding="utf-8"))
    host, port = cfg["comfyui"].get("host"), cfg["comfyui"].get("port", 8188)
    if _reachable(host, port):
        return host, port
    if _reachable("127.0.0.1", 8188):
        return "127.0.0.1", 8188
    raise RuntimeError(f"không liên lạc được ComfyUI sản xuất {host}:{port} lẫn 127.0.0.1:8188")


def clamp_n(n):
    """Kẹp n_per_type trong [1, per_type] của bộ đề thi cố định; tạo bộ đề thi lần đầu nếu chưa có."""
    try:
        exam = exam_set.load_exam_set()
    except FileNotFoundError:
        cfg = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text(encoding="utf-8"))
        exam = exam_set.build_exam_set(cfg["paths"]["backgrounds_dir"])
    return max(1, min(n, exam["per_type"]))


def build_config(run_id, slug, types, n, out_dir):
    """Cấu hình batch riêng cho một lượt sinh (gốc hoặc biến thể "generate") trên bộ đề thi cố định.
    Trả về (đường dẫn cấu hình, tổng số ảnh, "host:port" ComfyUI dùng)."""
    cfg = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text(encoding="utf-8"))
    host, port = _host_port()
    cfg["comfyui"].update(host=host, port=port)
    cases = exam_set.subset(types, n)
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    jobs_path = CFG_DIR / f"sens-{run_id}-{slug}-jobs.json"
    jobs_path.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    cfg["generation"].update(total_images=len(cases), fixed_jobs=str(jobs_path))
    cfg["generation"].pop("defect_distribution", None)
    cfg["paths"].update(output_base_dir=str(out_dir), checkpoint_dir=str(CKPT_ROOT / f"sens-{run_id}-{slug}"),
                        logs_dir=str(STATE / "logs"))
    cfg_path = CFG_DIR / f"sens-{run_id}-{slug}.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Bản sao jobs.json trong thư mục ảnh ra: evaluate.run() ghép case_id theo job_id qua tệp này.
    (out_dir / "fixed-jobs.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    return cfg_path, len(cases), f"{host}:{port}"


def run_batch_subprocess(cfg_path, out_dir, types, total, extra_env, log, log_name):
    """Chạy batch-production-main.py làm tiến trình con (như loop_generate.do_generate); tôn trọng
    state/stop.flag (giết cả nhóm tiến trình), báo tiến độ qua log.emit("gen_progress", ...)."""
    env = {**os.environ, **extra_env}
    env.pop(knobs.FROZEN_ENV, None)
    with open(log.dir / f"{log_name}.log", "w") as glog:
        proc = subprocess.Popen([sys.executable, str(BATCH_MAIN), "--config", str(cfg_path)],
                                cwd=str(BATCH_MAIN.parent), stdin=subprocess.DEVNULL, stdout=glog,
                                stderr=subprocess.STDOUT, env=env, start_new_session=True)
        log.emit("child", pid=proc.pid, what=log_name)
        while proc.poll() is None:
            if STOP.exists():
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise Stopped(f"dừng theo yêu cầu khi đang sinh ({log_name})")
            done = sum(1 for t in types for _ in (out_dir / t).glob("*[0-9].png")) if out_dir.exists() else 0
            log.emit("gen_progress", done=done, total=total)
            time.sleep(5)
    if proc.returncode != 0:
        raise RuntimeError(f"sinh ảnh lỗi (mã {proc.returncode}), xem {glog.name}")
