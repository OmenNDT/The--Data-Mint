# Phase 1: Bug Fixes & Prerequisites

## Context Links
- [Plan](plan.md)
- [Code Standards](../../docs/code-standards.md)
- [Original Plan](../260213-1522-one-click-training-launcher/plan.md)

## Overview
- **Priority**: P0 (blocking — UI won't run without these fixes)
- **Status**: Complete
- **Effort**: 1h
- **Description**: Fix critical bugs found in code review that prevent UI from launching correctly.
- **Completed**: 2026-02-14

## Key Insights
<!-- Updated: Validation Session 1 - pip install gradio required, Linux-only -->
- Import bug in `ui_dataset_panel.py` will crash on import
- `check_gpu_available()` returns None for gpu_msg on success → UI shows "GPU: None"
- `ProgressTracker` exists but is dead code — not wired into orchestrator/UI
- Missing `gradio` in requirements.txt
- **Gradio not installed** — must `pip install gradio` before any testing
- **Linux-only** — no .bat testing needed

## Requirements

### Functional
- FR1: Fix relative import in `ui_dataset_panel.py`
- FR2: Fix `check_gpu_available()` to return GPU name on success
- FR3: Add `gradio>=4.0` to requirements.txt
- FR4: Ensure `python -m launcher.gradio_launcher_app` runs without import errors

### Non-Functional
- NFR1: No file exceeds 200 lines (split if needed during fixes)

## Related Code Files

### Files to Modify
- `pipeline/launcher/ui_dataset_panel.py` — Fix import (line 10)
- `pipeline/launcher/launcher_utils.py` — Fix check_gpu_available() return value (line 111)
- `pipeline/requirements.txt` — Add gradio

## Implementation Steps

1. Fix `ui_dataset_panel.py:10`:
   - Change `from launcher.config_preset_manager import ...` → `from .config_preset_manager import ...`

2. Fix `launcher_utils.py:111` `check_gpu_available()`:
   - Change `return True, None` → `return True, gpu_name`

3. Update `requirements.txt`:
   - Add `gradio>=4.0`

4. Install gradio: `pip install gradio>=4.0`

5. Smoke test: `cd pipeline && python -c "from launcher import PipelineLauncherApp"`
   - Verify no import errors

## Todo List
- [x] Fix relative import in ui_dataset_panel.py
- [x] Fix check_gpu_available() return value
- [x] Add gradio to requirements.txt
- [x] Verify imports work without errors

## Success Criteria
- `from launcher import PipelineLauncherApp` succeeds
- `check_gpu_available()` returns GPU name string on success
- `pip install -r requirements.txt` includes gradio

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Other hidden import errors | Medium | Run full import test |
| Gradio version conflict | Low | Pin >= 4.0, test after install |

## Security Considerations
- No security impact from these fixes

## Next Steps
- Phase 2: Create demo mock mode for testing without real pipeline
