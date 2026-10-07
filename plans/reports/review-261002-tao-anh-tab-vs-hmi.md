# Review: Gradio "Tạo Ảnh" tab vs Plant HMI (2026-10-02)

Read-only. Paths relative to `pipeline/`.

## Verdict

**Remove the tab** (it is also a production hazard). Before removal, port **3 inputs** to an HMI "new batch" form: total_images, defect_distribution, backgrounds_dir (optionally sampler name/scheduler/cfg). Prompts/LoRA strength/denoise belong in a versioned prompt-templates file selected via config, not in a run form.

Of the tab's 15 or so controls, **11 are dead**: shown but never sent to the pipeline. Only total_images, distribution, sampler name/scheduler/steps/cfg, bg dir, output dir and pilot reach `batch-production-main.py`, and they do so by **overwriting `config/batch-config.yaml` in place**.

## Feature table

| Control (ui_generation_panel.py) | Persisted where | Pipeline consumes? | HMI covers today? | Impact of removal |
|---|---|---|---|---|
| ComfyUI status + refresh (:24-49,130) | n/a | n/a | **Yes**: `COMFY_UP` permissive (plant_batch_control.py:121) + operator-tools ComfyUI start/stop (plant_operator_tools.py:78-110) | none |
| Checkpoint dropdown (:137-143) | **nowhere** (no variable, not an input to on_run) | Real source: templates `model_paths.checkpoint` -> node 1 (batch-job-scheduler.py:122-124) | No (it is file-driven either way) | **none (DEAD)** |
| ControlNet dropdown (:144-150) | nowhere | Real source: hardcoded in workflow JSON `control_net_name` (sd15-...-batch-api-workflow.json:47). templates `model_paths.controlnet` is also unused | No | **none (DEAD)** |
| LoRA CheckboxGroup (:151-157) | nowhere | Real source: templates `defect_prompts.<d>.lora_name` (scheduler:131). `batch-config.yaml lora_models:` is also **unused** | No | **none (DEAD)** |
| Per-defect positive/negative (:60-67) | nowhere (never written back to templates) | Templates `positive`/`negative` are consumed (scheduler:136-140) | No (edit the yaml by hand / prompts_path per config) | **none (DEAD)**; edits in the UI were silently discarded |
| LoRA strength slider (:69-72) | nowhere | templates `lora_strength` consumed (scheduler:132-133) | No | none (DEAD) |
| ControlNet strength slider (:73-76) | nowhere | **No**: templates `controlnet_strength` is never read. Node 9 `strength: 0.8` is hardcoded (workflow json:71) | No | none. The templates key is dead too (separate bug: the 0.85 in templates is never applied) |
| Denoise slider (:77-80) | nowhere | templates `denoise` consumed (scheduler:160,173) | No | none (DEAD) |
| Sampler name / scheduler (:89-98) | batch-config.yaml `sampler.name/scheduler` (generation_config_utils.py:154-158) | Yes (scheduler:171-172) | **No** (only via picking a different config file) | lose UI edit; config-file edit still works |
| Steps (:100-103) | batch-config.yaml `sampler.steps` | Yes, but **overridden** by HMI SP-601: env > setpoints.json > recipe (batch-production-main.py:171-173, plant_setpoints.py:55-95). Recipe outside 10..40 silently becomes 25 | **Yes**: SP-601 faceplate (plant_setpoints.py:22-34) | none; HMI is authoritative already |
| CFG (:104-107) | batch-config.yaml `sampler.cfg` | Yes (scheduler:170) | No | lose UI edit |
| Seed (:108-111) | nowhere (not in on_run inputs) | No: per-job `random.randint` (scheduler:64) | n/a | none (DEAD) |
| Total images (:163-166) | batch-config.yaml `generation.total_images` | Yes (scheduler:53) | **No** (needs a pre-made config) | **real loss**: port |
| Distribution sliders (:168-176) | batch-config.yaml `generation.defect_distribution`, normalised to 4 dp (:225-230) | Yes, `int(total*ratio)` truncates (scheduler:57) | **No** | **real loss**: port. Tab offers only 10 classes (generation_config_utils.py:24-35); **undercut + lack_of_side_wall_fusion are dropped from batch-config.yaml** on every run |
| Background dir (:186-189) | batch-config.yaml `paths.backgrounds_dir` | Yes (scheduler:42) | No (copied from source config, plant_batch_run_dirs.py:34-37) | **real loss**: port (free-text path, so it needs dir validation) |
| Output dir (:190-193) | batch-config.yaml `paths.output_base_dir` | Yes | **Better**: HMI forces a fresh `output/synthetic/<ts>_<config>/` per run (plant_batch_run_dirs.py:29-45) | none; HMI is safer |
| Pilot (:194-197) | CLI `--pilot` | Yes (main:189-194) | **Yes** (plant_batch_control_routes.py:42) | none |
| Run / Cancel (:201-203,253-259) | n/a | Popen child of tdm-backend; cancel = SIGTERM | **Yes, better**: systemd-run unit, SIGINT stop with checkpoint save, permissives, lock, audit, resume (routes:83-172, process_ops) | none |
| Progress bar + log (:206-211) | n/a | regex on stdout | **Partly**: P&ID/flow metrics, ComfyUI progress panel, checkpoint idx/total. No log tail of batch stdout (journalctl --user -u <unit>) | minor; consider a log-tail endpoint |
| LoRA-missing validation (generation_process_manager.py:37-57) | n/a | n/a | **No**: CONFIG_VALID only checks `paths.output_base_dir` (plant_batch_state_builder.py:85) | small loss; and the Gradio check scans the **wrong dir** (`<root>/models/loras`, generation_config_utils.py:74-84), while ComfyUI loads `comfyui/models/loras`. They differ: loswf + riawelc LoRAs exist only in comfyui/ |
| "All 0%" guard (process_manager:39-42) | n/a | n/a | No | trivial; add to form validation |
| Realism knobs | n/a in tab | Yes, frozen per batch + `realism-knobs-used.json` PV (main:177-185, realism/knobs.py:19,118) | **Yes**: realism page PUT /api/knobs, promote (plant_realism_routes.py:137-159) | n/a (HMI-only feature) |

