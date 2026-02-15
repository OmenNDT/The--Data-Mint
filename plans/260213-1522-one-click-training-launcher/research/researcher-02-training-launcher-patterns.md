# One-Click ML Training Launcher Patterns Research

**Project**: The Data Mint - One-Click Training Launcher
**Date**: 2026-02-13
**Researcher**: researcher-02

## Executive Summary

Researched pipeline orchestration, config presets, progress tracking, and dataset selection patterns for wrapping multi-step CLI pipeline into a "select dataset + press run" launcher. Key finding: config presets + unified orchestrator + real-time progress is the proven pattern.

---

## 1. Pipeline Orchestration Patterns

### Unified Orchestrator Pattern
Wrap all pipeline phases into a single Python entry point:
```python
class PipelineOrchestrator:
    def run(self, dataset_path, preset="standard"):
        self.run_generation(config)      # Phase 6
        self.run_post_processing()       # Phase 7
        self.run_qa()                    # Phase 8
        self.run_validation()            # Phase 9
```

### CLI Orchestration (Click/Typer)
- Click command groups: hierarchical CLI structures for complex toolchains
- Typer: type-hint-based CLI, good for ML pipelines
- `subprocess.run()` for invoking existing scripts
- Click's `CliRunner` for testing CLI in isolation

### ComfyUI API Wrappers
- **comfy-api-simplified**: small wrapper, edit & queue workflows programmatically
- **ComfyUI API Wrapper (ai-dock)**: FastAPI wrapper with async/sync/streaming
- **comfy-pack**: package workflows as production APIs
- Native approach: direct HTTP to `/api/prompt`, `/api/status`

---

## 2. Configuration Presets

### Tiered Preset Pattern
```yaml
presets:
  pilot:
    total_images: 500
    epochs: 20
    description: "Quick test run (~30min)"
  standard:
    total_images: 5000
    epochs: 50
    description: "Standard training (~4h)"
  full:
    total_images: 20000
    epochs: 100
    description: "Full production (~18h)"
```

### Key Design Principles
- Encode best practices into presets (from SageMaker pattern)
- Allow expert override of individual params
- Show estimated time for each preset
- Store as YAML alongside existing configs

---

## 3. Progress Tracking for Long-Running Jobs

### Multi-Level Progress
1. **Pipeline level**: Phase 1/4, Phase 2/4, etc.
2. **Phase level**: 1,500/20,000 images generated
3. **Metrics level**: Current GPU temp, ETA, throughput

### Implementation Pattern
- Parse stdout lines from subprocess
- Regex match progress indicators (e.g., `[CHECKPOINT] Generated 1000 images`)
- Calculate ETA from throughput
- Update UI progress bar + status text

### Checkpoint Resume
- Existing checkpoint system (every 100 images) already supports resume
- UI should detect existing checkpoints and offer "Resume" option

---

## 4. Dataset Selection UX

### Patterns from Industry Tools
- **Ultralytics HUB**: Upload dataset → auto-detect format → train
- **Roboflow**: Drag-drop images → label → export → train (one-click)
- **YOLO Train Detection GUI**: CustomTkinter GUI, select model + data.yaml, press train
- **YOLOv8 Web UI**: Label + train + inference in single GUI

### Recommended UX Flow
1. Browse/select folder containing YOLO-format dataset
2. Auto-detect `data.yaml` in folder
3. Display dataset stats (image count, class distribution)
4. Select preset or customize params
5. Press "Start Training"

---

## 5. Error Recovery Patterns

- **Auto-resume**: Detect checkpoint files on startup, offer resume
- **Phase isolation**: Each phase saves outputs independently; can restart from any phase
- **Graceful degradation**: If QA fails, show warning but don't abort (user decides)
- **Log persistence**: Save all logs to file for post-mortem analysis

---

## 6. Training Result Presentation

### After Training Completes
- mAP@0.5 summary table per experiment
- Per-class precision/recall breakdown
- Loss curves (if available from Ultralytics output)
- Sample prediction images (before/after)
- Comparison chart: real-only vs mixed vs synth-only
- Export results as markdown/PDF report

---

## 7. Reference Implementations

| Tool | Stack | Features |
|------|-------|----------|
| [YOLO Train Detection GUI](https://github.com/SpreadKnowledge/YOLO_train_detection_GUI) | CustomTkinter + Ultralytics | Train, detect, webcam. Supports YOLOv12 |
| [YOLOv8 Web UI](https://www.digitalocean.com/community/tutorials/introducing-the-yolov8-web-ui) | Web-based | Label + train + inference |
| Ultralytics HUB | Cloud | Upload → train → deploy |
| Roboflow | Cloud | Full pipeline, one-click train |

---

## Architecture Recommendation

```
┌─────────────────────────────────────────┐
│          Gradio UI (localhost)           │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ Dataset   │  │ Config   │  │  Run  │ │
│  │ Selector  │  │ Presets  │  │  Btn  │ │
│  └──────────┘  └──────────┘  └───────┘ │
│  ┌──────────────────────────────────┐   │
│  │      Progress + Live Logs        │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │      Results Dashboard           │   │
│  └──────────────────────────────────┘   │
└──────────────┬──────────────────────────┘
               │
    ┌──────────▼──────────┐
    │ PipelineOrchestrator │
    │  - Config loader     │
    │  - Preset manager    │
    │  - Phase runner      │
    │  - Progress tracker  │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Existing Pipeline   │
    │  - batch-production  │
    │  - post-processing   │
    │  - qa-pipeline       │
    │  - validation        │
    └─────────────────────┘
```

---

## Sources

- [YOLO Train Detection GUI](https://github.com/SpreadKnowledge/YOLO_train_detection_GUI)
- [YOLOv8 Web UI - DigitalOcean](https://www.digitalocean.com/community/tutorials/introducing-the-yolov8-web-ui)
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [Roboflow YOLO Guide](https://blog.roboflow.com/guide-to-yolo-models/)
- [SageMaker AI Projects Templates](https://aws.amazon.com/blogs/machine-learning/simplify-modelops-with-amazon-sagemaker-ai-projects-using-amazon-s3-based-templates/)
- [ComfyUI API Wrapper](https://github.com/ai-dock/comfyui-api-wrapper)
- [comfy-api-simplified](https://pypi.org/project/comfy-api-simplified/)
- [Click Advanced Patterns](https://click.palletsprojects.com/en/stable/advanced/)
- [Building CLI Tools with Click and Typer](https://inventivehq.com/blog/python-cli-tools-guide)

---

## Unresolved Questions

1. Should the launcher also handle LoRA training (Phase 3) or only inference+validation?
2. Should preset configs be user-editable via UI or only selectable?
3. Need for multi-user support or single-user local tool?
