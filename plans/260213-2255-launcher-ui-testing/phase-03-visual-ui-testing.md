# Phase 3: Visual UI Testing

## Context Links
- [Plan](plan.md)
- [Phase 2: Demo Mock Mode](phase-02-demo-mock-mode.md)
- [Gradio Testing Research](research/researcher-01-gradio-testing.md)

## Overview
- **Priority**: P1 (core — user observes UI)
- **Status**: Complete
- **Effort**: 1h
- **Description**: Launch the Gradio UI in demo mode at localhost:7860. Run through all UI interactions while user observes. Document any visual/functional issues.
- **Completed**: 2026-02-14 — 15/15 automated tests passed via gradio_client

## Key Insights
<!-- Updated: Validation Session 1 - agent automated via gradio_client, not manual browser -->
- **Agent automated testing** — dùng gradio_client gọi API endpoints, report kết quả text
- Test all 3 tabs: Thiết lập, Tiến trình, Kết quả
- Vietnamese labels must render correctly
- Dark theme / Soft blue theme consistency
- gradio_client `.predict()` and `.submit()` for endpoint validation

## Requirements

### Functional
- FR1: Launch app at localhost:7860 in demo mode
- FR2: Test Setup tab: browse, preset dropdown, expert mode, phase checkboxes
- FR3: Test Progress tab: run pipeline, observe progress bar + logs
- FR4: Test Results tab: verify QA/validation/gallery display after run
- FR5: Test Cancel functionality mid-run
- FR6: Test error states: empty dataset path, no phases selected

### Non-Functional
- NFR1: UI responsive at 1080p+ resolution
- NFR2: All Vietnamese labels display correctly (no encoding issues)

## Architecture

### Test Flow
```
1. Launch: DEMO_MODE=1 python -m launcher.gradio_launcher_app
2. User opens http://localhost:7860
3. Test sequence (agent triggers via gradio_client or instructions):
   a. Setup tab → verify all components visible
   b. Browse button → mock dialog returns path
   c. Preset dropdown → change preset, verify estimate updates
   d. Expert mode → toggle, verify fields show/hide
   e. Phase 9 checkbox → toggle, verify real dataset field shows
   f. Run Pipeline → switch to Progress tab
   g. Observe progress bar + log updates
   h. Wait for completion → check Results tab
   i. Cancel test → start run, cancel mid-way
   j. Error test → clear dataset path, try run
```

## Related Code Files

### Files Referenced
- `pipeline/launcher/gradio_launcher_app.py` — Main app to launch
- `pipeline/launcher/ui_dataset_panel.py` — Setup tab
- `pipeline/launcher/ui_progress_panel.py` — Progress tab
- `pipeline/launcher/ui_results_panel.py` — Results tab

## Implementation Steps

1. **Launch app in demo mode**:
   ```bash
   cd pipeline && DEMO_MODE=1 python -m launcher.gradio_launcher_app
   ```
   - Verify app starts without errors
   - Verify status bar shows "Demo Mode" or similar

2. **Test Setup Tab (Thiết lập)**:
   - Verify all Vietnamese labels render: "Thư mục Dataset", "Preset", "Chế độ Expert"
   - Click Browse → verify dialog opens (or mock returns path)
   - Change preset from Pilot → Standard → Full → verify estimate text updates
   - Toggle Expert checkbox → verify number fields appear/disappear
   - Change expert values → verify they stick
   - Check/uncheck Phase 9 → verify real dataset path field shows/hides

3. **Test Progress Tab (Tiến trình)**:
   - Click "Chạy Pipeline" → verify tab switches to Progress
   - Observe progress bar moving from 0% to 100%
   - Observe log display updating with checkpoint lines
   - Verify "Hủy" (Cancel) button appears during run
   - Verify completion message appears

4. **Test Results Tab (Kết quả)**:
   - After run completes, switch to Results tab
   - Verify run summary displays (time, images, phases)
   - Verify QA section shows SSIM and pass rate
   - Verify validation table shows mAP values
   - Verify sample images gallery (may be empty in demo)
   - Verify report buttons present

5. **Test Error Handling**:
   - Leave dataset path empty → click Run → expect error message
   - Uncheck all phases → click Run → expect error message
   - Verify error messages are in Vietnamese

6. **Test Cancel**:
   - Start pipeline → wait 3 seconds → click Cancel
   - Verify pipeline stops and status shows "Đã hủy"

7. **Document issues** found during visual testing

## Todo List
- [x] Launch app in demo mode
- [x] Test Setup tab components and interactions
- [x] Test Progress tab: run, progress bar, logs
- [x] Test Results tab: metrics, gallery
- [x] Test error handling (empty path, no phases)
- [x] Test cancel functionality
- [x] Document all visual/functional issues found

## Success Criteria
- App launches at localhost:7860 without errors
- All 3 tabs functional and navigable
- Vietnamese labels display correctly
- Progress bar updates during demo pipeline run
- Results tab populates after completion
- Error messages shown for invalid inputs
- Cancel stops running pipeline

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Gradio not installed | High | Phase 1 adds to requirements.txt |
| Port 7860 already in use | Low | Use --server-port flag |
| tkinter not available (headless) | Medium | Mock browse_folder in demo mode |

## Security Considerations
- Local testing only (localhost)
- No real data processed

## Next Steps
- Phase 4: Automated unit tests for non-UI components
