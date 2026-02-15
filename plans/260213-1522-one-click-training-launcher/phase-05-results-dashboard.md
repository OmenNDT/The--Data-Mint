# Phase 5: Results Dashboard

## Context Links
- [Codebase Summary](../../docs/codebase-summary.md) - QA and validation output formats
- [System Architecture](../../docs/system-architecture.md) - Output file locations
- [Phase 3: Gradio UI](phase-03-gradio-launcher-ui.md) - Results tab container

## Overview
- **Priority**: P2 (post-completion UX)
- **Status**: Pending
- **Effort**: 3h
- **Description**: After pipeline completes, populate the Results tab with QA metrics, validation mAP scores, per-class breakdown, sample generated images, and links to full reports.

## Key Insights
<!-- Updated: Validation Session 1 - Add SQLite training history + LoRA training metrics -->
- Phase 3 produces LoRA safetensors + training logs (loss curves)
- Phase 8 outputs `qa-results.json` with SSIM scores, annotation validation results
- Phase 9 outputs `validation-results.json` with mAP per experiment, per-class metrics
- Phase 8 generates `spot-check-gallery.html` (self-contained HTML)
- Phase 9 generates trained model weights at `results/{experiment}/weights/best.pt`
- Generated images stored in `output/synthetic/{defect_type}/`
- Gradio has `gr.Gallery`, `gr.DataFrame`, `gr.JSON`, `gr.HTML` widgets
- **SQLite training history** — persist results across sessions for comparison
- **LoRA training metrics** — display alongside validation metrics

## Requirements

### Functional
- FR1: Display QA summary (SSIM mean, pass rate, annotation check pass/fail)
- FR2: Display validation mAP table (per experiment: ratio, mAP@0.5, mAP@0.5:0.95)
- FR3: Display per-class precision/recall table
- FR4: Show sample generated images in gallery (random 12 from output)
- FR5: Link to full reports (qa-report.md, validation-report.md, spot-check gallery)
- FR6: Show "optimal ratio" recommendation from validation
- FR7: Display pipeline run summary (total time, phases completed, image count)

### Non-Functional
- NFR1: < 200 lines per file
- NFR2: Results persist after tab switch (no reload needed)
- NFR3: Handle partial results (e.g., Phase 9 skipped)

## Architecture

```
ResultsDashboard
├── __init__(output_base_dir)
├── load_qa_results() -> Optional[QAResults]
├── load_validation_results() -> Optional[ValidationResults]
├── get_sample_images(count=12) -> List[Path]
├── get_run_summary() -> RunSummary
└── format_for_gradio() -> dict  # all components data
```

### Results Tab Layout
```
┌─ Results ─────────────────────────────────────┐
│                                                │
│ Run Summary                                    │
│ ┌────────────────────────────────────────────┐ │
│ │ Total Time: 4h 32m | Images: 5,000        │ │
│ │ Phases: 6 OK, 7 OK, 8 OK, 9 OK            │ │
│ └────────────────────────────────────────────┘ │
│                                                │
│ QA Results                                     │
│ ┌────────────────────────────────────────────┐ │
│ │ SSIM: 0.94 mean | Pass Rate: 97%          │ │
│ │ Annotations: COCO OK | YOLO OK             │ │
│ └────────────────────────────────────────────┘ │
│                                                │
│ Validation Results                             │
│ ┌────────────────────────────────────────────┐ │
│ │ Ratio    │ mAP@0.5 │ mAP@0.5:0.95        │ │
│ │ Real-only│  0.42   │  0.28                │ │
│ │ 50/50    │  0.61   │  0.39                │ │
│ │ Synth    │  0.55   │  0.34                │ │
│ │ Optimal: 50% synthetic ratio               │ │
│ └────────────────────────────────────────────┘ │
│                                                │
│ Sample Images                                  │
│ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐               │
│ │  │ │  │ │  │ │  │ │  │ │  │               │
│ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘               │
│ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐               │
│ │  │ │  │ │  │ │  │ │  │ │  │               │
│ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘               │
│                                                │
│ [ Open QA Report ] [ Open Validation Report ]  │
└────────────────────────────────────────────────┘
```

## Related Code Files

### Files to Create
- `pipeline/launcher/results-dashboard.py` (~180 lines) - Results loading + formatting
- `pipeline/launcher/ui-results-panel.py` (~120 lines) - Gradio Results tab components (from Phase 3)

### Existing Files Referenced (read-only)
- `pipeline/qa/qa-pipeline-main.py` - `qa-results.json` schema
- `pipeline/validation/evaluation-metrics.py` - `validation-results.json` schema

## Implementation Steps

1. Analyze output file formats:
   - Read `qa-pipeline-main.py` to understand `qa-results.json` structure
   - Read `evaluation-metrics.py` to understand `validation-results.json` structure
2. Create `results-dashboard.py`:
   - `QAResults` dataclass: `ssim_mean`, `ssim_std`, `pass_rate`, `coco_valid`, `yolo_valid`
   - `ValidationResults` dataclass: `experiments` (list of dicts with ratio, mAP values), `optimal_ratio`
   - `RunSummary` dataclass: `total_seconds`, `images_generated`, `phases_completed`
3. Implement `load_qa_results()`:
   - Read `output/qa-reports/qa-results.json`
   - Parse into `QAResults`
   - Return `None` if file doesn't exist
4. Implement `load_validation_results()`:
   - Read `output/validation/validation-results.json`
   - Parse into `ValidationResults`
   - Return `None` if file doesn't exist (Phase 9 skipped)
5. Implement `get_sample_images(count=12)`:
   - Scan `output/synthetic/` for PNG files
   - Random sample of `count` images (stratified across defect types)
   - Return list of absolute paths
6. Create `ui-results-panel.py`:
   - `create_results_panel()` returning Gradio components:
     - `gr.Markdown` for run summary
     - `gr.DataFrame` for QA metrics
     - `gr.DataFrame` for validation mAP table
     - `gr.Gallery(columns=6)` for sample images
     - `gr.Button("Open QA Report")`, `gr.Button("Open Validation Report")`
   - `populate_results(dashboard)` function to fill components with data
7. Wire report buttons:
   - Open markdown/HTML report files in default browser via `webbrowser.open()`

## Todo List
- [ ] Analyze `qa-results.json` format from qa-pipeline-main.py
- [ ] Analyze `validation-results.json` format from evaluation-metrics.py
- [ ] Create `QAResults`, `ValidationResults`, `RunSummary` dataclasses
- [ ] Implement `load_qa_results()`
- [ ] Implement `load_validation_results()`
- [ ] Implement `get_sample_images()`
- [ ] Create `ui-results-panel.py` with Gradio components
- [ ] Wire "Open Report" buttons to browser
- [ ] Handle missing results gracefully (show "Phase skipped" message)

## Success Criteria
- QA results displayed correctly when `qa-results.json` exists
- Validation mAP table shows all experiments with metrics
- Sample images display in gallery grid
- Report buttons open files in browser
- Graceful handling when Phase 9 skipped (no validation section)

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| JSON output format not documented | Medium | Read source code to determine schema; add validation |
| Large image gallery slows UI | Low | Limit to 12 thumbnails; lazy loading |
| Report files not found after partial run | Medium | Check file existence; show "not available" message |

## Security Considerations
- Only reads local output files
- `webbrowser.open()` opens local files only
- No data uploaded or transmitted

## Next Steps
- Integrate into Phase 3 (Gradio UI) Results tab
- Phase 6 (Testing) validates end-to-end flow including results display
