# Benchmark Pipeline - Base Model Comparison

**Document Version**: 1.1
**Last Updated**: 2026-03-03
**Location**: `pipeline/benchmark/`
**Status**: In Progress (Rev01-Rev06 complete, generation paused)

## Overview

The benchmark pipeline compares 6 Stable Diffusion 1.5 base models for LoRA training effectiveness on weld defect X-ray image generation. Includes 1 baseline and 5 challenger models.

**Models** (6 Total):
- **Baseline** — Official Stable Diffusion 1.5
- **MedXRay** (Osama03) — Medical X-ray specialized variant
- **Realistic Vision V5.1** (SG161222) — Photorealism optimized
- **Absolute Reality v1.8.1** (civic-ai) — Balanced quality
- **CyberRealistic V4.2** (sam749) — Stylized aesthetic
- **MedXRay Direct** — Alternative medical X-ray variant

**Purpose**: Determine which base model produces highest-quality synthetic weld defect images when fine-tuned with LoRA, and validate new workflow improvements (VAEEncode + SetLatentNoiseMask, background filtering, composite blending).

**Total LOC**: ~1,350 (10 Python scripts + 1 bash orchestrator)

## Current Status (as of 2026-03-03)

| Phase | Status | Notes |
|-------|--------|-------|
| Model Download | ✓ Complete | All 6 models downloaded |
| Config Generation | ✓ Complete | 30 TOML files (6 models × 5 defects) |
| LoRA Training | ✓ Complete | 25 models trained (5 challengers × 5 defects) |
| Benchmark Generation | 🔄 In Progress | Rev01-Rev06 complete, awaiting ComfyUI restart |
| Metrics Computation | ⏳ Pending | FID/SSIM/Sharpness calculation |
| Report Generation | ⏳ Pending | HTML + JSON output |

**Revisions Completed**:
- Rev01-Rev02: Fixed LoadImage MASK alpha channel bug (ComfyUI extracts from ALPHA, not pixel values)
- Rev03-Rev04: Corrected crack color consistency (dark tones, realistic X-ray appearance)
- Rev05-Rev06: Applied background brightness filter (mean ≥140 on 0-255), composite blending approach
- Current Blocker: ComfyUI API server down (manual restart needed)

---

## Components

### Model Management

**`download-benchmark-models.py`** (237 lines)
- Downloads 4 challenger models from HuggingFace/CivitAI
- VAE download (stabilityai sd-vae-ft-mse-original)
- Model registry JSON for metadata tracking
- Dry-run validation before actual downloads
- **Usage**: `python3 pipeline/benchmark/download-benchmark-models.py [--dry-run]`

**`generate-training-configs.py`** (178 lines)
- Generates 20 TOML configs (5 defects × 4 models)
- Per-model hyperparameter sets (learning rate, batch size, epochs)
- Compatible with kohya-ss training framework
- **Output**: `/models/checkpoints/benchmark/configs/`

**`generate-benchmark-configs.py`** (207 lines)
- Generates batch-config.yaml + prompt templates per model
- Supports deterministic generation (fixed seeds across models)
- ComfyUI workflow variation per model (dynamic checkpoint/VAE loading)
- **Output**: `pipeline/config/benchmark/`

**`train-benchmark-loras.sh`** (124 lines)
- Bash orchestrator for sequential LoRA training (5 models × 5 defects)
- Trains against each base model with identical hyperparameters
- Saves checkpoints for comparison
- **Total training time**: ~60-70 hours (on RTX 3090)

---

## Image Generation

**`run-benchmark-generation.py`** (325 lines)
- Deterministic seed manifest (100 seeds per defect type)
- Generates 500 test images per model (100 per defect type)
- Reuses BatchJobScheduler with model-specific config override
- **Usage**: `python3 pipeline/benchmark/run-benchmark-generation.py [--model {name}] [--all] [--seeds-only]`
- **Output**: `/output/benchmark/{model}/{defect}/`

**`convert-synthetic-to-yolo-format.py`** (176 lines)
- Converts binary masks to YOLO format
- Prepares synthetic data for downstream validation with YOLOv8
- Stratified split per model (train/val/test)
- **Output**: YOLO train/val/test directories per model

---

