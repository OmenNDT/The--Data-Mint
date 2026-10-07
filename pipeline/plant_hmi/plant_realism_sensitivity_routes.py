"""Tuyến HTTP cho mục "Độ nhạy núm" trên trang độ thật (bước 4, plan
`plans/261002-1430-realism-knob-sensitivity-screening/plan.md`): đo từng nhóm núm lệch quanh điểm gốc (núm sản
xuất hiện tại), xem núm nào đẩy mục tiêu nào, đẩy bao nhiêu, kéo hỏng mục tiêu nào khác.

  GET  /plant-hmi/realism/api/sensitivity        bản đo mới nhất, trạng thái lượt đang chạy, "đã cũ" so với núm
                                                  sản xuất hiện tại, các nhóm sẽ đo
  POST /plant-hmi/realism/api/sensitivity/start   {"pilot": bool, "n_per_type": int 5..40} -> mở lượt mới

Việc nặng (`python -m realism.sensitivity_screen`) chạy dưới `systemd-run --user` làm unit
`tdm-realism-<run_id>`, giống `/api/run` của `plant_realism_routes.py` (cùng lý do: ngoài cgroup tdm-backend, một
lượt đo không bị giết khi khởi động lại launcher). Tuyến này chỉ mở lượt, đọc nhật ký/kết quả; dừng dùng chung
`/api/stop` của `plant_realism_routes.py` (cùng `realism/state/stop.flag`). Ghi dùng chung CSRF guard
(X-Plant-HMI: 1 + kiểm Origin/Host) như mọi tuyến ghi khác của Plant HMI.

Kết quả: bản đủ (không pilot) được `sensitivity_screen` chép vào `realism/state/sensitivity.json` ("latest");
mọi lượt (pilot hay không) còn có bản riêng ở `realism/state/runs/<run_id>/sensitivity.json" — khi lượt MỚI NHẤT
là pilot, bản riêng đó được lộ thêm ra ở "latest_pilot" để xem trước khi chạy đủ.
"""
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from realism import issues, knobs, sensitivity_groups
from realism.runlog import RUNS_DIR, list_runs, read_events, read_json

from . import plant_gpu_lease as gpu_lease
from . import plant_realism_job_status as job_status
from .plant_batch_process_ops import is_unit_active
from .plant_setpoint_routes import _require_trusted_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/realism")
PIPELINE = Path(__file__).resolve().parents[1]
SENS_LATEST_PATH = PIPELINE / "realism" / "state" / "sensitivity.json"
N_MIN, N_MAX, N_DEFAULT = 5, 40, 20
_START = threading.Lock()


def _write_guard(request, x_plant_hmi):
    _require_trusted_request(request, x_plant_hmi)
    return request.client.host if request.client else "unknown"


def _sens_runs():
    """Lượt đo theo thứ tự tên (sens-<ngày-giờ>), bỏ các lượt đo con "-eval-": list_runs() xếp theo mtime nên mỗi lần
    một lượt con ghi result.json nó thành "mới nhất", làm trang báo sai trạng thái và /api/stop trả 409 (review H1)."""
    return sorted(r for r in list_runs() if r.startswith("sens-") and "-eval-" not in r)


def _job_for(rid: str) -> dict:
    """Trạng thái một lượt đo, cùng cách suy luận như `plant_realism_job_status.job()`
    (xong/lỗi đọc từ nhật ký, còn sống suy từ pid) nhưng theo tiến độ riêng của
    `sensitivity_screen` (bản ghi kind=variant, kind=gen_progress thay vì kind=item/gen_progress
    của vòng lặp chính)."""
    ev = read_events(rid)
    if not ev:                                            # chưa ghi được dòng nào: đang khởi động hay đã chết ngay
        if is_unit_active(job_status.unit_for(rid)):
            return {"run_id": rid, "state": "running", "stage": "khởi động"}
        return {"run_id": rid, "state": "failed",
                "error": f"lượt đo dừng khi khởi động: {job_status.log_tail(rid) or 'không có nhật ký'}"}
    cfg = next((e for e in ev if e["kind"] == "config"), {})
    last = {e["kind"]: e for e in ev}
    err = last.get("error")
    state = ("done" if "done" in last else "stopped" if err and err.get("stopped") else "failed" if err else
             "running" if job_status.alive(ev[0]["pid"], "realism.sensitivity_screen") else "dead")
    variant, gen = last.get("variant", {}), last.get("gen_progress", {})
    return {"run_id": rid, "state": state, "pilot": bool(cfg.get("pilot")), "n_per_type": cfg.get("n_per_type"),
            "started": ev[0]["ts"], "variant": variant.get("id"), "variant_index": variant.get("index"),
            "variant_total": variant.get("total"), "gen_done": gen.get("done"), "gen_total": gen.get("total"),
            "error": err.get("message") if err else None, "last_ts": ev[-1]["ts"]}


def sens_job() -> dict:
    """Lượt đo độ nhạy gần nhất, hoặc rảnh. Dùng cả ở đây và ở `/api/stop` của
    `plant_realism_routes.py` (một flag dừng chung cho cả vòng lặp và lượt đo)."""
    runs = _sens_runs()
    return _job_for(runs[-1]) if runs else {"state": "idle"}


