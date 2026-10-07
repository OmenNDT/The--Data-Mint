# Phase 4 report: P-601 ComfyUI black-box progress panel (incl. review fixes)

## Ground-truth correction vs spec (still holds after fixes)

Recorded 1077 real messages from `ws://127.0.0.1:8188/ws` during a live pilot
batch. Traced ComfyUI source: `execution_start/executing/execution_success/
execution_error/execution_cached` all require a `client_id` to be sent at all
(`add_message(..., broadcast=False)`); a prompt posted without one (our
pipeline) only ever gets `status`/`progress`/`progress_state` broadcast. Built
around these 3 real events.

## Review-fix round (M1, L5, L6, L9 + new fields)

- **M1 (foreign job invisibility)** — a job submitted by someone else WITH a
  `client_id` (e.g. the web UI) is unicast only to that socket; we never see
  its `progress`/`progress_state`. `status.queue_remaining` still reflects it,
  so it could stay above 0 forever from our view once our own prompt ended.
  Two independent fixes in `plant_comfyui_progress_state.py`:
  1. `apply_progress_state` now finalizes our tracked prompt the moment every
     node in its own `nodes` map is `finished`/`error`, never waiting on
     `queue_remaining==0`.
  2. `compute_comfy_progress` adds phase `"busy_foreign"`: reported when
     `queue_remaining` is non-zero/known but we have not received one of our
     own `progress`/`progress_state` events for `BUSY_FOREIGN_GRACE_S=10s`
     (`state["last_progress_event_ts"]`). A 10 s grace window prevents
     flickering `busy_foreign` in the brief gap right after our own prompt
     gets queued and before its first `progress_state` arrives.
  - Did **not** implement the optional `GET /queue` HTTP confirmation (single-
    flight, 5 s TTL) — the two fixes above are pure, deterministic and fully
    unit-tested without it, and adding a network call into the hot polling
    path seemed like unjustified risk for a call explicitly marked optional.
    Flagging this as a deliberate scope cut, not an oversight.
- **L5 (reconnect backoff)** — changed from exponential 5→60s to the spec'd
  fixed schedule: retry every 3 s for the first 60 s after a disconnect, then
  every 60 s (`RECONNECT_FAST_S=3.0`, `RECONNECT_FAST_WINDOW_S=60.0`,
  `RECONNECT_SLOW_S=60.0` in `plant_comfyui_progress_observer.py`). The clock
  resets whenever `_connect_and_listen` reports a session was actually
  established (even if it dropped moments later).
- **L6 (disconnect must not count an in-flight prompt)** — new pure function
  `on_disconnect(state, now)`: finalizes with `count=False` (no `prompts_1h`
  bump, no `last_prompt_s` write) and clears all tracking fields + `connected`.
  Called from `_run_forever` after every connect attempt/session end,
  regardless of success, so a genuinely dropped live session is also cleared.
- **L9 (panel must not throw on a malformed prompt_id)** — panel JS now uses
  `String(data.prompt_id).slice(0, 8)` instead of `data.prompt_id.slice(...)`.
- **New dict fields** — `step_seen` (bool: at least one `progress` tick seen
  for the current prompt — main's alarm can use this to give LO severity while
  a loader node runs and no step has ticked yet) and `node_class` (the node's
  `class_type`, independent of `node_title` which may be a custom `_meta.title`
  in a future workflow). Panel JS shows "chưa có bước đo (đang tải/ chạy node
  một lần)" instead of a fake 0% bar when `step_seen` is false.

## File layout change

Split the workflow-JSON node-metadata loader out of the observer into its own
tiny file, `pipeline/plant_hmi/plant_comfyui_workflow_meta.py` (38 lines,
`load_node_meta(workflow_path) -> Dict[str, Dict[str,str]]`), purely to keep
`plant_comfyui_progress_observer.py` under the 200-line budget after adding the
L5/L6 logic. This is a new file within my own phase-4 ownership (not touching
main's or phase-5's files), flagging it since it wasn't in the original file
list.

## Final dict shape (`current_progress()` / `GET /plant-hmi/api/comfyui/progress`)

