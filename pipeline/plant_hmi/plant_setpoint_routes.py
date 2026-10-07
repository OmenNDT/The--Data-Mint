"""Reverse-control API for the Plant HMI setpoint faceplate (phase 5).

  GET    /plant-hmi/api/control/setpoints          list of setpoint rows (SP, PV, limits)
  PUT    /plant-hmi/api/control/setpoints/{key}     write a new SP {value, reason}
  DELETE /plant-hmi/api/control/setpoints/{key}     clear the override {reason}, PV -> RECIPE
  GET    /plant-hmi/api/control/audit?limit=        change history, newest first

No login (user's decision). Two independent CSRF guards on every write (rule H1):
`X-Plant-HMI: 1` (a plain cross-site <form> cannot set a custom header), AND the
`Origin`/`Sec-Fetch-Site` request headers must agree the request is same-origin.
The header alone is not enough: some deployed CORS configs (e.g. Gradio) echo
back any Origin once the Host is not "localhost", so a malicious page could
still get a preflight-free custom-header request through in that configuration.
`updated_by`/`who` is the client IP (no login, per the user's decision).

PV (rule R2) is the process's OWN feedback, never the SP: the newest `kind=config`
record emitted by the live batch process after it resolved the value, guarded
against pid reuse (`ts >= process_start - 2s`). No live process or no record yet
renders `pv: null`, never the SP or the default.
"""

import logging
from typing import Dict, List, Optional

from .plant_request_guards import require_trusted_request
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from . import plant_host_readers as host
from . import plant_production_readers as production
from .plant_telemetry_collector import collector
from .plant_setpoints import REGISTRY, clear_setpoint, read_audit, read_store, set_setpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control")

PV_SOURCE_BADGE = {"env": "LOCAL", "setpoint": "REMOTE", "recipe": "RECIPE"}
MAX_AUDIT_LIMIT = 500


class SetpointWrite(BaseModel):
    value: StrictInt
    reason: str = Field(default="", max_length=200)


class SetpointClear(BaseModel):
    reason: str = Field(default="", max_length=200)


def _newest_live_process() -> Optional[Dict]:
    """The most recently started live batch process, or None."""
    procs = host.find_batch_processes()
    return procs[-1] if procs else None  # find_batch_processes() sorts by start_ts ascending


def _row(key: str, spec: Dict, live: Optional[Dict]) -> Dict:
    store_entry = read_store().get(key)
    store_value = store_entry.get("value") if isinstance(store_entry, dict) else None

    config_path = live.get("config_path") if live else None
    recipe_cfg = production.load_batch_config(config_path)
    section_name, field_name = spec["config"]
    recipe = production.section(recipe_cfg, section_name).get(field_name)

    sp = store_value if store_value is not None else recipe

    pv = pv_pid = pv_source = None
    if live is not None:
        record = collector.config_for(live["pid"], live["start_ts"]).get(key)
        if record is not None:
            pv = record.get("value")
            pv_pid = live["pid"]
            pv_source = PV_SOURCE_BADGE.get(record.get("source"))

    return {
        "key": key,
        "label": spec["label"],
        "unit": spec["unit"],
        "sp": sp,
        "pv": pv,
        "pv_pid": pv_pid,
        "pv_source": pv_source,
        "min": spec["min"],
        "max": spec["max"],
        "recipe": recipe,
        "updated_at": store_entry.get("updated_at") if isinstance(store_entry, dict) else None,
        "updated_by": store_entry.get("updated_by") if isinstance(store_entry, dict) else None,
        "reason": store_entry.get("reason") if isinstance(store_entry, dict) else None,
        "applies": spec["applies"],
    }


@router.get("/setpoints")
def list_setpoints() -> JSONResponse:
    try:
        collector.poll()  # rule L7: read fresh PV, don't rely on some other request's poll
        live = _newest_live_process()
        rows: List[Dict] = [_row(key, spec, live) for key, spec in REGISTRY.items()]
        return JSONResponse(rows)
    except Exception:
        logger.exception("plant control setpoints list failed")
        return JSONResponse({"error": "setpoints lỗi, xem log tdm-backend"}, status_code=500)


@router.put("/setpoints/{key}")
def write_setpoint(key: str, body: SetpointWrite, request: Request,
                    x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"setpoint không tồn tại: {key}")
    who = request.client.host if request.client else "unknown"
    try:
        entry = set_setpoint(key, body.value, who, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("plant control setpoint write failed")
        raise HTTPException(status_code=500, detail="ghi setpoint lỗi, xem log tdm-backend")
    return JSONResponse({"key": key, **entry})


@router.delete("/setpoints/{key}")
def delete_setpoint(key: str, body: SetpointClear, request: Request,
                     x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    """Rule M3: clear the stored override so the next batch resolves back to the
    recipe value (PV source becomes RECIPE); audit line records `new: null`."""
    require_trusted_request(request, x_plant_hmi)
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"setpoint không tồn tại: {key}")
    who = request.client.host if request.client else "unknown"
    try:
        clear_setpoint(key, who, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("plant control setpoint clear failed")
        raise HTTPException(status_code=500, detail="xoá setpoint lỗi, xem log tdm-backend")
    return JSONResponse({"key": key, "cleared": True})


@router.get("/audit")
def audit(limit: int = Query(50, ge=1, le=MAX_AUDIT_LIMIT)) -> JSONResponse:
    try:
        return JSONResponse(read_audit(limit))
    except Exception:
        logger.exception("plant control audit read failed")
        return JSONResponse({"error": "audit lỗi, xem log tdm-backend"}, status_code=500)

# Backward-compatible name: plant_realism_routes.py (added by another session) imports the
# pre-refactor private name. The guard itself now lives in plant_request_guards.py.
_require_trusted_request = require_trusted_request
