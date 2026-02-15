# Phase 3: Gradio Launcher UI

## Context Links
- [Research: GUI Frameworks](research/researcher-01-gui-frameworks.md)
- [Research: Training Patterns](research/researcher-02-training-launcher-patterns.md)
- [Phase 1: Orchestrator](phase-01-pipeline-orchestrator.md)
- [Phase 2: Config Presets](phase-02-config-preset-manager.md)

## Overview
- **Priority**: P1 (core deliverable)
- **Status**: Pending
- **Effort**: 5h
- **Description**: Build Gradio web UI with three panels: (1) dataset selection + config, (2) live progress + logs, (3) results dashboard. User flow: select dataset folder, pick preset, press Run.

## Key Insights
<!-- Updated: Validation Session 1 - Vietnamese UI, all 9 phases, full features, GPU monitor -->
- Gradio `gr.Blocks()` API for custom layouts
- **Vietnamese UI labels** — professional tool for AI engineers
- **All 9 phases** — tabs/sections for LoRA training, generation, post-processing, QA, validation
- Folder picker: Tkinter `askdirectory()` triggered by button, result placed in `gr.Textbox`
- Progress: `gr.Progress()` for bar + generator functions (yield) for streaming
- Logs: Use `gr.Textbox` with streaming updates or `gr.Code` for log display
- Long-running tasks: Run in background thread, update UI via generator/polling
- Gradio 4.x supports `gr.Tab()` for organizing sections
- **GPU monitoring widget** — real-time nvidia-smi polling for temp/VRAM
- **Checkpoint resume** — detect and offer resume for Phase 6
- **Maximum parameter tuning** — expose all config params with Vietnamese tooltips
- Native Linux execution — no WSL path concerns

## Requirements

### Functional
- FR1: Dataset folder selection via browse button (Tkinter) or text input
- FR2: Preset dropdown (Pilot/Standard/Full) with runtime estimate display
- FR3: Expert toggle revealing override fields (total_images, epochs, batch_size, model_size)
- FR4: Real dataset path input for Phase 9 (optional, skips Phase 9 if empty)
- FR5: "Run Pipeline" button that starts orchestrator in background
- FR6: "Cancel" button to stop running pipeline
- FR7: Live log display (scrolling text area)
- FR8: Phase progress indicator (Phase 2/4, overall %)
- FR9: Results tab showing metrics after completion
- FR10: Auto-detect checkpoint and offer "Resume" option

### Non-Functional
- NFR1: < 200 lines per file (split UI into components)
- NFR2: Opens in browser at `localhost:7860`
- NFR3: Responsive layout (works on 1080p+)
- NFR4: Dark theme (matches ML tool conventions)

## Architecture

### File Structure
```
pipeline/launcher/
├── gradio-launcher-app.py     (~180 lines) - Main app, layout, event wiring
├── ui-dataset-panel.py        (~100 lines) - Dataset selection + config components
├── ui-progress-panel.py       (~120 lines) - Progress bar + log display
├── ui-results-panel.py        (~120 lines) - Results dashboard (Phase 5)
```

### UI Layout (3 tabs)
```
┌─────────────────────────────────────────────────┐
│  The Data Mint - One-Click Training Launcher    │
├──────────┬──────────────┬───────────────────────┤
│ Setup    │ Progress     │ Results               │
├──────────┴──────────────┴───────────────────────┤
│                                                  │
│  [Tab: Setup]                                    │
│  ┌─ Dataset Folder ─────────────────────────┐   │
│  │ [____________path______________] [Browse] │   │
│  └──────────────────────────────────────────┘   │
│  ┌─ Config ─────────────────────────────────┐   │
│  │ Preset: [Pilot v]  Est: ~30 min          │   │
│  │                                           │   │
│  │ [x] Expert Mode                           │   │
│  │   Total Images: [500  ]                   │   │
│  │   Epochs:       [20   ]                   │   │
│  │   Batch Size:   [16   ]                   │   │
│  │   Model Size:   [nano v]                  │   │
│  └──────────────────────────────────────────┘   │
│  ┌─ Phases ─────────────────────────────────┐   │
│  │ [x] Phase 6: Generate  [x] Phase 7: Ann │   │
│  │ [x] Phase 8: QA        [ ] Phase 9: Val  │   │
│  │ Real Dataset: [________] [Browse]         │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  [ Resume Checkpoint ] [ Run Pipeline ]          │
│                                                  │
│  [Tab: Progress]                                 │
│  Phase: 1/4 - Batch Generation                  │
│  [=========>                    ] 45%            │
│  ┌─ Live Logs ──────────────────────────────┐   │
│  │ [INFO] Generated 450/500 images...       │   │
│  │ [INFO] Checkpoint saved at job 400       │   │
│  └──────────────────────────────────────────┘   │
│  [ Cancel ]                                      │
│                                                  │
│  [Tab: Results]                                  │
│  (populated by Phase 5 - results-dashboard)      │
└─────────────────────────────────────────────────┘
```

