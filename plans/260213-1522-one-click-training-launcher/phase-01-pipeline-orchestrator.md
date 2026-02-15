# Phase 1: Pipeline Orchestrator

## Context Links
- [Codebase Summary](../../docs/codebase-summary.md)
- [System Architecture](../../docs/system-architecture.md)
- [Batch Config](../../pipeline/config/batch-config.yaml)
- [Research: Training Patterns](research/researcher-02-training-launcher-patterns.md)

## Overview
- **Priority**: P1 (foundation for all other phases)
- **Status**: Pending
- **Effort**: 3h
- **Description**: Create `PipelineOrchestrator` class that wraps phases 6-9 into a single callable entry point. Each phase runs as subprocess, captures stdout/stderr, and reports status via callback.

## Key Insights
<!-- Updated: Validation Session 1 - Expanded from 4 phases to all 9 phases -->
- All 9 phases have CLI entry points or shell scripts with well-defined args
- Existing scripts have no shared state; they communicate via filesystem (output dirs)
- Phase flow is strictly sequential: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
- Checkpoint resume already exists in Phase 6
- Phase 9 requires `--real-yolo-dir` (optional, unchecked by default in UI)
- Phase 3 (LoRA training) uses kohya-ss with TOML configs (~2-3h per model, 5 models)
- Native Linux execution — no WSL path translation needed

## Requirements

### Functional
<!-- Updated: Validation Session 1 - Expanded scope to all 9 phases -->
- FR1: Run all 9 phases sequentially with a single method call
- FR2: Accept config dict (from preset manager) to build CLI args
- FR3: Support running subset of phases (e.g., skip Phase 9, run only Phase 3)
- FR4: Emit progress callbacks (phase started/completed/failed)
- FR5: Capture and forward stdout/stderr in real-time
- FR6: Support cancellation (kill subprocess)
- FR7: Detect and offer checkpoint resume for Phase 6
- FR8: Support Phase 3 LoRA training via kohya-ss (5 TOML configs)
- FR9: Phase 9 optional — skip unless user provides real dataset path

### Non-Functional
- NFR1: No modifications to existing pipeline scripts
- NFR2: < 200 lines per file
- NFR3: Google-style docstrings, type hints on all functions

## Architecture

```
PipelineOrchestrator
├── __init__(config: dict, progress_callback: Callable)
├── run_all() -> PipelineResult
├── run_phase(phase_id: int) -> PhaseResult
├── cancel() -> None
└── get_status() -> dict

PhaseRunner (internal)
├── _build_command(phase_id, config) -> List[str]
├── _run_subprocess(cmd) -> subprocess.Popen
├── _stream_output(proc, callback) -> int
└── _parse_exit_code(returncode) -> PhaseResult
```

### Data Flow
```
User config (dict)
    |
PipelineOrchestrator.run_all()
    |
    +--> Phase 6: subprocess.Popen(["python", "batch-production-main.py", "--config", ...])
    |       stdout -> progress_callback
    |       wait for exit code 0
    |
    +--> Phase 7: subprocess.Popen(["python", "post-processing-main.py", "--synthetic-dir", ...])
    |       stdout -> progress_callback
    |       wait for exit code 0
    |
    +--> Phase 8: subprocess.Popen(["python", "qa-pipeline-main.py", "--dataset-dir", ...])
    |       stdout -> progress_callback
    |       wait for exit code 0
    |
    +--> Phase 9: subprocess.Popen(["python", "validation-main.py", "--synth-yolo-dir", ...])
            stdout -> progress_callback
            wait for exit code 0
```

## Related Code Files

### Files to Create
- `pipeline/launcher/__init__.py` (~20 lines) - Module exports
- `pipeline/launcher/pipeline-orchestrator.py` (~180 lines) - Main orchestrator class
- `pipeline/launcher/phase-runner.py` (~150 lines) - Subprocess execution helper
- `pipeline/launcher/launcher-utils.py` (~80 lines) - Path validation, config helpers

### Existing Files Referenced (read-only)
- `pipeline/batch_manager/batch-production-main.py` - Phase 6 entry (args: `--config`, `--pilot`)
- `pipeline/post_processing/post-processing-main.py` - Phase 7 entry (args: `--synthetic-dir`, `--output-dir`, `--train-ratio`, `--val-ratio`, `--test-ratio`)
- `pipeline/qa/qa-pipeline-main.py` - Phase 8 entry (args: `--synthetic-dir`, `--dataset-dir`, `--output-dir`, `--ssim-sample-size`)
- `pipeline/validation/validation-main.py` - Phase 9 entry (args: `--real-yolo-dir`, `--synth-yolo-dir`, `--output-dir`, `--model-size`, `--epochs`, `--batch-size`, `--ratios`)

