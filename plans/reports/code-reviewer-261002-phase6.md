# Code review: Plant HMI phase 6 (6A batch start/stop, 6B ISA-18.2 ack/shelve)

Scope: plant_batch_*.py, plant_alarm_state*.py, plant_request_guards.py, _alarm_views, sampler journal, static JS for batch control + alarm list. Read-only review; no services touched.
Line numbers are file-relative (pipeline/plant_hmi/...).

## CRITICAL

**C1. Every alarm action button is dead in the browser.** `static/plant-hmi-alarm-list.js:11-18` defines a local `h()` that does `node.setAttribute(k, v)` for every attr, including `onclick`/`oninput` functions. The function is stringified into an inline handler body `() => run(...)`, which only creates an arrow fn and never calls it (closure vars are also out of scope). Result: Ack (61, 67), Tạm tắt (71), duration picks, Tiếp tục, Huỷ, Ack all (187), Bỏ tạm tắt (143), shelved-summary toggle all do nothing; reason `oninput` (83) never updates `reason`. No console error, so it looks "fine". Live verification was via API, not the UI.
Fix: import `h` from `plant-hmi-setpoint-dom.js` (which handles `on*` via addEventListener and skips null attrs) and delete the local copy.

**C2. Lost-update race: snapshot poll overwrites ack/shelve/unshelve.** `plant_snapshot_builder.py:188` calls `read_store()` with NO lock, then `annotate_alarms` (`plant_alarm_state.py:186-192`) takes the lock and writes the whole `updated_store` built from that stale read. Sequence: poll T1 reads store, POST /ack writes the ack, T1 writes the stale store, so the ack is gone. The journal already has an `acked` row, so state and journal disagree. Same for shelve (alarm pops back) and unshelve (shelve comes back). The window is always open: while any alarm is active, `last_seen_ts = now` changes every tick, so every poll (each tab every 3 s, plus the sampler) rewrites the file.
Fix: do read, compute and write inside one `_locked_store()`. Better: merge only `last_seen` into a fresh read under the lock (never write back `acks`/`shelves` from the caller's copy).

## HIGH

**H1. 6B journal rows break restart seeding, so acks/shelves get lost on every backend restart.** `plant_historian_store.py:120-133 latest_alarm_states()` takes the latest row per `code|tag|pid` and keeps it only if `state == "raised"`. 6B now appends `acked`/`shelved`/`unshelved` rows (ts later than `since`) for the same key. After restart, an acked or shelved alarm is not seeded:
(a) `seed_alarm_on_delay` misses it, `since` resets to the new first-seen, the occurrence key changes, so the ack/shelve is lost and the alarm re-annunciates unacked;
(b) the sampler re-journals a duplicate `raised`;
(c) a shelved occurrence's old key is still in `last_seen` (not popped by shelve), so it shows up as a false "đã hết · chờ xác nhận" for up to 24 h.
Also, when a snapshot poll lands before the sampler thread seeds, `AlarmOnDelay._first` already holds `now` and `seed()` uses setdefault, so the same key loss happens.
Fix: `WHERE state IN ('raised','cleared')` in the seeding query; seed synchronously before routes serve.

**H2. Concurrent start TOCTOU leads to two batches on one GPU.** `plant_batch_control_routes.py:141-150`: there is no lock between evaluating `NO_LIVE_BATCH` and `systemd-run`, and the new python is not visible in /proc until after systemd forks and execs. Sync FastAPI handlers run in parallel threadpool workers. Triggers: Xác nhận button not disabled while in flight (`plant-hmi-batch-control-panel.js:71-73, 81-92`), two tabs, a curl retry, or a Gradio-launcher start (separate path, no shared lock). The unit name `tdm-batch-%y%m%d-%H%M%S` (`plant_batch_process_ops.py:25-26`) only collides within the same second. Two batches share checkpoint and output, which corrupts the checkpoint and mixes images.
Fix: a module `threading.Lock` plus an `fcntl` lock file (shared with the launcher) held across evaluate, start, and wait until `find_batch_processes()` sees the pid. Or use a fixed unit name `tdm-batch` with `--collect`, so systemd rejects a second start atomically. Disable the button while pending.

**H3. Stop = SIGTERM, but the batch has no SIGTERM handler, so it dies without saving.** `plant_batch_process_ops.py:104,113` (`systemctl stop` defaults to KillSignal=SIGTERM for the whole cgroup; the fallback is `os.kill(pid, 15)` with the comment "checkpoint-save path"). `batch_manager/batch-production-main.py:473-479` handles only `KeyboardInterrupt` (SIGINT). Python's default SIGTERM terminates at once: no finally, no checkpoint flush. Up to `checkpoint_interval-1` images of progress are lost. Prompts already queued in ComfyUI keep running, the GPU stays busy, and `NO_LIVE_BATCH` passes, so a new start piles onto that queue.
Fix: `systemd-run -p KillSignal=SIGINT -p TimeoutStopSec=60` and `os.kill(pid, signal.SIGINT)`, or add a SIGTERM→KeyboardInterrupt handler in the batch. Optionally interrupt/clear the ComfyUI queue on stop.

**H4. DNS rebinding bypasses the CSRF guard on all 7 write routes.** `plant_request_guards.py:23-28` only checks Origin host == Host header. With rebinding (evil.com resolves to the LAN IP), Origin=`http://evil.com:7860` and Host=`evil.com:7860` match, Sec-Fetch-Site is `same-origin`, and the header can be set because the request is same-origin from the browser's view. Any web page the operator opens can start/stop batches and ack/shelve alarms. No auth means LAN users can do this anyway, but rebinding widens it to the internet.
Fix: a Host allowlist (localhost, 127.0.0.1, LAN IP, Tailscale IPs, hostname) checked in `require_trusted_request`.

**H5. Shelve keyed per occurrence (includes `since`), so it is useless for chattering alarms.** `plant_alarm_state.py:43-44, 165-171`. The main ISA-18.2 shelving use case is a nuisance/chattering point. Each clear and re-raise gets a new `since`, so a new key, and the alarm is unshelved again. Also `new_last_seen` is filled before the shelf check (162), so a shelved occurrence that clears lands in `cleared_unacked` and demands an ack, which defeats the shelve.
Fix: key shelves by `code|tag|pid` (point), keep acks per occurrence; skip last_seen for shelved points.

## MEDIUM

- **M1. Client timeout shorter than server worst case.** `static/plant-hmi-batch-control-api.js:8` aborts at 8 s. The server can take probes, then `systemd-run` (timeout 10 s), then a 5 s active poll. The UI shows an abort error and resets to idle while the batch actually starts, which invites a retry (feeds H2). Use 20 s for start/stop, or return 202 then poll.
- **M2. Unbounded, unvalidated alarm keys.** `plant_alarm_state_routes.py:32-49`: `key` has no max_length, `keys` has no max_items, and there is no check that the key exists. A LAN client can bloat `alarm-state.json` (kept 24 h, and rewritten + fsync'd every poll, M3) and inject fake `acked` journal rows with any code/tag. Fix: `max_length=256`, `max_items=200`, accept only keys in the current active/cleared_unacked/shelved set.
- **M3. fsync write of the full store on every poll while any alarm is active** (`last_seen_ts` always changes, `plant_alarm_state.py:162-164, 189`). This costs IO per tab per 3 s and widens C2. Keep `last_seen_ts` in memory, or persist only when the key set changes.
- **M4. Row kind fixed at creation.** `plant-hmi-alarm-list.js` `createRow(key, kind)` / `renderAlarmList` 301-311. When an active alarm clears unacked, the same key moves to `cleared`, but the cached row stays `active`: the duration keeps growing, Tạm tắt is still offered, and there is no cleared styling. Recreate the row when kind changes.
- **M5. Own SwapRateMeter sampled only on GET.** `plant_batch_control_routes.py:35, 85`. Right after a restart the first POST is blocked (`None`, which is fail-safe and OK). When the panel has not polled for a long time, the rate is averaged over hours, so current thrash is diluted and MEM_OK passes. Reuse the snapshot/sampler meter, or treat a last read older than 30 s as unknown.
- **M6. Restart after stop silently discards progress by default.** `resume` defaults to false, and in non-tty mode the batch backs up the checkpoint and starts fresh (`batch-production-main.py:261-263`) into the same output dir. The stop confirm text implies progress is kept. Default resume=on when a checkpoint exists, or show it as a permissive/warning.
- **M7. Start success is weak.** systemd-run default Type=simple is "active" after fork, before exec (man systemd-run), so a bad venv path or an instant crash still returns ok. Failed transient units linger without `--collect`. Add `-p Type=exec --collect`.

## LOW

- **L1.** NUL byte in config name: `Path.resolve` raises ValueError, but `plant_batch_config_whitelist.py:25-27` catches only OSError. `/start` returns an unhandled 500 with no audit row (GET catches it).
- **L2.** systemd 255 `systemd-run` expands `${VAR}` in argv by default. A config path containing `$` gets mangled (not shell injection). Add `--expand-environment=no` (`plant_batch_process_ops.py:32-36`).
- **L3.** `/start` exceptions in `_permissive_state` (e.g. /proc scan) are outside try (`routes:141`): fail-closed but not audited.
- **L4.** Stop binds by pid only. Pass `start_ts` from GET and verify it in POST, to rule out pid reuse or stopping a different batch than the operator confirmed (low probability).
- **L5.** Ack-all sends every visible key, including already-acked ones. That overwrites `acked_by/acked_at` and adds duplicate journal rows (`plant_alarm_state.py:101-109`, `alarm-list.js:187`). Filter to unacked.
- **L6.** Shelve expiry is not journalled (only manual unshelve). The unshelve onclick has no try/catch. The `_alarm_views` fallback (`plant_snapshot_builder.py:191-192`) returns alarms without `key`, so JS rows map to `undefined` and collapse into one.
- **L7.** `batch-audit.jsonl` grows forever and `read_audit` reads the whole file every 5 s poll. `_live_batches` re-runs `list_configs()` (YAML loads, 10 s cache) per live pid.
- **L8.** `_generated/effective-run-config.yaml` is overwritten by each Gradio run, so an HMI start of it runs whatever the last UI session baked in. The UI could show its mtime.

## Checked, OK

- argv lists, no shell; absolute config path, so no `--flag` injection.
- Whitelist: strict resolve plus real parent == allowed dir blocks `..`, symlink escape and nested dirs; unicode names harmless.
- Float `since` in the key: the key is a server-built string echoed back by JS unchanged, and SQLite REAL round-trips doubles exactly. The only drift path is restart (H1).
- Permissives: None means block, which is fail-safe. The stop route re-validates pid against live /proc at POST time.
- `require_trusted_request` is on all 6 new POSTs (+ setpoint PUT/DELETE). All text is rendered via textContent (no XSS from reason/message).
- Backend restart does not kill HMI-started units (R8).

## Unresolved questions

1. Was per-occurrence shelving (H5) a deliberate spec choice? The plan says only "shelve có hạn".
2. Should stop also cancel prompts already queued in ComfyUI?
3. Should the Gradio launcher's own start path honor the same lock/permissives (H2)?
4. Which hostnames/IPs should the Host allowlist accept (Tailscale acct A/B, LAN 10.42.0.x)?
