# HMI "Tạo mẻ mới" (new batch) form — implementation report (2026-10-02)

Paths relative to `pipeline/` unless stated.

## Files added

Backend:
- `plant_hmi/plant_batch_compose.py` (168 lines) — `defect_options`, `lora_present`,
  `missing_for_config`, `compose_options`, `compose_config` (orchestration + YAML write).
- `plant_hmi/plant_batch_compose_validate.py` (119 lines) — name/total/distribution/
  backgrounds_dir validation, `ComposeError`.
- `plant_hmi/plant_batch_allocate.py` (46 lines) — `allocate_counts` (largest-remainder),
  `ratio_for_count` (nudges the written ratio with `math.nextafter` so the scheduler's own
  `int(total*ratio)` reproduces the exact count despite float rounding).
- `plant_hmi/plant_batch_compose_routes.py` (88 lines) — `GET compose-options` /
  `POST compose`, included into `plant_batch_control_routes.router` (same prefix), so
  `plant_hmi_routes.py` needed no change.
- `tests/test-plant-hmi-batch-compose.py` (32 tests, all pass).

Frontend:
- `static/plant-hmi-batch-compose-api.js` (39 lines) — fetch wrapper.
- `static/plant-hmi-batch-compose-row.js` (40 lines) — per-defect row (weight slider+number,
  live count, LoRA/mask badge with `data-tip`).
- `static/plant-hmi-batch-compose-panel.js` (193 lines) — form (base select, name, total,
  rows, backgrounds dir, reason, two-step "Lưu config"/"Lưu & chạy").

## Files modified

- `plant_hmi/plant_batch_control.py` — new `LORA_PRESENT` permissive (blocking), reads
  `state["lora_missing"]`.
- `plant_hmi/plant_batch_state_builder.py` — `permissive_state` now also computes
  `lora_missing` via `compose.missing_for_config(config_cfg)`.
- `plant_hmi/plant_batch_control_routes.py` — trimmed (now 185 lines): module docstring
  updated, `ComposeBody`/compose routes moved out, `router.include_router(compose_router)`
  added.
- `static/plant-hmi-batch-control.js` — mounts the compose toggle button + form, wires
  `onComposed` to refresh state and force-select the new config.
- `static/plant-hmi-batch-control-panel.js` — added `forceSelectConfig(name)` to the
  `createStartControls` return value (229 → 240 lines; file already exceeded 200 before
  this change).
- `static/plant-hmi-batch-control.css` — `.bcp-*` classes, dark-neumorphism tokens reused
  from the existing `:root` palette.

## API

```
GET  /plant-hmi/api/control/batch/compose-options?base=<name>
  -> { base_config, defects: [{defect, label, lora_name, lora_present, mask_generator,
       default_weight}], default_total_images, default_backgrounds_dir }

POST /plant-hmi/api/control/batch/compose
  body: {name, base_config, total_images, distribution: {defect: weight}, backgrounds_dir?,
         reason?, overwrite?}
  -> 200 {config_name, counts, total_images, backgrounds_dir}
  -> 400 {error, failures: [{field, message}]}
```

Validation enforced server-side: slug name `^[a-z0-9-]{1,60}$`, overwrite refused unless
`overwrite: true`; base config must resolve via the existing whitelist; every defect in
`distribution` must exist in the base config's own `comfyui.prompts_path` templates
(falls back to the repo default templates file when absent); any defect with weight > 0
must have BOTH a LoRA file under `comfyui/models/loras` and an entry in the hardcoded
`MASK_GENERATOR_DEFECTS` set (mirrors `mask_prefetch_worker_pool.py`'s generator dict,
all 13 current defects are covered); at least one weight > 0; `total_images` int 1..20000;
`backgrounds_dir` must exist, be a directory, contain ≥1 png/jpg, and resolve under
`dataset/` or the base config's own `backgrounds_dir` parent.

Count allocation: largest-remainder on normalised weights (counts always sum to
`total_images` exactly), then each written ratio is nudged via `math.nextafter` until
`int(total_images * ratio)` reproduces that exact count — verified for totals
{1,7,100,333,1000,12345,20000} × {1,2,3,7,13} classes in
`RatioForCountTests.test_ratio_reproduces_count_for_many_totals_and_splits`.

Write path: `yaml.safe_dump(new_cfg, sort_keys=False)` to a `.tmp` file then
`Path.replace()` into `config/_generated/<name>.yaml`; base config is only ever read
(`production.load_batch_config`, cached) — `test_valid_compose_writes_file_and_leaves_base_untouched`
and every validation-failure test assert the base file's sha256 is unchanged. The
`lora_models:` key (review doc: unused/misleading) is dropped from the written config.

## LORA_PRESENT permissive

Added to `evaluate_permissives` (blocking): for the currently *selected* run config (not
the compose form), every defect with weight > 0 in its own `generation.defect_distribution`
must have a present LoRA file and a mask generator. `plant_batch_state_builder.permissive_state`
supplies `lora_missing` via `compose.missing_for_config`.

## Frontend flow

"＋ Tạo mẻ mới" toggles a form below the start/stop card. Selecting a base config fetches
`compose-options` and builds one row per defect; rows with a missing LoRA/mask generator
are disabled (forced weight 0) with a red "✗" badge and a tooltip listing what's missing.
Weight edits recompute a live per-row count via a JS mirror of the server's largest-remainder
math (server remains authoritative on save). "Lưu config" / "Lưu & chạy" both arm a
two-step confirm (same pattern as Start/Stop); "Lưu & chạy" calls `compose` then the
existing `startBatch(config_name, pilot=false, resume=false, reason)` — no new start
endpoint needed. On success, `onComposed` refreshes state (so the new file is visible via
the whitelist scan) then calls the new `startControls.forceSelectConfig(name)`, since
`update()` deliberately keeps the operator's prior selection on every poll (rule H2) and
would otherwise never auto-switch to the newly created config.

## Verification

- `python3 -m py_compile plant_hmi/*.py` — clean.
- `node --check` on all new/edited JS files — clean.
- `tests/test-plant-hmi-batch-compose.py` — 32/32 pass (validation, allocation/ratio
  exactness, base-config-untouched hash check, CSRF 403, overwrite refusal, LORA_PRESENT
  permissive).
- All 10 `tests/test-plant-hmi-*.py` suites (197 tests total) still pass after the edits.
- `node tests/js/check-alarm-list-buttons.mjs` — passes (untouched, confirms no breakage
  from a shared import like `plant-hmi-setpoint-dom.js`).
- Did NOT start ComfyUI, start any real batch, restart any service, or commit.

## Status: DONE
**Summary:** New-batch compose form (backend validate/allocate/write + LORA_PRESENT
permissive + frontend form) implemented across new/owned files only; all required test
suites pass.
**Concerns:** none blocking.

## For main / docs

- No `plant_hmi_routes.py` change needed — compose routes mount via
  `plant_batch_control_routes.router.include_router(compose_router)` under the same
  prefix already registered there.
- `static/plant-hmi-batch-control-panel.js` already exceeded 200 lines before this task
  (229); my one-method addition took it to 240. Worth a follow-up split if main is doing a
  broader cleanup pass, not done here to respect file-ownership/scope.
- Did not touch `ui_generation_panel.py` / `generation_config_utils.py` / the Gradio
  "Tạo Ảnh" tab (review doc recommends removing it) — out of this task's file ownership.

## Unresolved questions

- None blocking. Per the review doc's own open question: sampler name/scheduler/cfg were
  intentionally left out of the form (spec listed them optional); add later if operators
  ask to tune them per batch.