## Related Code Files

### Files to Create
- `pipeline/launcher/gradio-launcher-app.py` (~180 lines) - Main Gradio app
- `pipeline/launcher/ui-dataset-panel.py` (~100 lines) - Setup tab components
- `pipeline/launcher/ui-progress-panel.py` (~120 lines) - Progress tab components

### Existing Files Referenced
- `pipeline/launcher/pipeline-orchestrator.py` (Phase 1)
- `pipeline/launcher/config-preset-manager.py` (Phase 2)

## Implementation Steps

1. Install dependencies: `pip install gradio>=4.0`
2. Create `ui-dataset-panel.py`:
   - `browse_folder()` function using `tkinter.filedialog.askdirectory()`
   - `create_dataset_panel()` returning Gradio components:
     - `gr.Textbox` for dataset path + `gr.Button("Browse")`
     - `gr.Dropdown` for preset selection
     - `gr.Markdown` for runtime estimate
     - `gr.Checkbox("Expert Mode")` controlling visibility of:
       - `gr.Number` for total_images, epochs, batch_size
       - `gr.Dropdown` for model_size
     - `gr.CheckboxGroup` for phases to run
     - `gr.Textbox` for real dataset path (Phase 9)
3. Create `ui-progress-panel.py`:
   - `create_progress_panel()` returning:
     - `gr.Markdown` for current phase label
     - `gr.Slider` or `gr.HTML` for progress bar (read-only)
     - `gr.Textbox(lines=20, max_lines=30)` for log display (streaming)
     - `gr.Button("Cancel")`
   - `update_progress(log_line, progress_state)` function
4. Create `gradio-launcher-app.py`:
   - Import components from ui panels
   - Build `gr.Blocks(theme=gr.themes.Soft(primary_hue="blue"))` layout
   - Wire events:
     - Browse button -> `browse_folder()` -> update textbox
     - Preset dropdown -> `on_preset_change()` -> update estimate + fields
     - Expert checkbox -> toggle override field visibility
     - Run button -> `start_pipeline()` (generator function with yield)
     - Cancel button -> `orchestrator.cancel()`
   - `start_pipeline()` generator:
     - Validate inputs
     - Build config from preset + overrides
     - Create `PipelineOrchestrator`
     - Call `run_all()` in thread
     - Yield log updates and progress to UI components
   - Entry point: `app.launch(server_name="0.0.0.0", server_port=7860)`
5. Handle async/threading:
   - Orchestrator runs in background thread
   - Use `queue.Queue` to pass log lines from callback to generator
   - Generator polls queue and yields updates
6. Add checkpoint detection:
   - On app load, check `pipeline/checkpoints/` for existing checkpoint
   - If found, show "Resume" button with checkpoint info

## Todo List
- [ ] Install Gradio >= 4.0
- [ ] Create `ui-dataset-panel.py` with browse + config components
- [ ] Create `ui-progress-panel.py` with progress bar + log area
- [ ] Create `gradio-launcher-app.py` main layout
- [ ] Wire browse button to Tkinter folder dialog
- [ ] Wire preset dropdown to config manager
- [ ] Wire expert mode toggle to show/hide override fields
- [ ] Implement `start_pipeline()` generator function
- [ ] Wire cancel button to orchestrator.cancel()
- [ ] Add checkpoint detection on app load
- [ ] Add input validation before run (dataset path exists, config valid)
- [ ] Test on Windows with RTX 3090 environment

## Success Criteria
- App launches at `localhost:7860` and displays Setup tab
- Browse button opens native folder dialog and populates path
- Preset selection updates runtime estimate
- Run button starts pipeline; Progress tab shows live logs
- Cancel button stops running pipeline
- Errors shown clearly in UI (red banner or status text)

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Tkinter folder dialog blocks Gradio event loop | High | Run in separate thread; Tkinter root created/destroyed per call |
| Gradio generator doesn't update fast enough | Medium | Poll queue every 0.5s; batch log lines |
| Long-running subprocess freezes UI | High | Background thread + queue pattern; never block main thread |
| Gradio version incompatibility | Low | Pin to >= 4.0; test before release |
| Browser tab closed during run | Medium | Pipeline continues in background; show "running" status on reload |

## Security Considerations
- Gradio runs on localhost only (no public sharing)
- No file upload (only folder path text input)
- Subprocess args validated against path injection
- No authentication needed (local tool)

## Next Steps
- Phase 4 (Progress Tracking) enhances the log parsing for structured progress
- Phase 5 (Results Dashboard) populates the Results tab
