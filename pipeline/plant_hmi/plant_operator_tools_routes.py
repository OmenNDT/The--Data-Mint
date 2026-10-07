"""Routes for the two operator tool buttons (output folders, ComfyUI on/off).

  GET  /plant-hmi/api/control/tools/runs        newest per-run output folders
  POST /plant-hmi/api/control/tools/open        {name}  show a run folder on this machine's desktop
  GET  /plant-hmi/api/control/tools/comfyui     unit + HTTP state, batch running?
  POST /plant-hmi/api/control/tools/comfyui     {action: start|stop, reason}
  POST /plant-hmi/api/control/tools/evaluate    {name}  realism check of one run folder (detached)
  GET  /plant-hmi/api/control/tools/evaluate?name=   state + newest result summary

Every POST uses the shared CSRF/DNS-rebinding guard and is written to the batch audit.
"""

import time
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import plant_operator_tools as tools
from . import plant_production_readers as production
from . import plant_run_evaluation as evaluation
from . import plant_slow_probes as probes
from .plant_batch_audit import append_audit
from .plant_request_guards import require_trusted_request

router = APIRouter(prefix="/api/control/tools")


class OpenBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ComfyBody(BaseModel):
    action: Literal["start", "stop"]
    reason: str = Field(default="", max_length=200)


def _comfy_http_ok() -> Optional[bool]:
    cfg = production.section(production.load_batch_config(None), "comfyui")
    try:
        port = int(cfg.get("port") or 8188)
    except (TypeError, ValueError):
        port = 8188
    return probes.comfyui(str(cfg.get("host") or "127.0.0.1"), port).get("ok")


@router.get("/runs")
def runs() -> JSONResponse:
    return JSONResponse({"root": str(tools.RUNS_ROOT), "runs": tools.list_runs()},
                        headers={"Cache-Control": "no-store"})


@router.post("/open")
def open_run(body: OpenBody, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    require_trusted_request(request, x_plant_hmi)
    path = tools.resolve_run(body.name)
    if path is None:
        raise HTTPException(status_code=404, detail="không có thư mục lần chạy này")
    error = tools.open_folder(path)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return JSONResponse({"opened": str(path)})


@router.get("/comfyui")
def comfyui_state() -> JSONResponse:
    return JSONResponse(tools.comfy_state(_comfy_http_ok()), headers={"Cache-Control": "no-store"})


@router.post("/comfyui")
def comfyui_toggle(body: ComfyBody, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    require_trusted_request(request, x_plant_hmi)
    who = request.client.host if request.client else "unknown"
    error = tools.comfy_start() if body.action == "start" else tools.comfy_stop()
    append_audit({"ts": time.time(), "action": f"comfyui_{body.action}", "who": who,
                  "accepted": error is None, "reason": body.reason, "error": error})
    if error:
        status = 409 if "batch" in error else 500
        raise HTTPException(status_code=status, detail=error)
    return JSONResponse({"ok": True, "action": body.action})


@router.post("/evaluate")
def evaluate_run(body: OpenBody, request: Request, x_plant_hmi: Optional[str] = Header(default=None)):
    require_trusted_request(request, x_plant_hmi)
    path = tools.resolve_run(body.name)
    if path is None:
        raise HTTPException(status_code=404, detail="không có thư mục lần chạy này")
    return JSONResponse({"run_id": evaluation.start(path, body.name)})


@router.get("/evaluate")
def evaluation_state(name: str) -> JSONResponse:
    if tools.resolve_run(name) is None:
        raise HTTPException(status_code=404, detail="không có thư mục lần chạy này")
    return JSONResponse(evaluation.status(name), headers={"Cache-Control": "no-store"})
