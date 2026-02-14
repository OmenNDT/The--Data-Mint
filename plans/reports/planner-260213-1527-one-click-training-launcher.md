# Planner Report: One-Click Training Launcher

**Date**: 2026-02-13
**Plan**: `plans/260213-1522-one-click-training-launcher/`

## Summary

Created 7-file implementation plan to transform The Data Mint from 4+ CLI commands into a Gradio-based one-click launcher. User flow: select dataset folder, pick preset, press Run. Pipeline phases 6-9 execute sequentially via subprocess orchestration.

## Plan Structure

```
plans/260213-1522-one-click-training-launcher/
├── plan.md                              # Overview (68 lines)
├── phase-01-pipeline-orchestrator.md    # Subprocess wrapper for phases 6-9
├── phase-02-config-preset-manager.md    # Pilot/Standard/Full presets
├── phase-03-gradio-launcher-ui.md       # Web UI with 3 tabs
├── phase-04-progress-tracking.md        # Real-time log parsing
├── phase-05-results-dashboard.md        # Post-run metrics display
├── phase-06-testing-and-polish.md       # Tests, error handling, scripts
├── research/                            # 2 research reports (pre-existing)
└── scout/                               # Scout report (pre-existing)
```

## Key Architecture Decisions

1. **Gradio** over PySide6 - fastest dev path, ML-native widgets, sufficient for single-page launcher
2. **Subprocess wrapping** - no refactoring of existing pipeline scripts; run via `subprocess.Popen`
3. **Tkinter hybrid** - folder picker via `tkinter.filedialog.askdirectory()` since Gradio lacks native folder browser
4. **3 presets** - Pilot (500 imgs, ~30min), Standard (5K, ~4h), Full (20K, ~18h) with expert override
5. **Sequential phases** - 6 -> 7 -> 8 -> 9, each as separate subprocess

## New Files to Create

| File | LOC | Purpose |
|------|-----|---------|
| `pipeline/launcher/__init__.py` | ~20 | Module exports |
| `pipeline/launcher/pipeline-orchestrator.py` | ~180 | Phase 6-9 orchestration |
| `pipeline/launcher/phase-runner.py` | ~150 | Subprocess execution |
| `pipeline/launcher/config-preset-manager.py` | ~160 | Preset loading/validation |
| `pipeline/launcher/gradio-launcher-app.py` | ~180 | Main Gradio UI |
| `pipeline/launcher/ui-dataset-panel.py` | ~100 | Setup tab |
| `pipeline/launcher/ui-progress-panel.py` | ~120 | Progress tab |
| `pipeline/launcher/ui-results-panel.py` | ~120 | Results tab |
| `pipeline/launcher/progress-tracker.py` | ~180 | Log parsing + ETA |
| `pipeline/launcher/results-dashboard.py` | ~180 | Results data loading |
| `pipeline/launcher/launcher-utils.py` | ~80 | Path helpers |
| `pipeline/launcher/error-handler.py` | ~100 | Preflight checks |
| `pipeline/config/presets/pilot.yaml` | ~25 | Pilot preset |
| `pipeline/config/presets/standard.yaml` | ~25 | Standard preset |
| `pipeline/config/presets/full.yaml` | ~25 | Full preset |
| `pipeline/run-launcher.sh` | ~15 | Linux launch script |
| `pipeline/run-launcher.bat` | ~10 | Windows launch script |
| **Total** | **~1,670** | |

## Effort Estimate

| Phase | Hours | Dependencies |
|-------|-------|--------------|
| 1. Pipeline Orchestrator | 3h | None |
| 2. Config Preset Manager | 2h | None |
| 3. Gradio Launcher UI | 5h | Phases 1, 2 |
| 4. Progress Tracking | 3h | Phase 1 |
| 5. Results Dashboard | 3h | Phase 3 |
| 6. Testing & Polish | 2h | All above |
| **Total** | **18h** | |

Phases 1 and 2 can be implemented in parallel. Phase 3 depends on both.

## Unresolved Questions

1. Should launcher handle LoRA training (Phase 3) or only inference+validation?
2. Should preset configs be user-editable in UI or only selectable?
3. Need GPU utilization display (nvidia-smi polling) in progress panel?
4. Should training history persist across sessions (SQLite) or just show last run?
5. Where is the real YOLO dataset for Phase 9 `--real-yolo-dir`? (required arg, no default)