## Evaluation & Ranking

**`benchmark-metrics-calculator.py`** (119 lines)
- Computes quality metrics:
  - **FID** (Fréchet Inception Distance) — distribution similarity to real data
  - **SSIM** (Structural Similarity) — background coherence
  - **Sharpness** (Laplacian variance) — feature detail quality
- Per-model, per-defect analysis
- Real data comparison against GDXray training set

**`benchmark-evaluation-pipeline.py`** (198 lines)
- Orchestrates full evaluation workflow
- Composite ranking: FID (40%) + SSIM (40%) + Sharpness (20%)
- Generates per-model breakdown + overall recommendation
- **Usage**: `python3 pipeline/benchmark/benchmark-evaluation-pipeline.py [--models {names}]`
- **Output**: `benchmark-results.json`

**`benchmark-html-report-generator.py`** (186 lines)
- Self-contained HTML report with:
  - Ranking table (FID/SSIM/Sharpness per model)
  - Composite scores + recommendation
  - Visual gallery (sample images per model per defect)
  - Statistical comparisons
- **Output**: `benchmark-report.html` (~5-10 MB)

---

## Data Organization

```
models/checkpoints/benchmark/
├── model-registry.json                # Metadata (URLs, sizes, download status)
├── realistic-vision-v51.safetensors   # Downloaded checkpoints (4 files)
├── medical-xray-sd15.safetensors
├── absolute-reality-v181.safetensors
├── cyberrealistic-v42.safetensors
└── configs/
    ├── crack-baseline-config.toml
    ├── crack-medxray-config.toml
    ├── ... (20 configs total)
    └── undercut-cyberreal-config.toml

output/benchmark/
├── seeds.json                         # Deterministic seed manifest
├── baseline/
│   └── {defect}/
│       ├── images/                    # 100 PNG per defect
│       └── masks/
├── medxray/
│   └── ...
├── ... (5 models total)
├── benchmark-results.json             # Metrics summary + ranking
└── benchmark-report.html              # Visual report

kohya-ss/output/benchmark/
├── baseline/
│   └── {defect}/
│       └── xray_{defect}_lora_r32.safetensors
├── medxray/
│   └── ...
└── ... (5 models total, 25 LoRA files)
```

---

## Execution Workflow

1. **Download Models** (~30 min)
   ```bash
   python3 pipeline/benchmark/download-benchmark-models.py
   ```

2. **Generate Training Configs** (~5 min)
   ```bash
   python3 pipeline/benchmark/generate-training-configs.py
   python3 pipeline/benchmark/generate-benchmark-configs.py
   ```

3. **Train LoRAs** (~60-70 hours)
   ```bash
   bash pipeline/benchmark/train-benchmark-loras.sh
   ```

4. **Generate Deterministic Images** (~2 hours)
   ```bash
   python3 pipeline/benchmark/run-benchmark-generation.py --all
   ```

5. **Evaluate & Rank** (~30 min)
   ```bash
   python3 pipeline/benchmark/benchmark-evaluation-pipeline.py
   python3 pipeline/benchmark/benchmark-html-report-generator.py
   ```

**Total Time**: ~65-75 hours (mostly training)

---

## Key Features

- **Deterministic Generation**: Same seeds across all models for fair comparison
- **Fair Hyperparameters**: Identical training settings per defect type
- **Composite Ranking**: Weighted metrics (FID 40%, SSIM 40%, Sharpness 20%)
- **Visual Report**: HTML gallery with per-model, per-defect samples
- **Integration**: Works with existing batch production pipeline

---

## Integration Points

- **Batch Scheduler**: Dynamic checkpoint/VAE selection per job
- **Workflow**: `sd15-lora-controlnet-inpaint-external-vae-workflow.json` supports model-specific VAE
- **Config Generation**: Model-specific batch-config.yaml generation

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Model Coverage | 5 models | baseline + 4 challengers |
| Defect Coverage | 5 defects | crack, porosity, inclusion, LOF, undercut |
| Test Images | 500 total | 100 per defect type per model |
| Training Consistency | <2% variance | Same hyperparams across models |
| Report Completeness | 100% | HTML + JSON outputs |

---

**Last Updated**: 2026-02-16
