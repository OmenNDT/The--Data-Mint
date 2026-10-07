"""Tuyến HTTP của vòng cải thiện độ thật, gắn dưới /plant-hmi (cùng cổng 7860 với launcher, không mở cổng mới).

  GET  /plant-hmi/realism/                trang (static/plant-hmi-realism.html)
  GET  /plant-hmi/realism/api/state       việc đang chạy + tiến độ, núm (thử, sản xuất, PV, nhật ký), 5 vấn đề, lịch sử
  GET  /plant-hmi/realism/api/result/{id} kết quả đo một lượt (sáu tiêu chí, từng cặp)
  PUT  /plant-hmi/realism/api/knobs       {"changes": {tên: giá trị}, "reason"}: ghi KHO NÚM THỬ; 422 ngoài giới hạn
  POST /plant-hmi/realism/api/promote     đưa núm thử vào kho sản xuất (mọi đợt sinh của launcher đọc kho này)
  POST /plant-hmi/realism/api/reset-production  đưa kho sản xuất về mặc định (hành vi cũ của bộ sinh)
  POST /plant-hmi/realism/api/run         {"action": evaluate|propose|cycle|auto, "n_per_type", "types", "max_iter"}
  POST /plant-hmi/realism/api/stop        cờ dừng; quá hạn thì `systemctl --user stop` unit; mồ côi thì dừng nhóm tiến trình
Việc nặng chạy dưới `systemd-run --user` làm unit `tdm-realism-<run_id>` (ngoài cgroup tdm-backend, rule R8: restart
launcher không giết vòng lặp đang chạy); tuyến chỉ mở, đọc nhật ký và trạng thái. Tuyến ghi dùng chung lớp chặn CSRF
của tuyến giá trị đặt (luật H1); "ai sửa" là IP máy khách (không đăng nhập, theo quyết định cũ).
"""
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from realism import issues, knobs, loop, loop_gate
from realism.runlog import RUNS_DIR, list_runs, read_json

from . import plant_realism_job_status as job_status
from .plant_realism_sensitivity_routes import sens_job
from .plant_setpoint_routes import _require_trusted_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/realism")
STATIC = Path(__file__).resolve().parent / "static" / "plant-hmi-realism.html"
PIPELINE = Path(__file__).resolve().parents[1]
RUN_ID = re.compile(r"[\w-][\w.-]{0,79}")
ACTIONS = {"evaluate", "propose", "cycle", "auto"}
TYPES = {"crack", "porosity", "lack_of_penetration", "clustered_porosity", "linear_porosity", "lack_of_fusion"}
_START = threading.Lock()
STOP_GRACE_S = 30.0  # first /api/stop sets the flag; a repeat call past this age escalates to systemctl stop


def _write_guard(request, x_plant_hmi):
    _require_trusted_request(request, x_plant_hmi)
    return request.client.host if request.client else "unknown"


@router.get("/", include_in_schema=False)
def page():
    return FileResponse(STATIC, media_type="text/html", headers={"Cache-Control": "no-cache"})


@router.get("/api/state")
def state():
    try:
        h = loop.history()
        latest = read_json(h[-1]["eval_run"], "result.json") if h else None
        base = read_json(h[0]["eval_run"], "result.json") if h else None
        pv = next((r["knobs"] for r in reversed(h) if r.get("knobs")), None)
        best = loop_gate.read_best()
        return JSONResponse({
            "ts": time.time(), "job": job_status.job(), "history": h,
            "issues": {"latest": issues.evaluate(latest), "baseline": issues.evaluate(base),
                       "latest_iter": h[-1]["iter"] if h else None},
            "latest_eval": h[-1]["eval_run"] if h else None, "baseline_eval": h[0]["eval_run"] if h else None,
            "best": {"iter": best["iter"], "score": best.get("score")} if best else None,
            "knobs": {"registry": {k: {"issue": s[0], "label": s[1], "min": s[2], "max": s[3], "default": s[4],
                                       "fix": s[5]} for k, s in knobs.REGISTRY.items()},
                      "candidate": knobs.resolve("candidate", use_env=False),
                      "production": knobs.resolve("production", use_env=False),
                      "env_override": bool(os.environ.get("REALISM_KNOBS")), "pv": pv, "audit": knobs.audit_tail(15)},
        }, headers={"Cache-Control": "no-store"})
    except Exception:                                        # trang độ thật không bao giờ được làm sập launcher
        logger.exception("realism state failed")
        return JSONResponse({"error": "đọc trạng thái lỗi, xem log launcher"}, status_code=500)


@router.get("/api/result/{run_id}")
def result(run_id: str):
    r = read_json(run_id, "result.json") if RUN_ID.fullmatch(run_id) else None
    if r is None:
        raise HTTPException(status_code=404)
    return JSONResponse(r, headers={"Cache-Control": "no-store"})


