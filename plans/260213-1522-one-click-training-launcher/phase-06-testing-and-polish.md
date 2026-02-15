# Phase 6: Testing and Polish

## Context Links
- [Code Standards](../../docs/code-standards.md) - Testing requirements
- [All Phase Files](.) - Phases 1-5

## Overview
- **Priority**: P2 (quality assurance)
- **Status**: Pending
- **Effort**: 2h
- **Description**: Integration tests, error handling hardening, launch script, and dependency management for the launcher module.

## Key Insights
<!-- Updated: Validation Session 1 - Linux-only, 9-phase test coverage, no .bat scripts -->
- Unit tests for orchestrator and config manager can run without GPU
- Integration test requires ComfyUI running + GPU (use pilot mode: 5 images)
- Gradio has `gr.Blocks.queue()` for async handling
- Need launcher entry script for one-command startup
- **Linux-only** — no .bat scripts needed, only .sh
- **9-phase coverage** — tests must cover LoRA training subprocess wrapping too
- **Vietnamese UI tests** — verify labels render correctly

## Requirements

### Functional
- FR1: Unit tests for ConfigPresetManager (preset loading, validation, overrides)
- FR2: Unit tests for ProgressTracker (regex parsing, ETA calculation)
- FR3: Integration test: pilot run through orchestrator (5 images end-to-end)
- FR4: Error handling: ComfyUI not running, invalid dataset path, disk full
- FR5: Launch script (`run-launcher.sh` / `run-launcher.bat`) for one-command startup
- FR6: Updated `requirements.txt` with Gradio dependency

### Non-Functional
- NFR1: 80%+ coverage on launcher module (excluding Gradio UI code)
- NFR2: All error paths show user-friendly messages (no raw tracebacks in UI)

## Architecture

### Test Structure
```
pipeline/tests/
├── test-config-preset-manager.py     (~80 lines)
├── test-progress-tracker.py          (~100 lines)
├── test-pipeline-orchestrator.py     (~80 lines)
└── test-launcher-integration.py      (~60 lines)  # requires GPU + ComfyUI
```

### Error Handling Matrix
| Error | Detection | UI Message | Recovery |
|-------|-----------|------------|----------|
| ComfyUI not running | Pre-run connectivity check | "ComfyUI not detected at {host}:{port}" | Show setup instructions |
| Dataset path invalid | Path validation | "Dataset folder not found: {path}" | Highlight input field red |
| Disk space < 5GB | Pre-run check | "Low disk space ({X}GB free). Need ~{Y}GB" | Block run |
| Phase fails (non-zero exit) | Exit code check | "Phase {N} failed. See logs for details" | Show logs, offer retry |
| GPU not available | nvidia-smi check | "No CUDA GPU detected" | Block run |
| Config validation fails | validate_config() | List specific errors | Highlight fields |

## Related Code Files

### Files to Create
- `pipeline/tests/test-config-preset-manager.py` (~80 lines)
- `pipeline/tests/test-progress-tracker.py` (~100 lines)
- `pipeline/tests/test-pipeline-orchestrator.py` (~80 lines)
- `pipeline/tests/test-launcher-integration.py` (~60 lines)
- `pipeline/launcher/error-handler.py` (~100 lines) - Pre-flight checks
- `pipeline/run-launcher.sh` (~15 lines) - Linux/WSL launch script
- `pipeline/run-launcher.bat` (~10 lines) - Windows launch script

### Existing Files to Modify
- `pipeline/requirements.txt` - Add gradio dependency

## Implementation Steps

1. Create `error-handler.py` with pre-flight checks:
   - `check_comfyui_connection(host, port) -> bool`
   - `check_gpu_available() -> bool`
   - `check_disk_space(output_dir, required_gb) -> bool`
   - `check_dataset_path(path) -> bool`
   - `run_preflight_checks(config) -> List[str]` (returns list of error messages)
2. Create unit tests for ConfigPresetManager:
   - `test_list_presets_returns_three`
   - `test_load_pilot_preset_has_500_images`
   - `test_apply_overrides_changes_total_images`
   - `test_validate_config_catches_missing_keys`
   - `test_estimate_runtime_reasonable`
3. Create unit tests for ProgressTracker:
   - `test_parse_checkpoint_line`
   - `test_parse_epoch_line`
   - `test_parse_thermal_line`
   - `test_overall_progress_weighted`
   - `test_unknown_line_no_crash`
   - `test_eta_calculation`
4. Create unit tests for PipelineOrchestrator:
   - `test_build_phase6_command`
   - `test_build_phase7_command`
   - `test_phases_to_run_filters_correctly`
   - Mock subprocess for unit testing
5. Create integration test (GPU required):
   - `test_pilot_end_to_end`: Run orchestrator with pilot preset, verify outputs exist
   - Mark with `@pytest.mark.gpu` for conditional running
6. Create launch scripts:
   - `run-launcher.sh`: Activate venv, run `python launcher/gradio-launcher-app.py`
   - `run-launcher.bat`: Same for Windows
7. Update `requirements.txt`:
   - Add `gradio>=4.0`
8. Polish error messages in Gradio UI:
   - Wrap `start_pipeline()` in try/except
   - Show user-friendly error in `gr.Warning()` or `gr.Error()`
   - Log full traceback to file

## Todo List
- [ ] Create `error-handler.py` with preflight checks
- [ ] Create `test-config-preset-manager.py`
- [ ] Create `test-progress-tracker.py`
- [ ] Create `test-pipeline-orchestrator.py`
- [ ] Create `test-launcher-integration.py` (GPU marker)
- [ ] Create `run-launcher.sh`
- [ ] Create `run-launcher.bat`
- [ ] Update `requirements.txt` with gradio
- [ ] Add error handling in Gradio UI (try/except + user messages)
- [ ] Run all tests, verify 80%+ coverage on launcher module
- [ ] Manual smoke test: launch UI, browse folder, select preset, run pilot

## Success Criteria
- All unit tests pass without GPU/ComfyUI
- Integration test passes with ComfyUI + GPU (pilot mode, 5 images)
- `run-launcher.sh` / `run-launcher.bat` starts Gradio app in one command
- Pre-flight checks block run with clear error when ComfyUI is down
- No raw tracebacks shown in Gradio UI

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Integration test flaky due to GPU/ComfyUI | Medium | Mark as `@pytest.mark.gpu`, run separately |
| Gradio version breaks between pin and test | Low | Pin exact version in requirements.txt |
| Windows path handling differs from WSL | Medium | Test both; use `pathlib.Path` consistently |

## Security Considerations
- Tests don't commit secrets or API keys
- Launch scripts don't hardcode paths (use relative to script dir)
- `requirements.txt` pins minimum versions (no wildcards)

## Next Steps
- This is the final phase. After completion:
  - Update project docs (`docs/codebase-summary.md`, `docs/system-architecture.md`)
  - Update `docs/development-roadmap.md` with launcher milestone
  - Create demo video / usage guide
