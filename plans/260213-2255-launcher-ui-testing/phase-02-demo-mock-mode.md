# Phase 2: Demo Mock Mode

## Context Links
- [Plan](plan.md)
- [Phase 1: Bug Fixes](phase-01-bug-fixes-prerequisites.md)
- [Mock Patterns Research](research/researcher-02-mock-subprocess.md)

## Overview
- **Priority**: P1 (required for visual testing without real training)
- **Status**: Complete
- **Effort**: 1.5h
- **Description**: Create a demo/mock mode that simulates pipeline execution with fake progress output. Allows full UI testing without ComfyUI, GPU, or actual training.
- **Completed**: 2026-02-14

## Key Insights
<!-- Updated: Validation Session 1 - demo duration 20-30s, Linux-only -->
- User explicitly said: "chỉ test UI chứ không training AI thật"
- Mock subprocess.Popen to emit fake [CHECKPOINT], epoch, SSIM lines
- Simulate ~25 second "pipeline run" with realistic progress (user chose 20-30s)
- Create fake QA/validation results JSON for Results tab testing
- Mock tkinter folder dialog to return test path

## Requirements

### Functional
- FR1: `--demo` flag or `DEMO_MODE=1` env var to enable mock mode
- FR2: Mock pipeline emits realistic log lines (checkpoint, thermal, epoch)
- FR3: Mock completes in ~25 seconds (not 18 hours) — enough to observe each phase
- FR4: Fake qa-results.json and validation-results.json for Results tab
- FR5: Mock folder dialog returns a valid test path
- FR6: All UI interactions work in demo mode (run, cancel, progress, results)

### Non-Functional
- NFR1: Demo mode code in separate file (not mixed with production code)
- NFR2: < 200 lines per file

## Architecture

```
gradio_launcher_app.py
    |
    if DEMO_MODE:
        use MockPipelineOrchestrator  # from demo_pipeline_runner.py
    else:
        use PipelineOrchestrator      # real pipeline
```

### Mock Log Output Sequence (10 seconds)
```
[INFO] Pipeline started - Demo Mode
[Phase 6/9] Tạo Ảnh
[CHECKPOINT] Generated 100 images, elapsed: 2.0s
GPU temp: 72.5
[CHECKPOINT] Generated 200 images, elapsed: 4.0s
[CHECKPOINT] Generated 300 images, elapsed: 6.0s
[Phase 8/9] Kiểm tra Chất lượng
SSIM check: 50/100 images
SSIM check: 100/100 images
QA complete. SSIM: 0.94
[Phase 9/9] Đánh giá
Epoch 5/20
Epoch 10/20
Epoch 15/20
Epoch 20/20
mAP@0.5: 0.612
Pipeline completed successfully!
```

## Related Code Files

### Files to Create
- `pipeline/launcher/demo_pipeline_runner.py` (~120 lines) — Mock orchestrator + fake output
- `pipeline/launcher/demo_results_data.py` (~60 lines) — Fake QA/validation JSON data

### Files to Modify
- `pipeline/launcher/gradio_launcher_app.py` — Add demo mode detection + swap orchestrator

## Implementation Steps

1. Create `demo_pipeline_runner.py`:
   - `MockPipelineOrchestrator` class with same interface as `PipelineOrchestrator`
   - `run_all()` emits fake log lines via progress_callback with time.sleep delays
   - Returns `PipelineResult(success=True, ...)` after ~10 seconds
   - `cancel()` stops the mock run immediately

2. Create `demo_results_data.py`:
   - `create_fake_qa_results()` → writes qa-results.json with realistic SSIM values
   - `create_fake_validation_results()` → writes validation-results.json with mAP values
   - `create_fake_sample_images()` → creates placeholder PNG files (or uses existing)

3. Modify `gradio_launcher_app.py`:
   - Check `os.environ.get("DEMO_MODE")` or `--demo` flag
   - If demo: use `MockPipelineOrchestrator` instead of real one
   - If demo: skip ComfyUI/GPU pre-flight checks (show "Demo Mode" in status bar)
   - If demo: mock `browse_folder()` to return `"./dataset/demo"`

4. Create demo launch command:
   - `DEMO_MODE=1 python -m launcher.gradio_launcher_app`
   - Or: `python -m launcher.gradio_launcher_app --demo`

## Todo List
- [x] Create MockPipelineOrchestrator with fake log output
- [x] Create fake QA/validation result data
- [x] Add demo mode detection to main app
- [x] Swap orchestrator based on demo flag
- [x] Test: launch in demo mode, run pipeline, verify progress + results

## Success Criteria
- `DEMO_MODE=1 python -m launcher.gradio_launcher_app` launches UI
- Clicking "Run Pipeline" shows progress bar advancing over ~10 seconds
- Log display shows realistic checkpoint/epoch lines
- Results tab populates with fake QA/validation data after run
- Cancel button stops mock pipeline immediately
- No real subprocess spawned, no GPU/ComfyUI needed

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Demo mode accidentally used in production | Medium | Clear "DEMO MODE" banner in UI |
| Mock output format diverges from real | Low | Base mock on actual log patterns from code |

## Security Considerations
- Demo mode creates local files only
- No external connections made

## Next Steps
- Phase 3: Visual UI testing with demo mode active
