"""Compose routes for the "Tạo mẻ mới" form (phase 6B), split out of
`plant_batch_control_routes.py` purely to keep that file under the 200-line
guideline. Included into that module's router (same `/api/control/batch`
prefix), so `plant_hmi_routes.py` needs no change.

  GET  /plant-hmi/api/control/batch/compose-options    defects/defaults for a base config
  POST /plant-hmi/api/control/batch/compose            {name, base_config, total_images,
                                                         distribution, backgrounds_dir, reason, overwrite}

Same CSRF guard and audit-every-attempt pattern as start/stop.
"""

import logging
import time
from typing import Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import plant_batch_compose as compose
from . import plant_batch_config_whitelist as whitelist
from .plant_batch_audit import append_audit
from .plant_request_guards import require_trusted_request

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_REASON_LEN = 200


class ComposeBody(BaseModel):
    name: str
    base_config: str
    total_images: int
    distribution: Dict[str, float]
    backgrounds_dir: Optional[str] = None
    reason: str = Field(default="", max_length=MAX_REASON_LEN)
    overwrite: bool = False


def _who(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/compose-options")
def compose_options(base: Optional[str] = None) -> JSONResponse:
    try:
        configs = whitelist.list_configs()
        if not base:
            base = configs[0]["name"] if configs else None
        if not base:
            return JSONResponse({"error": "không có config nào trong whitelist"}, status_code=404)
        return JSONResponse(compose.compose_options(base))
    except compose.ComposeError as e:
        return JSONResponse({"error": str(e), "failures": e.errors}, status_code=400)
    except Exception:
        logger.exception("plant batch compose-options failed")
        return JSONResponse({"error": "đọc compose-options lỗi, xem log tdm-backend"}, status_code=500)


@router.post("/compose")
def compose_batch(body: ComposeBody, request: Request,
                   x_plant_hmi: Optional[str] = Header(default=None)) -> JSONResponse:
    require_trusted_request(request, x_plant_hmi)
    who = _who(request)
    try:
        result = compose.compose_config(
            name=body.name, base_config=body.base_config, total_images=body.total_images,
            distribution=body.distribution, backgrounds_dir=body.backgrounds_dir,
            reason=body.reason, overwrite=body.overwrite, who=who)
    except compose.ComposeError as e:
        append_audit({"ts": time.time(), "action": "compose", "who": who, "accepted": False,
                      "name": body.name, "base_config": body.base_config, "reason": body.reason,
                      "errors": e.errors})
        return JSONResponse({"error": str(e), "failures": e.errors}, status_code=400)
    except Exception:
        logger.exception("plant batch compose failed")
        append_audit({"ts": time.time(), "action": "compose", "who": who, "accepted": False,
                      "name": body.name, "base_config": body.base_config, "reason": body.reason,
                      "error": "exception khi tạo config"})
        raise HTTPException(status_code=500, detail="tạo config lỗi, xem log tdm-backend")

    append_audit({"ts": time.time(), "action": "compose", "who": who, "accepted": True,
                  "name": body.name, "base_config": body.base_config, "reason": body.reason,
                  "overwrite": body.overwrite, "config_name": result["config_name"], "counts": result["counts"]})
    return JSONResponse(result)