```
{connected: bool, phase: "idle"|"executing"|"busy_foreign",
 prompt_id: str|None, node: str|None, node_title: str|None, node_class: str|None,
 step: int|None, steps: int|None, step_seen: bool,
 it_s: float|None, elapsed_s: float|None,
 last_event_ts: float|None, last_prompt_s: float|None, prompts_1h: int}
```
When `phase != "executing"` (`idle` or `busy_foreign`), all of
`prompt_id/node/node_title/node_class/step/steps/it_s/elapsed_s` are `None` and
`step_seen` is `False` (tested). `busy_foreign` is a NEW value main's
`COMFY_STALLED` alarm condition should treat the same as `idle` (no
"executing" claim to stall-check) — only `phase=="executing"` should ever be
candidate for `COMFY_STALLED`.

## Files (all under 200 lines, py_compile / node --check clean)

- `pipeline/plant_hmi/plant_comfyui_progress_state.py` (199) — pure functions,
  rewritten: `new_state`, `finalize_current_prompt(state, now, count=True)`,
  `_clear_tracking`, `start_new_prompt`, `on_disconnect`, `apply_status`,
  `apply_progress_state`, `apply_progress`, `compute_comfy_progress`.
- `pipeline/plant_hmi/plant_comfyui_progress_observer.py` (191) — `start_observer()`
  (idempotent), `current_progress()` (never raises/blocks); new L5 backoff
  schedule; calls `on_disconnect` after every session end.
- `pipeline/plant_hmi/plant_comfyui_workflow_meta.py` (38, new) —
  `load_node_meta(workflow_path)`.
- `pipeline/plant_hmi/plant_comfyui_progress_routes.py` (27, unchanged) —
  `GET /api/comfyui/progress`.
- `pipeline/plant_hmi/static/plant-hmi-comfyui-progress-panel.js` (74) —
  `initComfyProgressPanel(container)`; handles `busy_foreign`, `step_seen`,
  `String(prompt_id)`.
- `pipeline/plant_hmi/static/plant-hmi-comfyui-progress.css` (24, unchanged).
- `pipeline/tests/test-plant-hmi-comfyui-progress.py` (187, 12 tests) — added
  `test_all_nodes_finished_finalizes_without_waiting_for_queue_zero`,
  `test_foreign_job_keeps_us_out_of_executing` (M1),
  `test_disconnect_mid_prompt_does_not_count_it_l6` (L6); updated `NODE_META`
  fixture shape and idle-field assertions for `node_class`/`step_seen`.

## Verification

- All 12 tests in my suite pass; py_compile and `node --check` clean.
- Re-ran the other 3 suites I don't own but must not break:
  `test-plant-hmi-alarm-rules.py` (18 OK), `test-plant-hmi-telemetry.py`
  (16 OK — hit one transient `AttributeError` mid-run because main was
  actively editing `plant_telemetry_collector.py` at that moment; passed
  clean 15 s later, not caused by my files), `test-plant-hmi-historian.py`
  (21 OK).
- 5th suite `test-plant-hmi-setpoints.py` (phase-5's own file) currently fails
  with 18 errors (`AttributeError: ... does not have the attribute
  'SETPOINTS_DIR'`) — this is phase-5's in-progress work on their own files,
  outside my ownership; re-checked 20 s apart, still failing, so likely
  genuinely mid-development rather than a save-timing artifact. Not touched.
- Live smoke test against the actually-running `tdm-comfyui` service (FastAPI
  `TestClient` + `start_observer()` + 3 s wait) returned 200 with the new
  field set (`node_class`, `step_seen` included, all `None`/`False` since idle).
- Did not restart any service, did not queue any prompt, did not touch
  `plant_alarm_rules.py` or any phase-5 file.

Status: DONE
Summary: M1/L5/L6/L9 fixed plus `step_seen`/`node_class` exposed, all in the
5 owned files (+ 1 new small helper module to stay under 200 lines); all 12
own tests pass, the other 3 non-owned suites I must not break also pass
(one transient failure during a concurrent edit by main, self-resolved).
Concerns: optional GET /queue confirmation deliberately not implemented
(pure logic already satisfies M1's acceptance criteria); phase-5's
test-plant-hmi-setpoints.py currently fails but is their own in-progress file,
not mine to fix — flagging so the coordinator knows before calling "all 5
suites pass" done.