## Side effects / hazards of the tab (why remove, not just hide)

1. **Destructive in-place write of `config/batch-config.yaml`** (generation_config_utils.py:168-170): `yaml.dump` sorts keys and **drops all comments** (current file has comments at lines 7-9, 15, 16, 30). It also replaces `defect_distribution` with only the 10 tab classes, so **undercut and LOSWF are silently removed** from the base config. The 4-dp normalisation plus `int()` truncation under-produces images.
2. **Main silo**: writes into `output/synthetic` + `pipeline/checkpoints` without `--resume`, so it runs non-interactively and backs up then overwrites the existing checkpoint (main:254-263). HMI per-run folders avoid this.
3. **Popen child of tdm-backend** (generation_process_manager.py:79-83): restarting `tdm-backend.service` kills the batch. stdout goes to a PIPE that only the Gradio generator drains, so when the browser disconnects the generator stops, the 64 KB pipe fills and the **batch blocks on print()** (hung GPU job, `_generation_process` set to None, cancel can no longer reach it).
4. **Cancel = SIGTERM** (:87,136): the batch only saves its checkpoint on SIGINT/KeyboardInterrupt (main:277,483), so up to 99 images of progress are lost.
5. **No permissives, no lock**: it does not take `ops.start_lock()` and has no NO_LIVE_BATCH / NO_TRAINING / MEM_OK checks, so it can start a second batch next to an HMI batch or a LoRA training on the same GPU. No audit trail.
6. Module-global `_generation_process`: two browser tabs share and clobber the state.
7. Steps edited in the tab are silently overridden by the HMI setpoint store/env (confusing).

Note: the "Thiết lập" tab (Phase 6-9 orchestrator) overlaps too. It writes `config/_generated/effective-run-config.yaml` (gradio_launcher_app.py:510-532), so it does not mutate the base config, but it has the same Popen/no-lock issues for phase 6. It is out of scope here. HMI can already run that generated file via the whitelist, and gets its own run dir.

## Recommendation

- **Remove the Tạo Ảnh tab** (gradio_launcher_app.py:333-334, plus the `generation_load_info` wiring :417-420, ui_generation_panel.py, generation_process_manager.py; and the re-export in launcher/__init__.py:22,52. Checked: no other module imports generation_config_utils/process_manager).
- **Do not port** checkpoint/ControlNet/LoRA pickers, prompt editors, strengths, denoise or seed: they are dead in the tab. Their real source is the prompt-templates yaml (selected per config via `comfyui.prompts_path`, e.g. riawelc). For experimentation, copy a templates file plus a config into `config/_generated/` and start it from HMI.
- **Port to an HMI "new batch" form** that writes a new `config/_generated/<name>.yaml` (safe_dump, sort_keys=False, never touching base configs), then goes through the existing whitelist -> permissives -> run-dir -> systemd-run path.

## Minimal HMI "new batch" form fields (nothing lost for production)

1. **Base config** (whitelist dropdown, already exists): inherits comfyui/workflow_path/prompts_path/output/reliability/thermal.
2. **total_images**: int >= 1 (cap, e.g. <= 20000).
3. **defect_distribution**: one weight per class **read from the base config + templates keys** (all 12, not a hardcoded 10). Normalise to sum 1. Server-side: reject all-zero; reject classes absent from `defect_prompts`. Allocate counts with largest-remainder so the job count equals total exactly (or show the truncated count).
4. **backgrounds_dir**: path, validated server-side (exists, is a dir, contains png/jpg, under the project root or an allow-list).
5. **pilot / resume / reason**: already exist.
6. Optional (only if operators really tune them): **sampler.name, sampler.scheduler, sampler.cfg** as enums/range-checked, or better as SP faceplates like SP-601. **steps** is already SP-601.
7. **Permissive to add: LORA_PRESENT**. For each class with weight > 0, `defect_prompts[d].lora_name` must exist in `comfyui/models/loras` (the dir ComfyUI really loads) and the class must have a mask generator.

Output dir is NOT a field: the run dir is forced by plant_batch_run_dirs.

## Unresolved questions

- Do operators actually tune sampler name/scheduler/cfg per run? If not, drop item 6.
- Is `templates.controlnet_strength` (0.85) meant to apply? Currently node 9 is hardcoded at 0.8: a pipeline bug independent of this decision.
- Should `batch-config.yaml lora_models:` and templates `sampler_config`/`model_paths.controlnet` (all unused) be deleted to avoid misleading edits?