@router.put("/api/knobs")
def put_knobs(body: dict, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    who = _write_guard(request, x_plant_hmi)
    changes = body.get("changes") or {}
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(status_code=422, detail="thiếu changes")
    try:
        return {"store": knobs.write_many(changes, who, body.get("reason") or "chỉnh tay trên HMI", store="candidate")}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/api/promote")
def promote(request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    """Đưa núm BẢN TỐT NHẤT (cổng nghiệm thu, bước 3) vào sản xuất — không phải núm thử hiện tại trên HMI, vì
    núm thử có thể đang ở một vòng chưa qua cổng hoặc đã bị loại. Chưa có bản tốt nhất nào (chưa vòng nào dùng
    bộ đề thi cố định) → 409, báo chạy ít nhất một vòng trước."""
    who = _write_guard(request, x_plant_hmi)
    best = loop_gate.read_best()
    if not best:
        raise HTTPException(status_code=409, detail="Chưa có bản tốt nhất (chạy ít nhất một vòng trên bộ đề thi trước)")
    best_knobs = {k: v["value"] for k, v in (best.get("knobs") or {}).items()}
    reason = f"đưa bản tốt nhất (vòng {best['iter']}) vào sản xuất"
    return {"store": knobs.write_many(best_knobs or dict(knobs.DEFAULTS), who, reason, store="production"),
            "promoted_iter": best["iter"]}


@router.post("/api/reset-production")
def reset_production(request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    who = _write_guard(request, x_plant_hmi)
    return {"store": knobs.write_many(dict(knobs.DEFAULTS), who, "đưa sản xuất về mặc định", store="production")}


@router.post("/api/run")
def run(body: dict, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    _write_guard(request, x_plant_hmi)
    # Mặc định 40 (bước 2a): sau khi lọc has_region, 20 ca để lại quá ít hàng cho cổng v2 ghép cặp (cần >= 10
    # ca chung có vùng mỗi loại).
    action, n, max_iter = body.get("action"), body.get("n_per_type", 40), body.get("max_iter", 5)
    types = [t for t in (body.get("types") or loop.DEFAULT_TYPES) if t in TYPES]
    if action not in ACTIONS:
        raise HTTPException(status_code=422, detail="action phải là evaluate, propose, cycle hoặc auto")
    if not (isinstance(n, int) and 1 <= n <= 500) or not (isinstance(max_iter, int) and 1 <= max_iter <= 20) or not types:
        raise HTTPException(status_code=422, detail="số ảnh mỗi loại 1..500, số vòng 1..20, ít nhất một loại lỗi")
    with _START:                                             # kiểm và mở trong cùng một khoá: không mở hai lượt
        if job_status.job().get("state") == "running":
            raise HTTPException(status_code=409, detail="Vòng lặp đang chạy: chờ xong hoặc dừng trước")
        if sens_job().get("state") == "running":            # cờ dừng dùng chung: không chạy song song (review M3)
            raise HTTPException(status_code=409, detail="Đang đo độ nhạy núm: chờ xong hoặc dừng trước")
        if action in ("cycle", "auto") and job_status.batch_running():
            raise HTTPException(status_code=409, detail="Đang có đợt sinh ảnh khác chạy (GPU bận)")
        rid = time.strftime("loop-%Y%m%d-%H%M%S-") + f"{int(time.time() * 1000) % 1000:03d}"
        (RUNS_DIR / rid).mkdir(parents=True, exist_ok=True)
        unit = job_status.unit_for(rid)
        # --service-type=exec + --collect: same reasoning as the batch-control route
        # (M7): "active" only once exec() itself succeeds, failed unit is unloaded.
        # --expand-environment=no (L2): run_id/types never get expanded as a systemd
        # specifier. No KillSignal override: the loop's own stop.flag is the normal
        # path; systemctl stop (SIGTERM, below) is only the last-resort escalation.
        argv = [sys.executable, "-m", "realism.loop", "--action", action, "--n-per-type", str(n),
                "--types", ",".join(types), "--max-iter", str(max_iter), "--run-id", rid]
        try:
            proc = subprocess.run(
                ["systemd-run", "--user", f"--unit={unit}", f"--working-directory={PIPELINE}",
                 "--service-type=exec", "--collect", "--expand-environment=no", *argv],
                capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HTTPException(status_code=500, detail=f"systemd-run lỗi: {exc}") from None
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:400]
            raise HTTPException(status_code=500, detail=f"systemd-run thất bại: {detail or 'không rõ lỗi'}")
    return {"run_id": rid, "unit": unit}


def _touch_or_escalate(run_id: str) -> dict:
    """stop.flag chung cho vòng lặp VÀ lượt đo độ nhạy (cả hai tôn trọng `realism/state/stop.flag`,
    bước 4 của plan độ nhạy núm): lần gọi đầu chỉ bật cờ, lần gọi lại sau khi cờ bị bỏ qua quá
    STOP_GRACE_S giây thì leo thang `systemctl --user stop` lên unit theo tên run_id."""
    loop.STATE.mkdir(parents=True, exist_ok=True)
    try:
        flag_age = time.time() - loop.STOP.stat().st_mtime
    except OSError:
        flag_age = None
    if flag_age is not None and flag_age > STOP_GRACE_S:
        unit = job_status.unit_for(run_id)                           # stop.flag was already set and ignored past grace: escalate
        out = subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True, text=True, timeout=10)
        return {"stopping": True, "escalated_unit": unit, "systemctl_ok": out.returncode == 0}
    loop.STOP.touch()
    return {"stopping": True}


@router.post("/api/stop")
def stop(request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    _write_guard(request, x_plant_hmi)
    j = job_status.job()
    if j.get("state") == "running":
        return _touch_or_escalate(j["run_id"])
    sj = sens_job()
    if sj.get("state") == "running":
        return _touch_or_escalate(sj["run_id"])
    child = j.get("child_pid")                               # vòng lặp đã chết nhưng đợt sinh nó mở còn chạy (mồ côi)
    if child and job_status.alive(child, "batch-production-main"):
        os.killpg(child, signal.SIGTERM)
        return {"stopping": True, "orphan_batch": child}
    raise HTTPException(status_code=409, detail="Không có vòng lặp nào đang chạy")