_TARGET_SPEC = {t["label"]: (t["op"], t["value"]) for iss in issues.ISSUES for t in iss["targets"]}


def _helps(entry: dict, op: str, value) -> Optional[bool]:
    """Chiều "có giúp" của một mục tiêu bị đổi: True đẩy đúng hướng issues.py muốn, False đẩy sai
    hướng, None khi thiếu prev/new để nói chiều. "between": còn ngoài khoảng thì xích gần khoảng
    hơn là giúp; đã trong khoảng thì còn trong khoảng sau khi đổi là giúp, ra khỏi là hại."""
    prev, new, delta = entry.get("prev"), entry.get("new"), entry.get("delta")
    if prev is None or new is None or delta is None:
        return None
    if op == ">=":
        return delta > 0
    if op == "<=":
        return delta < 0
    if op == "between":                                   # theo delta ghép cặp (số hiển thị), gốc là prev
        lo, hi = value
        moved = prev + delta
        if lo <= prev <= hi:
            return lo <= moved <= hi
        target = lo if prev < lo else hi
        return abs(moved - target) < abs(prev - target)
    return None


def _with_helps(sens: Optional[dict]) -> Optional[dict]:
    """Bản sao của `sens` với "helps" gắn vào mỗi mục tiêu của mỗi biến thể; không sửa tệp gốc."""
    if not sens:
        return sens
    effects = {}
    for vid, eff in (sens.get("effects") or {}).items():
        targets = {}
        for label, entry in (eff.get("targets") or {}).items():
            spec = _TARGET_SPEC.get(label)
            targets[label] = {**entry, "helps": _helps(entry, *spec) if spec else None}
        effects[vid] = {**eff, "targets": targets}
    return {**sens, "effects": effects}


def _read_latest() -> Optional[dict]:
    try:
        return json.loads(SENS_LATEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _is_stale(latest: Optional[dict]) -> bool:
    """Núm sản xuất hiện tại có khác bộ đã dùng làm điểm gốc lúc đo không (so sánh từng núm, dung
    sai nhỏ cho số thực); chưa đo lần nào thì không có gì để gọi là "cũ"."""
    if not latest:
        return False
    base = latest.get("base_knobs") or {}
    production = knobs.values(knobs.resolve("production", use_env=False))
    return any(base.get(k) is None or abs(float(base[k]) - float(v)) > 1e-6 for k, v in production.items())


@router.get("/api/sensitivity")
def sensitivity():
    try:
        latest = _with_helps(_read_latest())
        runs = _sens_runs()
        run_sens = read_json(runs[-1], "sensitivity.json") if runs else None
        latest_pilot = _with_helps(run_sens) if run_sens and run_sens.get("pilot") else None
        production = knobs.values(knobs.resolve("production", use_env=False))
        groups = {name: {"knobs": list(spec["knobs"]), "types": spec["types"], "mode": spec["mode"],
                          "two_sided": spec["two_sided"]} for name, spec in sensitivity_groups.GROUPS.items()}
        variants_planned = [v[0] for v in sensitivity_groups.variants(production)]
        return JSONResponse({
            "latest": latest, "latest_pilot": latest_pilot, "stale": _is_stale(latest),
            "job": sens_job(), "groups": groups, "variants_planned": variants_planned,
        }, headers={"Cache-Control": "no-store"})
    except Exception:                                      # trang độ thật không bao giờ được làm sập launcher
        logger.exception("sensitivity state failed")
        return JSONResponse({"error": "đọc độ nhạy lỗi, xem log launcher"}, status_code=500)


@router.post("/api/sensitivity/start")
def start(body: dict, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    _write_guard(request, x_plant_hmi)
    pilot = bool(body.get("pilot", False))
    n = body.get("n_per_type", N_DEFAULT)
    if not (isinstance(n, int) and N_MIN <= n <= N_MAX):
        raise HTTPException(status_code=422, detail=f"số ảnh mỗi loại {N_MIN}..{N_MAX}")
    with _START:                                           # kiểm và mở trong cùng một khoá: không mở hai lượt
        if job_status.job().get("state") == "running":
            raise HTTPException(status_code=409, detail="Vòng lặp cải thiện đang chạy: chờ xong hoặc dừng trước")
        if sens_job().get("state") == "running":
            raise HTTPException(status_code=409, detail="Đang có lượt đo độ nhạy khác chạy: chờ xong hoặc dừng trước")
        if job_status.batch_running():
            raise HTTPException(status_code=409, detail="Đang có đợt sinh ảnh khác chạy (GPU bận)")
        lease = gpu_lease.current()
        if lease:
            raise HTTPException(status_code=409, detail=f"GPU đang được giữ bởi {lease.get('owner', '?')}")
        rid = time.strftime("sens-%Y%m%d-%H%M%S")
        (RUNS_DIR / rid).mkdir(parents=True, exist_ok=True)
        unit = job_status.unit_for(rid)
        argv = [sys.executable, "-m", "realism.sensitivity_screen", "--run-id", rid, "--n-per-type", str(n)]
        if pilot:
            argv.append("--pilot")
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
    return {"run_id": rid, "unit": unit, "pilot": pilot}
