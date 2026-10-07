"""Sinh ảnh một vòng: cấu hình batch riêng trên bộ đề thi cố định, gọi batch-production-main.py làm tiến trình con.
Tách khỏi loop.py (bước 3 của plan) để mỗi tệp dưới 200 dòng; không đổi hành vi."""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

import yaml

from . import exam_set
from .loop_common import BATCH_MAIN, LOOP_OUT, PIPELINE, STATE, STOP, Stopped, candidate, history, knobs


def _reachable(host, port):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/system_stats", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def clamp_n(n):
    """n ca mỗi loại thực dùng: kẹp trong [1, per_type] của bộ đề thi (như _round_cases), không tạo bộ đề thi."""
    try:
        return max(1, min(n, exam_set.load_exam_set()["per_type"]))
    except FileNotFoundError:
        return max(1, n)


def _round_cases(types, n):
    """n ca đầu mỗi loại từ bộ đề thi cố định (tất định giữa các vòng); tạo bộ đề thi lần đầu nếu chưa có.
    Kẹp n trong [1, per_type] của bộ đề thi (mặc định 40) để không vượt số ca đã tạo sẵn."""
    try:
        exam = exam_set.load_exam_set()
    except FileNotFoundError:
        cfg = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text(encoding="utf-8"))
        exam = exam_set.build_exam_set(cfg["paths"]["backgrounds_dir"])
    n_clamped = max(1, min(n, exam["per_type"]))
    return exam_set.subset(types, n_clamped), n_clamped


def _gen_config(it, types, n):
    cfg = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text(encoding="utf-8"))
    host, port = cfg["comfyui"].get("host"), cfg["comfyui"].get("port", 8188)
    if not _reachable(host, port):
        if not _reachable("127.0.0.1", 8188):
            raise RuntimeError(f"không liên lạc được ComfyUI sản xuất {host}:{port} lẫn 127.0.0.1:8188")
        host, port = "127.0.0.1", 8188
    cfg["comfyui"].update(host=host, port=port)
    cases, n_clamped = _round_cases(types, n)
    total = len(cases)
    out = LOOP_OUT / f"iter-{it:02d}"
    jobs_path = PIPELINE / "config" / "_generated" / f"realism-iter-{it:02d}-jobs.json"
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    # Khoá fixed_jobs: scheduler sinh đúng danh sách ca này, không random/shuffle (bước 2 của plan).
    cfg["generation"].update(total_images=total, fixed_jobs=str(jobs_path))
    cfg["generation"].pop("defect_distribution", None)
    cfg["paths"].update(output_base_dir=str(out), checkpoint_dir=str(STATE / "checkpoints" / f"iter-{it:02d}"),
                        logs_dir=str(STATE / "logs"))
    path = PIPELINE / "config" / "_generated" / f"realism-iter-{it:02d}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    # Bản sao jobs.json trong thư mục ảnh ra: evaluate.run() ghép case_id theo job_id (chỉ số trong danh sách này)
    # mà không cần sửa batch-production-main.py (nó không biết và không cần biết case_id).
    out.mkdir(parents=True, exist_ok=True)
    (out / "fixed-jobs.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    return path, out, total, f"{host}:{port}", n_clamped


def _next_iter():
    used = [r["iter"] for r in history()] + [int(p.name[5:]) for p in LOOP_OUT.glob("iter-[0-9]*") if p.name[5:].isdigit()]
    return max(used, default=0) + 1                            # không bao giờ dùng lại thư mục vòng cũ


def do_generate(log, types, n):
    it = _next_iter()
    cfg_path, out, total, host, n_clamped = _gen_config(it, types, n)
    if n_clamped != n:
        log.emit("stage", stage="generate", state="n_clamped", requested=n, used=n_clamped,
                  note="bộ đề thi cố định chỉ có per_type ca, kẹp n_per_type")
    log.emit("stage", stage="generate", state="start", iter=it, total=total, types=types, output=str(out), comfyui=host)
    env = {**os.environ, "REALISM_KNOBS": json.dumps(candidate())}      # núm thử chỉ cho đợt này (nguồn LOCAL)
    env.pop(knobs.FROZEN_ENV, None)
    with open(log.dir / f"generate-iter-{it:02d}.log", "w") as glog:
        proc = subprocess.Popen([sys.executable, str(BATCH_MAIN), "--config", str(cfg_path)], cwd=str(BATCH_MAIN.parent),
                                stdin=subprocess.DEVNULL, stdout=glog, stderr=subprocess.STDOUT, env=env,
                                start_new_session=True)
        log.emit("child", pid=proc.pid, what="batch-production")
        while proc.poll() is None:
            if STOP.exists():
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise Stopped("dừng theo yêu cầu khi đang sinh ảnh")
            done = sum(1 for t in types for _ in (out / t).glob("*[0-9].png")) if out.exists() else 0
            log.emit("gen_progress", done=done, total=total, iter=it)
            time.sleep(5)
    if proc.returncode != 0:
        raise RuntimeError(f"sinh ảnh lỗi (mã {proc.returncode}), xem {glog.name}")
    log.emit("stage", stage="generate", state="end", iter=it)
    return it, out, host, n_clamped
