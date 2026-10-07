"""HTTP routes for the Plant HMI, attached to the FastAPI app Gradio already serves.

  GET /plant-hmi/                 P&ID page (static HTML)
  GET /plant-hmi/static/<file>    page assets (css/js)
  GET /plant-hmi/api/snapshot     level-1 snapshot JSON (read-only)
  GET /plant-hmi/api/events       telemetry flow records for particles (?since=epoch)

No new port: the routes live on the launcher's port 7860.
"""

import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .plant_history_routes import router as history_router
from .plant_historian_sampler import start_sampler
from .plant_comfyui_progress_observer import start_observer
from .plant_comfyui_progress_routes import router as comfy_progress_router
from .plant_setpoint_routes import router as setpoint_router
from .plant_batch_control_routes import router as batch_control_router
from .plant_alarm_state_routes import router as alarm_state_router
from .plant_operator_tools_routes import router as operator_tools_router
from .plant_snapshot_builder import build_snapshot
from .plant_telemetry_collector import collector

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
_ALLOWED_SUFFIX = {".css": "text/css", ".js": "text/javascript"}

router = APIRouter(prefix="/plant-hmi")


@router.get("", include_in_schema=False)
def _redirect():
    return RedirectResponse("/plant-hmi/")


@router.get("/", include_in_schema=False)
def page():
    return FileResponse(STATIC_DIR / "plant-hmi.html", media_type="text/html",
                        headers={"Cache-Control": "no-cache"})


@router.get("/static/{name}", include_in_schema=False)
def asset(name: str):
    # Flat directory, whitelisted suffixes: no path traversal possible
    path = STATIC_DIR / Path(name).name
    media = _ALLOWED_SUFFIX.get(path.suffix)
    if media is None or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})


@router.get("/api/snapshot")
def snapshot():
    try:
        return JSONResponse(build_snapshot(), headers={"Cache-Control": "no-store"})
    except Exception:  # the HMI must never take down the launcher
        logger.exception("plant-hmi snapshot failed")
        return JSONResponse({"error": "snapshot lỗi, xem log tdm-backend"}, status_code=500)


@router.get("/api/events")
def events(since: float = 0.0):
    """Flow records newer than `since` (max 500, last 15 min) for the particle layer.
    `ts` is server time so the client can align its clock."""
    try:
        collector.poll()
        return JSONResponse({**collector.events_since(since), "ts": time.time()},
                            headers={"Cache-Control": "no-store"})
    except Exception:
        logger.exception("plant-hmi events failed")
        return JSONResponse({"error": "events lỗi, xem log tdm-backend"}, status_code=500)


def attach_plant_hmi(app) -> None:
    """Register the routes ahead of Gradio's own routes so its catch-alls never shadow them."""
    before = len(app.router.routes)
    app.include_router(router)
    app.include_router(history_router, prefix="/plant-hmi")
    app.include_router(comfy_progress_router, prefix="/plant-hmi")
    app.include_router(setpoint_router, prefix="/plant-hmi")
    app.include_router(batch_control_router, prefix="/plant-hmi")
    app.include_router(alarm_state_router, prefix="/plant-hmi")
    app.include_router(operator_tools_router, prefix="/plant-hmi")
    try:  # realism loop page is optional: a broken import must never take the Plant HMI down
        from .plant_realism_routes import router as realism_router
        from .plant_realism_sensitivity_routes import router as realism_sensitivity_router
        app.include_router(realism_router, prefix="/plant-hmi")              # /plant-hmi/realism/
        app.include_router(realism_sensitivity_router, prefix="/plant-hmi")  # /plant-hmi/realism/api/sensitivity*
    except Exception:
        logger.exception("Realism page not mounted")
    added = app.router.routes[before:]
    del app.router.routes[before:]
    app.router.routes[0:0] = added
    start_sampler()
    start_observer()  # phase 4: read-only listener on ComfyUI's websocket
    logger.info("Plant HMI mounted at /plant-hmi/")
