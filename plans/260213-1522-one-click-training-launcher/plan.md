---
title: "One-Click Training Launcher"
description: "Gradio-based professional launcher UI (Vietnamese) for all 9 pipeline phases with full parameter tuning"
status: pending
priority: P1
effort: 30h
branch: feat/one-click-launcher
tags: [gradio, launcher, ui, pipeline-orchestration, vietnamese, full-pipeline]
created: 2026-02-13
---

# One-Click Training Launcher

## Goal
Professional Gradio web UI (Vietnamese) for AI engineers. Cover all 9 pipeline phases with maximum parameter fine-tuning. Core UX: **chọn dataset → bấm Run**.

## Architecture
```
Gradio UI (localhost:7860) - Vietnamese labels
    |
PipelineOrchestrator  -->  ConfigPresetManager
    |
Phase 1-4 (setup) -> 5 (masks) -> 6 (gen) -> 7 (annot) -> 8 (QA) -> 9 (validation)
```

## New Files (`pipeline/launcher/`)
| File | Purpose |
|------|---------|
| `pipeline-orchestrator.py` | Wraps all 9 phases sequentially via subprocess |
| `config-preset-manager.py` | Tiered presets + full parameter overrides |
| `gradio-launcher-app.py` | Main Gradio UI entry point (Vietnamese) |
| `progress-tracker.py` | Parse subprocess stdout for real-time progress |
| `results-dashboard.py` | Post-run metrics, mAP, gallery display |
| `launcher-utils.py` | Path validation, GPU monitoring, helpers |
| `error-handler.py` | Pre-flight checks, error recovery |
| `ui-*.py` | UI panel components (dataset, progress, results, lora) |

## Phases

| # | Phase | Effort | Status |
|---|-------|--------|--------|
| 1 | [Pipeline Orchestrator](phase-01-pipeline-orchestrator.md) | 5h | ✅ done |
| 2 | [Config Preset Manager](phase-02-config-preset-manager.md) | 3h | ✅ done |
| 3 | [Gradio Launcher UI](phase-03-gradio-launcher-ui.md) | 8h | ✅ done |
| 4 | [Progress Tracking](phase-04-progress-tracking.md) | 4h | ✅ done |
| 5 | [Results Dashboard](phase-05-results-dashboard.md) | 4h | ✅ done |
| 6 | [Testing & Polish](phase-06-testing-and-polish.md) | 6h | ✅ done |

## Key Decisions
- **Gradio** for UI — ML-native, fast dev, web-based
- **Vietnamese UI** — professional tool for AI engineers
- **All 9 phases** — full pipeline coverage, not just phases 6-9
- **Full features** — presets + expert mode + GPU monitor + checkpoint resume + training history
- **Native Linux** — no WSL, direct Linux execution
- **Phase 9 optional** — unchecked by default, user provides real dataset path when needed
- **Maximum parameter tuning** — expose all tunables with Vietnamese descriptions

## Validation Log

### Session 1 — 2026-02-13
**Trigger:** Initial plan creation validation
**Questions asked:** 6

#### Questions & Answers

1. **[Architecture]** The pipeline scripts use WSL Linux paths (/mnt/e/...) but you're on Windows 11. How should the Gradio launcher execute pipeline scripts?
   - Options: Gradio on Windows, call WSL | Everything in WSL (Recommended) | Gradio on Windows, native Python
   - **Answer:** Other
   - **Custom input:** "Tôi sẽ run dự án này trên linux thực sự, nên mọi thứ phải thực hiện phù hợp với linux"
   - **Rationale:** Native Linux execution. No WSL/Windows path translation needed. Simplifies subprocess calls and path handling.

2. **[Scope]** Should the launcher scope include LoRA training (Phase 3) or only image generation + validation (Phases 6-9)?
   - Options: Phases 6-9 only (Recommended) | Include LoRA training | Phases 6-9 now, LoRA later
   - **Answer:** Other
   - **Custom input:** "Tôi không yêu cầu bạn chạy dự án này, tôi muốn làm giao diện cho dự án này, để dễ dàng khởi chạy thay vì gõ lệnh, tôi sẽ bấm nút."
   - **Rationale:** User wants UI for the ENTIRE pipeline — button-based launching instead of CLI commands for all phases.

3. **[Scope]** Phase 9 validation requires --real-yolo-dir. Where is this dataset, and should Phase 9 be optional?
   - Options: Phase 9 optional, skip by default | Phase 9 required, I have the data | Phase 9 required, create it first
   - **Answer:** Phase 9 optional, skip by default
   - **Rationale:** Phase 9 unchecked by default. User provides real dataset path when they want validation.

4. **[UI]** How complex should the launcher UI be?
   - Options: Minimal: presets + run (Recommended) | Standard: presets + expert override | Full: all features
   - **Answer:** Full: all features
   - **Rationale:** Presets + expert mode + GPU monitoring + checkpoint resume + training history (SQLite).

5. **[Scope]** Should the launcher cover ALL 9 phases or just automated phases?
   - Options: Phases 5-9 | Phases 6-9 only | All 9 phases | Phases 3, 6-9
   - **Answer:** All 9 phases
   - **Rationale:** Full pipeline UI including LoRA training, preprocessing, workflow design, mask gen, batch gen, post-proc, QA, validation.

6. **[UI]** Should the UI language be Vietnamese or English?
   - Options: English (Recommended) | Vietnamese | Bilingual
   - **Answer:** Other
   - **Custom input:** "Tiếng Việt, phần mềm này được xác định là một phần mềm chuyên nghiệp, dành riêng cho kỹ sư AI. Nên cần hỗ trợ tinh chỉnh tham số tối đa nhất có thể"
   - **Rationale:** Vietnamese UI for professional AI engineers. Maximum parameter tuning capability required.

#### Confirmed Decisions
- **Execution**: Native Linux (no WSL) — simplifies path handling
- **Scope**: All 9 pipeline phases — full UI coverage
- **Language**: Vietnamese — professional tool for AI engineers
- **UI complexity**: Full features — presets, expert mode, GPU monitor, checkpoint resume, history
- **Phase 9**: Optional, unchecked by default — user provides real dataset when needed
- **Parameters**: Maximum fine-tuning — expose all tunables with Vietnamese descriptions

#### Action Items
- [ ] Expand Phase 1 orchestrator to cover all 9 phases (was 6-9 only)
- [ ] Add LoRA training phase support (kohya-ss TOML configs)
- [ ] Add Vietnamese UI labels/translations throughout Phase 3
- [ ] Add GPU monitoring (nvidia-smi) to progress tracking
- [ ] Add SQLite training history to results dashboard
- [ ] Increase effort estimates for expanded scope (~30h total)
- [ ] Remove all WSL-specific path handling; use Linux paths only

#### Impact on Phases
- Phase 1: Expand orchestrator from 4 phases to 9 phases. Add kohya-ss/LoRA subprocess commands.
- Phase 2: Add presets that cover LoRA training params (rank, alpha, epochs, lr). Expand parameter space.
- Phase 3: Vietnamese labels for all UI elements. Add tabs for each major pipeline section. Add GPU monitor widget.
- Phase 4: Add log parsing for LoRA training (kohya-ss output format). Add GPU temp display.
- Phase 5: Add SQLite training history. Show LoRA training metrics alongside validation metrics.
- Phase 6: More tests needed for 9-phase coverage. Linux-only launch scripts (no .bat).
