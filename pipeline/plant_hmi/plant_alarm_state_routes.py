"""ISA-18.2 alarm ack/shelve API (phase 6B).

  POST /plant-hmi/api/alarms/ack       {key, reason?}          # key = occurrence (code|tag|pid|since)
  POST /plant-hmi/api/alarms/ack-all   {keys, reason?}
  POST /plant-hmi/api/alarms/shelve    {key, minutes, reason}   # key = point (code|tag|pid); minutes in {15,60,480}
  POST /plant-hmi/api/alarms/unshelve  {key}                    # key = point (code|tag|pid)
  GET  /plant-hmi/api/alarms/state                              # raw store, for debugging

Same CSRF guard as every other Plant HMI write route (`require_trusted_request`);
`who` is the client IP (no login, per the user's decision). A journal write failure
never fails the request (rule L3): the ack/shelve state is already persisted by the
time the journal line is attempted. Every key is validated against the store itself
(rule M2): an unknown/stale key gets 404, not a silent no-op.
"""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import plant_alarm_state as state
from . import plant_historian_store as historian
from .plant_request_guards import require_trusted_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alarms")


class AckBody(BaseModel):
    key: str = Field(..., max_length=state.MAX_KEY_LEN)
    reason: str = Field(default="", max_length=200)


class AckAllBody(BaseModel):
    keys: List[str] = Field(..., max_length=state.MAX_ACK_ALL_KEYS)
    reason: str = Field(default="", max_length=200)


class ShelveBody(BaseModel):
    key: str = Field(..., max_length=state.MAX_KEY_LEN)
    minutes: int
    reason: str = Field(..., max_length=200)


class UnshelveBody(BaseModel):
    key: str = Field(..., max_length=state.MAX_KEY_LEN)


def _occurrence_parts(key: str):
    """`code|tag|pid|since` -> (code, tag, pid); tolerant of a malformed/legacy key."""
    parts = key.split("|", 3)
    return _common_parts(parts)


def _point_parts(key: str):
    """`code|tag|pid` -> (code, tag, pid); tolerant of a malformed/legacy key."""
    parts = key.split("|", 2)
    return _common_parts(parts)


def _common_parts(parts):
    code = parts[0] if len(parts) > 0 and parts[0] else None
    tag = parts[1] if len(parts) > 1 and parts[1] != "None" else None
    pid_raw = parts[2] if len(parts) > 2 else None
    try:
        pid = int(pid_raw) if pid_raw not in (None, "None") else None
    except ValueError:
        pid = None
    return code, tag, pid


def _journal(ts: float, code: Optional[str], tag: Optional[str], pid: Optional[int],
             state_text: str, message: Optional[str]) -> None:
    try:
        historian.insert_alarm_journal(ts, code or "?", tag, None, pid, state_text, message)
    except Exception:
        logger.exception("plant alarm journal write failed (state already updated): %s %s", state_text, code)


def _who(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _not_found(exc: state.UnknownAlarmKey) -> HTTPException:
    return HTTPException(status_code=404, detail="báo động không tồn tại hoặc đã hết, tải lại trang")


@router.post("/ack")
def ack(body: AckBody, request: Request,
        x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    try:
        entry = state.ack(body.key, _who(request), body.reason)
    except state.UnknownAlarmKey as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("plant alarm ack failed")
        raise HTTPException(status_code=500, detail="xác nhận báo động lỗi, xem log tdm-backend")
    code, tag, pid = _occurrence_parts(body.key)
    _journal(entry["acked_at"], code, tag, pid, "acked", body.reason or None)
    return JSONResponse({"key": body.key, **entry})


@router.post("/ack-all")
def ack_all(body: AckAllBody, request: Request,
            x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    try:
        acked = state.ack_all(body.keys, _who(request), body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("plant alarm ack-all failed")
        raise HTTPException(status_code=500, detail="xác nhận tất cả lỗi, xem log tdm-backend")
    now = time.time()
    for key in acked:
        code, tag, pid = _occurrence_parts(key)
        _journal(now, code, tag, pid, "acked", body.reason or None)
    return JSONResponse({"acked": acked})


@router.post("/shelve")
def shelve(body: ShelveBody, request: Request,
           x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    try:
        entry = state.shelve(body.key, body.minutes, _who(request), body.reason)
    except state.UnknownAlarmKey as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("plant alarm shelve failed")
        raise HTTPException(status_code=500, detail="tạm tắt báo động lỗi, xem log tdm-backend")
    code, tag, pid = _point_parts(body.key)
    _journal(time.time(), code, tag, pid, "shelved", body.reason or None)
    return JSONResponse({"key": body.key, **entry})


@router.post("/unshelve")
def unshelve(body: UnshelveBody, request: Request,
             x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    try:
        existed = state.unshelve(body.key)
    except state.UnknownAlarmKey as exc:
        raise _not_found(exc) from exc
    except Exception:
        logger.exception("plant alarm unshelve failed")
        raise HTTPException(status_code=500, detail="bỏ tạm tắt lỗi, xem log tdm-backend")
    code, tag, pid = _point_parts(body.key)
    _journal(time.time(), code, tag, pid, "unshelved", None)
    return JSONResponse({"key": body.key, "unshelved": existed})


@router.get("/state")
def get_state() -> JSONResponse:
    try:
        return JSONResponse(state.read_store())
    except Exception:
        logger.exception("plant alarm state read failed")
        return JSONResponse({"error": "alarm state lỗi, xem log tdm-backend"}, status_code=500)
