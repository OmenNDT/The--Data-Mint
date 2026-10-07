"""Start/stop batch control API (phase 6A): interlocked start, audited stop.

  GET  /plant-hmi/api/control/batch          configs, permissives, live batches
  POST /plant-hmi/api/control/batch/start    {config, pilot, resume, reason}
  POST /plant-hmi/api/control/batch/stop     {pid, start_ts, reason}

Same CSRF guard as every other write route (`require_trusted_request`, rule H1).
Every start/stop attempt is audited, accepted or refused (who = client IP, no
login per the user's decision). State assembly (live list, permissive inputs,
checkpoint summary) lives in `plant_batch_state_builder.py`. The "Tạo mẻ mới"
compose-options/compose routes (phase 6B) live in `plant_batch_compose_routes.py`,
included below under this same router/prefix so `plant_hmi_routes.py` needs no change.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import plant_batch_config_whitelist as whitelist
from . import plant_batch_run_dirs as run_dirs
from . import plant_batch_process_ops as ops
from . import plant_gpu_lease as gpu_lease
from . import plant_host_readers as host
from . import plant_batch_state_builder as state_builder
from .plant_batch_audit import append_audit, read_audit
from .plant_batch_compose_routes import router as compose_router
from .plant_batch_control import blocking_failures, evaluate_permissives
from .plant_request_guards import require_trusted_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control/batch")
router.include_router(compose_router)

MAX_REASON_LEN = 200
PID_REUSE_SLACK_S = 2.0  # same slack as collector.config_for's pid-reuse guard (rule R2)

state_builder.start_swap_sampler()


class StartBody(BaseModel):
    config: str
    pilot: bool = False
    resume: bool = False
    reason: str = Field(default="", max_length=MAX_REASON_LEN)


class StopBody(BaseModel):
    pid: int
    start_ts: Optional[float] = None  # from the GET live row the operator confirmed (L4)
    reason: str = Field(default="", max_length=MAX_REASON_LEN)


def _who(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("")
def batch_control_state(config: Optional[str] = None) -> JSONResponse:
    try:
        configs = whitelist.list_configs()
        config_path = None
        selected_name = None
        if config:
            config_path = whitelist.resolve_config_name(config)
            selected_name = config if config_path else None
        elif configs:
            config_path = configs[0]["path"]
            selected_name = configs[0]["name"]
        permissives = evaluate_permissives(state_builder.permissive_state(config_path))
        return JSONResponse({
            "configs": configs,
            "permissives": permissives,
            "live": state_builder.live_batches(),
            "selected_config_name": selected_name,
            "checkpoint": state_builder.checkpoint_info(config_path),
        }, headers={"Cache-Control": "no-store"})
    except Exception:
        logger.exception("plant batch control state failed")
        return JSONResponse({"error": "trạng thái điều khiển batch lỗi, xem log tdm-backend"},
                            status_code=500)


@router.post("/start")
def start_batch(body: StartBody, request: Request,
                x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    who = _who(request)
    config_path = whitelist.resolve_config_name(body.config)
    if config_path is None:
        append_audit({"ts": time.time(), "action": "start", "who": who, "accepted": False,
                      "config": body.config, "reason": body.reason,
                      "error": "config không nằm trong whitelist"})
        raise HTTPException(status_code=400, detail="config không nằm trong whitelist")

    # H2: the whole evaluate -> systemd-run -> pid-visible sequence runs under one lock
    # (process-wide thread lock + cross-process fcntl file lock), so a second concurrent
    # start (another tab, a curl retry, the Gradio launcher's own path if it ever takes
    # this lock too) either waits and then sees this one as the live batch via
    # `NO_LIVE_BATCH`, or genuinely runs first and this one blocks instead. Wrapping the
    # permissive re-check in the same try also means an exception there is audited (L3),
    # not an unhandled 500.
    try:
        with ops.start_lock():
            permissives = evaluate_permissives(state_builder.permissive_state(config_path))
            failures = blocking_failures(permissives)
            if failures:
                append_audit({"ts": time.time(), "action": "start", "who": who, "accepted": False,
                              "config": body.config, "pilot": body.pilot, "resume": body.resume,
                              "reason": body.reason, "failures": failures})
                return JSONResponse({"error": "bị chặn bởi permissive", "failures": failures},
                                    status_code=409)
            # own output folder per run (fresh start) or the newest unfinished run (resume)
            if body.resume:
                run = run_dirs.latest_unfinished_run(body.config)
                if run is None:
                    append_audit({"ts": time.time(), "action": "start", "who": who, "accepted": False,
                                  "config": body.config, "resume": True, "reason": body.reason,
                                  "error": "không có lần chạy dở để resume"})
                    return JSONResponse({"error": "không có lần chạy dở nào của config này để resume"},
                                        status_code=409)
                run_cfg, run_dir = run["config_path"], run["run_dir"]
            else:
                run_cfg, run_dir = run_dirs.new_run(config_path, body.config)
            result = ops.start_batch(run_cfg, body.pilot, body.resume)
            # GPU_FREE above only re-checked an unlocked snapshot; take the lease for
            # real now, still inside start_lock(), using the batch's own pid so it
            # self-expires the moment the batch exits (plan Bước 1). A refusal here
            # means an extremely tight race (the HMI/CLI loop grabbed it between the
            # permissive check and this line): stop what we just started rather than
            # leave two GPU users running.
            if result["ok"]:
                lease_ok, holder = gpu_lease.acquire(f"hmi-batch:{result['unit']}", body.config, result["pid"])
                if not lease_ok:
                    ops.stop_batch(result["pid"], [result["pid"]])
                    who = (holder or {}).get("owner", "không rõ")
                    result = {"ok": False, "unit": result["unit"], "pid": result["pid"],
                              "error": f"GPU vừa bị {who} giữ ngay trước khi xin phiếu, đã dừng batch vừa khởi chạy"}
    except Exception:
        logger.exception("plant batch control start failed")
        append_audit({"ts": time.time(), "action": "start", "who": who, "accepted": False,
                      "config": body.config, "reason": body.reason, "error": "exception khi khởi chạy"})
        raise HTTPException(status_code=500, detail="khởi chạy batch lỗi, xem log tdm-backend")

    append_audit({"ts": time.time(), "action": "start", "who": who, "accepted": result["ok"],
                  "config": body.config, "pilot": body.pilot, "resume": body.resume,
                  "reason": body.reason, "unit": result.get("unit"), "run_dir": str(run_dir),
                  "error": result.get("error")})
    if not result["ok"]:
        return JSONResponse({"error": result["error"], "unit": result["unit"]}, status_code=500)
    return JSONResponse({"unit": result["unit"], "accepted": True, "run_dir": str(run_dir)})


@router.post("/stop")
def stop_batch(body: StopBody, request: Request,
               x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    who = _who(request)
    live = host.find_batch_processes()
    live_pids = [p["pid"] for p in live]

    # L4: a recycled pid (the operator's confirm dialog is a few seconds stale) must
    # never stop someone else's process; compare against the start_ts the GET response
    # carried for this pid, same slack as the telemetry collector's own pid-reuse guard.
    if body.start_ts is not None:
        entry = next((p for p in live if p["pid"] == body.pid), None)
        if entry is None or abs(entry["start_ts"] - body.start_ts) > PID_REUSE_SLACK_S:
            msg = "pid đã bị tái sử dụng hoặc không còn là batch đã xác nhận"
            append_audit({"ts": time.time(), "action": "stop", "who": who, "accepted": False,
                          "pid": body.pid, "reason": body.reason, "error": msg})
            return JSONResponse({"error": msg}, status_code=409)

    try:
        result = ops.stop_batch(body.pid, live_pids)
    except Exception:
        logger.exception("plant batch control stop failed")
        append_audit({"ts": time.time(), "action": "stop", "who": who, "accepted": False,
                      "pid": body.pid, "reason": body.reason, "error": "exception khi dừng"})
        raise HTTPException(status_code=500, detail="dừng batch lỗi, xem log tdm-backend")

    append_audit({"ts": time.time(), "action": "stop", "who": who, "accepted": result["ok"],
                  "pid": body.pid, "unit": result.get("unit"), "reason": body.reason,
                  "error": result.get("error")})
    if not result["ok"]:
        return JSONResponse({"error": result["error"]}, status_code=409)
    return JSONResponse({"accepted": True, "unit": result["unit"]})


@router.get("/audit")
def audit(limit: int = 50) -> JSONResponse:
    try:
        return JSONResponse(read_audit(min(limit, 500)))
    except Exception:
        logger.exception("plant batch control audit read failed")
        return JSONResponse({"error": "audit lỗi, xem log tdm-backend"}, status_code=500)