## Implementation Steps

1. Create `pipeline/launcher/` directory and `__init__.py`
2. Create `launcher-utils.py` with:
   - `validate_dataset_path(path) -> bool` - check dir exists, has expected structure
   - `resolve_pipeline_path(relative) -> Path` - resolve paths relative to pipeline root
   - `build_python_command(script_path, args_dict) -> List[str]` - build subprocess command
3. Create `phase-runner.py` with:
   - `PhaseResult` dataclass: `phase_id`, `success`, `exit_code`, `duration_seconds`, `output_dir`
   - `PhaseRunner` class:
     - `__init__(python_executable, pipeline_dir)`
     - `run(phase_id, script_path, args, progress_callback) -> PhaseResult`
     - `cancel()` - send SIGTERM to subprocess
     - Internal: `_stream_output()` using `asyncio.subprocess` or threading
4. Create `pipeline-orchestrator.py` with:
   - `PipelineOrchestrator` class:
     - `__init__(config, progress_callback, phases_to_run=[6,7,8,9])`
     - `run_all() -> List[PhaseResult]` - sequential execution
     - `run_phase(phase_id) -> PhaseResult`
     - `cancel()` - delegate to PhaseRunner
     - `get_status() -> dict` - current phase, overall progress
   - Internal: `_build_phase_args(phase_id, config) -> dict` mapping config keys to CLI args
5. Map config dict keys to CLI arguments for each phase:
   - Phase 6: `config.batch_config_path` -> `--config`, `config.pilot_mode` -> `--pilot`
   - Phase 7: `config.synthetic_dir` -> `--synthetic-dir`, `config.output_dir` -> `--output-dir`
   - Phase 8: `config.synthetic_dir` -> `--synthetic-dir`, `config.dataset_dir` -> `--dataset-dir`
   - Phase 9: `config.real_yolo_dir` -> `--real-yolo-dir`, `config.synth_yolo_dir` -> `--synth-yolo-dir`
6. Add checkpoint detection: check `pipeline/checkpoints/` for existing checkpoint files before Phase 6
7. Add logging via `logging.getLogger(__name__)`

## Todo List
- [ ] Create `pipeline/launcher/` directory
- [ ] Create `__init__.py` with module exports
- [ ] Implement `launcher-utils.py`
- [ ] Implement `PhaseResult` dataclass
- [ ] Implement `PhaseRunner` class with subprocess management
- [ ] Implement `PipelineOrchestrator` class
- [ ] Map all config keys to CLI args for phases 6-9
- [ ] Add checkpoint detection for Phase 6
- [ ] Add cancellation support (subprocess.terminate)
- [ ] Add logging throughout
- [ ] Verify type hints and docstrings

## Success Criteria
- Can instantiate `PipelineOrchestrator` with a config dict
- `run_all()` executes phases 6-9 sequentially via subprocess
- stdout/stderr streamed to callback in real-time
- Each phase exit code captured in `PhaseResult`
- `cancel()` terminates running subprocess
- No modifications to existing pipeline scripts

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Subprocess stdout buffering delays real-time output | Medium | Use `subprocess.Popen` with `bufsize=1`, `universal_newlines=True` |
| Windows vs WSL path differences | High | Use `launcher-utils.py` to normalize paths; detect environment |
| Phase 6 takes 18+ hours; connection drops | Medium | Checkpoint resume already built in; orchestrator detects and offers resume |
| Phase 9 `--real-yolo-dir` not provided | High | Validate before run; make Phase 9 optional with clear UI warning |

## Security Considerations
- No credentials in config dict (ComfyUI API has no auth)
- Subprocess commands built from validated paths only (no shell injection)
- Use `subprocess.Popen(cmd_list)` not `shell=True`

## Next Steps
- Phase 2 (Config Preset Manager) provides the config dict consumed by this orchestrator
- Phase 3 (Gradio UI) calls `PipelineOrchestrator.run_all()` on button click
- Phase 4 (Progress Tracking) consumes the `progress_callback`
