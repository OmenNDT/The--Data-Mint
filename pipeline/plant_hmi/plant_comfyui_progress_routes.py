"""HTTP route for the P-601 (ComfyUI) black-box progress panel.

  GET /plant-hmi/api/comfyui/progress   current phase/node/step JSON (read-only)

Mounted by the main `attach_plant_hmi` alongside `start_observer()`; this module
owns only the route, not the app wiring (see plan phase 4 file ownership).
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .plant_comfyui_progress_observer import current_progress

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/comfyui/progress")
def comfyui_progress():
    try:
        return JSONResponse(current_progress(), headers={"Cache-Control": "no-store"})
    except Exception:  # the HMI must never take down the launcher
        logger.exception("plant-hmi comfyui progress failed")
        return JSONResponse({"error": "comfyui progress lỗi, xem log tdm-backend"}, status_code=500)
