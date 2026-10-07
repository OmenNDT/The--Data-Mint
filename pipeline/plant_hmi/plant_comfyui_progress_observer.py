"""Read-only ComfyUI websocket observer for the P-601 black-box panel.

The batch pipeline posts prompts to ComfyUI WITHOUT a `client_id`
(`comfyui-rest-api-client.py`), so ComfyUI broadcasts `status`/`progress`/
`progress_state` to every `/ws` client (see `plant_comfyui_progress_state.py` for
why `executing`/`execution_start`/`execution_success` never arrive in that case,
and how a foreign job with its own `client_id` stays invisible to us). This
module only listens: it never posts a prompt, never touches the pipeline.

`start_observer()` is idempotent (safe to call from every code path that mounts
the router). `current_progress()` never raises and never blocks on the network;
it reads the last state the background thread computed.
"""

import json
import threading
import time
import uuid
from typing import Dict, Optional

try:
    import websocket  # websocket-client
except ImportError:  # dependency not installed yet: panel just says "unknown"
    websocket = None

from .plant_comfyui_progress_state import (
    apply_progress,
    apply_progress_state,
    apply_status,
    compute_comfy_progress,
    new_state,
    on_disconnect,
)
from .plant_comfyui_workflow_meta import load_node_meta

RECONNECT_FAST_S = 3.0    # L5: retry quickly right after a disconnect...
RECONNECT_FAST_WINDOW_S = 60.0
RECONNECT_SLOW_S = 60.0  # ...then stop hammering a server that stays down
RECV_TIMEOUT_S = 30.0    # idle recv timeout; connection itself stays open


class _ComfyProgressObserver:
    """One background thread, one mutable state dict behind a lock. All network
    and parsing errors are swallowed here (rule: telemetry must never break the
    job, and here there is no job to break, but a leaked exception would still
    kill the daemon thread silently and freeze the panel at its last value)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = new_state()
        self._node_meta: Dict[str, Dict[str, str]] = {}
        self._start_lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._started = True
            threading.Thread(target=self._run_forever, daemon=True,
                              name="plant-comfy-progress-observer").start()

    def current(self) -> Dict:
        with self._lock:
            state_copy = dict(self._state)
            state_copy["completions"] = list(self._state["completions"])
            meta = dict(self._node_meta)
        try:
            return compute_comfy_progress(state_copy, meta, time.time())
        except Exception as exc:  # a compute bug must degrade this panel only
            return {"connected": False, "phase": "idle", "error": f"{type(exc).__name__}: {exc}"[:200]}

    # -- background thread -------------------------------------------------

    def _read_config(self):
        """host/port/workflow_path from batch-config.yaml; defaults keep the
        observer useful even if the YAML is missing or malformed."""
        try:
            from .plant_production_readers import load_batch_config, section
            cfg = load_batch_config(None)
            comfy = section(cfg, "comfyui")
            host = comfy.get("host") or "127.0.0.1"
            port = comfy.get("port") or 8188
            workflow_path = comfy.get("workflow_path")
        except Exception:
            host, port, workflow_path = "127.0.0.1", 8188, None
        return host, port, workflow_path

    def _run_forever(self) -> None:
        disconnected_since: Optional[float] = None
        while True:
            connected_ok = False
            try:
                host, port, workflow_path = self._read_config()
                meta = load_node_meta(workflow_path)
                if meta:
                    self._node_meta = meta
                client_id = f"plant-hmi-observer-{uuid.uuid4().hex[:12]}"
                url = f"ws://{host}:{port}/ws?clientId={client_id}"
                connected_ok = self._connect_and_listen(url)
            except Exception:
                connected_ok = False
            now = time.time()
            with self._lock:
                on_disconnect(self._state, now)
            # L5: 3 s retries for the first minute after a disconnect, 60 s after
            if connected_ok:
                disconnected_since = None
            elif disconnected_since is None:
                disconnected_since = now
            if disconnected_since is None or now - disconnected_since < RECONNECT_FAST_WINDOW_S:
                time.sleep(RECONNECT_FAST_S)
            else:
                time.sleep(RECONNECT_SLOW_S)

    def _connect_and_listen(self, url: str) -> bool:
        """Returns True if a session was actually established (even if it later
        dropped): that resets the L5 fast-retry clock, unlike a failed handshake."""
        if websocket is None:
            time.sleep(RECONNECT_SLOW_S)  # dependency missing: stop hot-looping
            return False
        try:
            ws = websocket.create_connection(url, timeout=10)
        except Exception:
            return False
        session_ok = True
        try:
            with self._lock:
                self._state["connected"] = True
            ws.settimeout(RECV_TIMEOUT_S)
            while True:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue  # no traffic for a while; connection itself is fine
                if raw is None or raw == "":
                    break
                if isinstance(raw, (bytes, bytearray)):
                    continue  # binary preview frame (image bytes), not progress data
                self._handle_message(raw)
        finally:
            try:
                ws.close()
            except Exception:
                pass
        return session_ok

    def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict):
            return
        event, data = msg.get("type"), msg.get("data")
        if not isinstance(data, dict):
            return
        now = time.time()
        try:
            with self._lock:
                self._state["last_event_ts"] = now
                if event == "status":
                    status = data.get("status") or {}
                    exec_info = status.get("exec_info") or {}
                    qr = exec_info.get("queue_remaining")
                    apply_status(self._state, qr if isinstance(qr, int) else None, now)
                elif event == "progress_state":
                    apply_progress_state(self._state, data.get("prompt_id"), data.get("nodes"), now)
                elif event == "progress":
                    apply_progress(self._state, data.get("prompt_id"), data.get("node"),
                                    data.get("value"), data.get("max"), now)
                # other event types (executed, execution_error, ...) only refresh last_event_ts:
                # they require a client_id we never send, so they are not expected here, but a
                # ComfyUI version change sending them anyway must not crash the observer.
        except Exception:
            pass  # a single malformed message must never take down the observer thread


_observer = _ComfyProgressObserver()


def start_observer() -> None:
    """Start the background websocket listener once; safe to call repeatedly
    (Gradio launcher, CLI, systemd-run all mount the router independently)."""
    _observer.start()


def current_progress() -> Dict:
    """Never raises, never blocks on the network. `{"connected": False, ...}`
    until the first successful connection."""
    return _observer.current()
