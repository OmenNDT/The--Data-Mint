# Plant HMI phase 3 frontend — implementation + review-fix report

Plan: `plans/260926-2051-plant-hmi-phase3-historian-replay/plan.md`
Scope: `pipeline/plant_hmi/static/*` only (no Python touched, no services restarted/started).

## Round 1 — initial build

Files created:
- `plant-hmi-replay-clock.js` (59 lines) — virtual clock over [start,end], speeds x1/x10/x60/x600,
  per-frame wall-delta capped 250ms, auto-pause at end, reset on setRange.
- `plant-hmi-replay-derive.js` (94 lines) — incremental pure(ish) deriver: events → {produced,
  failed, running-per-unit, pendingIn}, shaped like the live snapshot.
- `plant-hmi-replay-controls.js` (162 lines) — run picker, event fetch, wires clock+deriver+
  particle layer, play/pause/seek/speed UI.
- `plant-hmi-trend-panel.js` (177 lines) — tag picker grouped by equipment, windows 1h/6h/24h/run,
  SVG polyline chart per tag with hover readout.
- `plant-hmi-alarm-journal.js` (82 lines) — table from `/api/history/alarms` with the same window
  selector.
- `plant-hmi-render-panels.js` (142 lines) — extracted from app.js to keep every file <200 lines:
  renderAlarms/renderBatches/renderUtilities/renderDetail/setConn + tiny DOM builder `h`.

Files edited:
- `plant-hmi-particle-layer.js` — added setMode('live'|'replay') + reset(); renderAt(T, serverNow)
  as the single frame-render primitive; STALE_S=330 cap independent of pid liveness; hasAlive flag
  gates ghost-pid removal until the first setAlivePids() call; job.retried flag resets a merged
  segment's err flag on a successful retry.
- `plant-hmi-event-stream.js` — since = body.cursor ?? body.ts (not last event ts); truncated
  handling resets particles + since=null; setServerTime called only here; resetEventStream() export.
- `plant-hmi-visible-polling.js` — setEnabled(bool) on the returned controller.
- `plant-hmi-app.js` — Live|Replay mode switch, reuses renderAll()/render* for both modes.
- `plant-hmi.html` / `plant-hmi.css` — mode switch bar, replay-card, trend/alarm-journal panels,
  responsive grid-lower row, dark-neumorphism styling for all new controls.

## Round 2 — code-review fixes (this pass)

- **H1** (particles deleted too early in replay): `renderAt()` only deletes finished/stale/ghost
  jobs when `mode === 'live'`; in replay it just skips drawing that frame. `place()` is a pure
  function of T, so backward seeks and replaying past the end show particles again without any
  extra bookkeeping.
- **H2** (Replay→Live→Replay loses particles): `plant-hmi-replay-controls.js` keeps
  `currentEvents` (the fetched run's events) in the controller closure and exposes `reactivate()`,
  which re-ingests them into the particle layer without a network round-trip. `app.js` calls
  `replay.reactivate()` inside `setMode('replay')` after a Live visit.
- **H3** (selectRun races): `selectRun()` uses a `loadSeq` request token, checked via a
  `stillCurrent()` closure before and after every paginated fetch, plus an `isReplayActive`
  callback passed from `app.js`. A superseded run pick or a mode switch away from Replay aborts
  both the fetch loop and the state application. `setMode`/`setParticleMode` on the particle layer
  is now called **only** from `app.js` (verified via grep — `replay-controls.js` no longer imports
  it at all).
- **Contract change** (`/api/history/events?run=&cursor=&limit=` → `{events, next_cursor, total}`):
  `fetchRunEvents()` rewritten for cursor pagination, `MAX_PAGES = 40`; when the cap is hit and more
  data remained, the status line shows `đã cắt bớt: X/total sự kiện`.
- **M1** (in-flight Live poll must not apply after switching to Replay): `visiblePolling()`'s task
  now receives an `isEnabled()` getter; `app.js poll()` and `event-stream.js pull()` check it after
  every `await` before touching `snap`/particles/DOM.
- **M2** (trend hover mapping): replaced the `getBoundingClientRect()`-based proportional math with
  `svg.getScreenCTM().inverse()` + `createSVGPoint()`/`matrixTransform`, correct at any rendered
  width.
- **M3** (trend/alarm-journal refresh races): both `refresh()` functions use a `seq` token,
  incremented per call and checked after the `await`, so a stale response can't overwrite a newer
  selection's result.
- **M7** (fake utility faults in replay): `replay-derive.js`'s `buildSnapshot()` now returns
  `utilities:{gpu:{unavailable:true}, comfy:{unavailable:true}, host:{unavailable:true}}` instead
  of `ok:false`/`0` values; `render-panels.js renderUtilities()` shows
  "không có dữ liệu khi phát lại" per block when `unavailable` is set. Live behaviour unchanged.
- **L5** (err colour from segment start instead of failing event): `ingest()` now records
  `seg.errTs` at the moment an `exit(!ok)`/`retry` lands; `place()` computes
  `err: seg.err && T >= (seg.errTs ?? seg.t0)`.
- **L6** (auto-pause button-label race): `replay-clock.js step()` sets `playing = false` **before**
  calling `emit()` when `t` reaches `end`, so the consumer's button label reads correctly on the
  final frame.
- **L8** (O(n) backward seek, optional): `createDeriver()` checkpoints
  `{idx, produced, failed, running, jobsSeen, terminal}` every 2000 events; a backward seek
  restores from the nearest checkpoint `<= T` instead of always rewinding to event 0.
- **L9** (polyline across data gaps): `trend-panel.js` splits each tag's points into groups
  wherever the gap exceeds `2 × step` (using the samples endpoint's returned `step`) and draws one
  `<polyline>` per group.
- TK-801 `max` in replay: left as-is per explicit instruction ("current is fine, don't overthink").

## Verification

- `node --check` passes on all 12 `plant-hmi-*.js` files.
- All files remain under 200 lines (largest: `plant-hmi-trend-panel.js` at 177).
- `grep -rn innerHTML plant-hmi-*.js` → no matches (textContent-only preserved).
- `grep` confirms `setMode`/`setParticleMode` is only ever called from `plant-hmi-app.js`.

## Concerns / unresolved

- Never tested against a live backend in this session (historian endpoints not deployed yet).
  Recommend live-testing once available: cursor pagination field names (`next_cursor`, `total`)
  match this implementation's assumptions, and the truncation message renders as expected.
- Replay's TK-801 fill bar stays visually empty (no `max` in the run contract) even though the
  numeric level is correct — cosmetic only, explicitly deemed acceptable.

Status: DONE
