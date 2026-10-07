"""Pure compute for the ComfyUI black-box progress panel (P-601).

`compute_comfy_progress(state, node_meta, now)` has no I/O: given the raw state
mutated by the websocket observer thread (see `plant_comfyui_progress_observer.py`)
it derives the dict the API/UI renders. Unknown values are `None` (never a faked
percentage) so the pure function is unit-testable with fixed inputs.

Real wire format (`tests/fixtures/comfyui-ws-sample.jsonl`, recorded live): a
prompt posted WITHOUT `client_id` only ever gets `status`/`progress`/
`progress_state` broadcast to unrelated `/ws` clients — `progress_state`
(per-node pending/running/finished/error) replaced the old `executing` event for
this case, and `execution_start/executing/execution_success/execution_error/
execution_cached` never arrive (`add_message(..., broadcast=False)` in
ComfyUI's `execution.py` only fires with a `client_id`).

M1: a foreign job (someone else's prompt, WITH a `client_id`, e.g. the web UI)
is unicast only to its own socket, so we never see its progress at all;
`status.queue_remaining` still reflects it and can stay above 0 forever once
ours is done. Two fixes: (1) our prompt is finalized as soon as every node in
its own `progress_state` is `finished`/`error`, never waiting on
`queue_remaining==0`; (2) `phase` reports `busy_foreign` (ComfyUI busy, nothing
of ours to show) instead of a stale/wrong `executing`, once the queue is
non-empty but none of our own progress messages arrived within a grace window.
"""

from typing import Dict, List, Optional

MAX_COMPLETIONS = 500  # bounded memory; a completion outlives the 1h window prune
COMPLETION_WINDOW_S = 3600.0
BUSY_FOREIGN_GRACE_S = 10.0  # grace before "busy_foreign": avoids flicker just after our own prompt is queued


def new_state() -> Dict:
    """Initial raw state for the observer (mutated under its own lock)."""
    return {
        "connected": False,
        "last_event_ts": None,
        "last_progress_event_ts": None,  # last progress/progress_state WE received
        "queue_remaining": None,
        "prompt_id": None,
        "prompt_start_ts": None,
        "prompt_counted": False,
        "node": None,
        "step_seen": False,
        "progress": None,       # {"value", "max", "ts"}
        "progress_prev": None,  # previous sample, for it/s
        "completions": [],      # list[float] timestamps of finished prompts
        "last_prompt_s": None,
    }


def prune_completions(completions: List[float], now: float) -> List[float]:
    cutoff = now - COMPLETION_WINDOW_S
    return [t for t in completions if t >= cutoff][-MAX_COMPLETIONS:]


def finalize_current_prompt(state: Dict, now: float, count: bool = True) -> None:
    """Record the in-flight prompt as completed (idempotent per prompt).
    `count=False` closes the tracking without adding to `prompts_1h`/
    `last_prompt_s` (L6: a prompt orphaned by a socket drop is unresolved,
    not a measured completion)."""
    if state["prompt_id"] is not None and not state["prompt_counted"]:
        if count:
            start = state.get("prompt_start_ts")
            if start:
                state["last_prompt_s"] = now - start
            state["completions"] = prune_completions(state["completions"] + [now], now)
    state["prompt_counted"] = True


def _clear_tracking(state: Dict) -> None:
    state["prompt_id"] = None
    state["prompt_start_ts"] = None
    state["node"] = None
    state["progress"] = None
    state["progress_prev"] = None
    state["step_seen"] = False


def start_new_prompt(state: Dict, prompt_id: str, now: float) -> None:
    """A `progress`/`progress_state` message references a prompt_id we have not
    seen yet: close out whatever was tracked (defensive, normally already closed
    by node-completion or a `status` queue_remaining=0) and start the new one."""
    if prompt_id != state["prompt_id"]:
        finalize_current_prompt(state, now)
        _clear_tracking(state)
        state["prompt_id"] = prompt_id
        state["prompt_start_ts"] = now
        state["prompt_counted"] = False


def on_disconnect(state: Dict, now: float) -> None:
    """The websocket dropped: whatever was tracked is unresolved (L6), and the
    panel must show "not observable" rather than a frozen last-known node."""
    finalize_current_prompt(state, now, count=False)
    _clear_tracking(state)
    state["connected"] = False


