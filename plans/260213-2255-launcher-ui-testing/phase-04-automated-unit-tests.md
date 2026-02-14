# Phase 4: Automated Unit Tests

## Context Links
- [Plan](plan.md)
- [Phase 3: Visual Testing](phase-03-visual-ui-testing.md)
- [Code Standards](../../docs/code-standards.md) — Testing requirements
- [Mock Patterns Research](research/researcher-02-mock-subprocess.md)

## Overview
- **Priority**: P2 (quality assurance)
- **Status**: Complete
- **Effort**: 0.5h
- **Description**: Automated unit tests for non-UI launcher components. ConfigPresetManager, ProgressTracker, ErrorHandler — testable without GPU/ComfyUI.
- **Completed**: 2026-02-14 — 30/30 unit tests passed

## Key Insights
- Existing test pattern in project: custom test runner (not pytest), self-contained assertions
- Focus on business logic, not Gradio UI (visual testing covers UI)
- ConfigPresetManager, ProgressTracker, ErrorHandler are pure logic — easy to test
- Mock nvidia-smi, ComfyUI, file system for ErrorHandler tests

## Requirements

### Functional
- FR1: Unit tests for ConfigPresetManager (preset loading, validation, overrides)
- FR2: Unit tests for ProgressTracker (regex parsing, ETA, phase weights)
- FR3: Unit tests for ErrorHandler (pre-flight checks with mocks)

### Non-Functional
- NFR1: Tests run without GPU, ComfyUI, or real pipeline scripts
- NFR2: < 200 lines per test file
- NFR3: Follow existing test pattern (custom runner with ✓/✗ output)

## Architecture

### Test Structure
```
pipeline/tests/
├── test-config-preset-manager.py    (~80 lines)
├── test-progress-tracker.py         (~100 lines)
└── test-error-handler.py            (~60 lines)
```

## Related Code Files

### Files to Create
- `pipeline/tests/test-config-preset-manager.py` (~80 lines)
- `pipeline/tests/test-progress-tracker.py` (~100 lines)
- `pipeline/tests/test-error-handler.py` (~60 lines)

### Existing Files Under Test
- `pipeline/launcher/config_preset_manager.py`
- `pipeline/launcher/progress_tracker.py`
- `pipeline/launcher/error_handler.py`

## Implementation Steps

1. Create `test-config-preset-manager.py`:
   - `test_list_presets_returns_three` — 3 built-in presets
   - `test_load_pilot_preset_has_500_images` — pilot.yaml → total_images=500
   - `test_apply_overrides_changes_total_images` — override total_images=1000
   - `test_validate_config_catches_missing_keys` — missing generation section
   - `test_validate_config_passes_valid` — valid config returns no errors
   - `test_estimate_runtime_reasonable` — pilot ~30 min estimate

2. Create `test-progress-tracker.py`:
   - `test_parse_checkpoint_line` — extracts image count
   - `test_parse_epoch_line` — extracts epoch/total
   - `test_parse_thermal_line` — extracts GPU temp
   - `test_parse_ssim_line` — extracts SSIM progress
   - `test_overall_progress_weighted` — phase weights sum correctly
   - `test_unknown_line_returns_none` — graceful fallback
   - `test_eta_calculation` — ETA decreases as progress increases

3. Create `test-error-handler.py`:
   - `test_check_dataset_path_valid` — existing dir passes
   - `test_check_dataset_path_empty` — empty string fails
   - `test_check_gpu_success` — verify GPU check passes (machine always has GPU)
   - `test_preflight_checks_collects_errors` — multiple errors collected (dataset/disk/scripts)

4. Run all tests: `cd pipeline && python tests/test-config-preset-manager.py && python tests/test-progress-tracker.py && python tests/test-error-handler.py`

## Todo List
- [x] Create test-config-preset-manager.py
- [x] Create test-progress-tracker.py
- [x] Create test-error-handler.py
- [x] Run all tests, verify pass

## Success Criteria
- All unit tests pass without GPU/ComfyUI
- ConfigPresetManager: 6 tests pass
- ProgressTracker: 7 tests pass
- ErrorHandler: 4 tests pass
- No import errors in test files

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Preset YAML paths differ in test env | Medium | Use test fixtures or temp dirs |
| Import paths break in test context | Medium | sys.path.insert pattern from existing tests |

## Security Considerations
- Tests don't commit secrets or create external connections
- Mock all external dependencies

## Next Steps
- All phases complete → update plan status
- Document any issues found → create fix tickets