def compute_comfy_progress(state: Dict, node_meta: Dict[str, Dict[str, str]], now: float) -> Dict:
    """Pure projection of raw observer state into the API/UI dict shape."""
    connected = bool(state.get("connected"))
    prompt_id = state.get("prompt_id")
    queue_remaining = state.get("queue_remaining")
    last_progress_ts = state.get("last_progress_event_ts")

    if prompt_id is not None:
        phase = "executing"
    elif queue_remaining not in (None, 0) and (
        last_progress_ts is None or now - last_progress_ts > BUSY_FOREIGN_GRACE_S
    ):
        phase = "busy_foreign"  # ComfyUI is busy, but not with a prompt we can see
    else:
        phase = "idle"

    node = node_title = node_class = step = steps = it_s = elapsed_s = None
    step_seen = False
    if phase == "executing":
        node = state.get("node")
        meta = node_meta.get(node) if node else None
        node_title = meta.get("title") if meta else None
        node_class = meta.get("class_type") if meta else None
        step_seen = bool(state.get("step_seen"))
        progress = state.get("progress")
        prev = state.get("progress_prev")
        if progress:
            step, steps = progress.get("value"), progress.get("max")
            if prev:
                dt = progress.get("ts", 0) - prev.get("ts", 0)
                dv = (progress.get("value") or 0) - (prev.get("value") or 0)
                if dt > 0 and dv >= 0:
                    it_s = dv / dt
        start_ts = state.get("prompt_start_ts")
        if start_ts:
            elapsed_s = max(0.0, now - start_ts)

    completions = prune_completions(state.get("completions") or [], now)

    return {
        "connected": connected,
        "phase": phase,
        "prompt_id": prompt_id if phase == "executing" else None,
        "node": node,
        "node_title": node_title,
        "node_class": node_class,
        "step": step,
        "steps": steps,
        "step_seen": step_seen,
        "it_s": it_s,
        "elapsed_s": elapsed_s,
        "last_event_ts": state.get("last_event_ts"),
        "last_prompt_s": state.get("last_prompt_s"),
        "prompts_1h": len(completions),
    }


def apply_status(state: Dict, queue_remaining: Optional[int], now: float) -> None:
    """`status` event: only `exec_info.queue_remaining` is meaningful here.
    Zero means ComfyUI's own queue is drained: a reliable but not the ONLY
    "our prompt finished" signal (see `apply_progress_state` for the M1 fix
    that does not depend on the queue ever reaching zero)."""
    state["queue_remaining"] = queue_remaining
    if queue_remaining == 0:
        finalize_current_prompt(state, now)
        _clear_tracking(state)


def apply_progress_state(state: Dict, prompt_id: Optional[str], nodes: Dict, now: float) -> None:
    """`progress_state` event: per-node pending/running/finished/error map."""
    if not prompt_id:
        return
    state["last_progress_event_ts"] = now
    start_new_prompt(state, prompt_id, now)
    nodes = nodes or {}
    for node_id, entry in nodes.items():
        if isinstance(entry, dict) and entry.get("state") == "running":
            state["node"] = str(node_id)
            break
    # M1: our prompt is done once every node we have heard about is no longer
    # pending/running, regardless of ComfyUI's overall queue (a foreign job
    # queued behind ours keeps `queue_remaining` above 0 forever from our view).
    if nodes and all(isinstance(e, dict) and e.get("state") in ("finished", "error")
                      for e in nodes.values()):
        finalize_current_prompt(state, now)
        _clear_tracking(state)


def apply_progress(state: Dict, prompt_id: Optional[str], node: Optional[str],
                    value, max_value, now: float) -> None:
    """`progress` event: per-step value/max of the sampling node (most precise source for step/steps/it_s)."""
    state["last_progress_event_ts"] = now
    if prompt_id:
        start_new_prompt(state, prompt_id, now)
    if node is not None:
        state["node"] = str(node)
    if isinstance(value, (int, float)) and isinstance(max_value, (int, float)):
        state["progress_prev"] = state.get("progress")
        state["progress"] = {"value": value, "max": max_value, "ts": now}
        state["step_seen"] = True
