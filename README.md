# The Data Mint - Synthetic Weld Defect X-ray Factory

A complete end-to-end pipeline for generating 20K-100K annotated synthetic X-ray images of weld defects using Stable Diffusion 1.5, LoRA fine-tuning, and ControlNet inpainting. Produces publication-ready datasets in COCO and YOLO formats for training defect detection models.

## Quick Facts

- **Status**: Production Ready (All 9 phases complete)
- **Output**: 20,000-100,000 synthetic weld defect X-ray images with COCO + YOLO annotations
- **Defect Types**: 5 (crack, porosity, inclusion, lack of fusion, undercut)
- **Throughput**: ~1,097 images/hour (20K in ~18 hours, 100K in ~4 days)
- **Hardware**: Dual Xeon E5-2696v4 (44c/88t) + RTX 3090 24GB + 64GB ECC RAM
- **Tech Stack**: SD 1.5 + LoRA (kohya-ss) + ControlNet v1.1 + ComfyUI API + Python orchestration

## Architecture Overview

```
┌─ GENERATION (Phases 1-6) ─────────────────────┐
│  [GDXray] → [Preprocess] → [Train LoRAs]      │
│  [Masks] → [ComfyUI Inpaint] → [Synthetic]    │
└────────────────────────────────────────────────┘
        ↓
┌─ POST-PROCESSING (Phase 7) ──────────────────┐
│  [Raw Output] → [COCO + YOLO] → [Split]      │
└────────────────────────────────────────────────┘
        ↓
┌─ QUALITY ASSURANCE (Phase 8) ────────────────┐
│  [SSIM Check] → [Validation] → [Report]      │
└────────────────────────────────────────────────┘
        ↓
┌─ VALIDATION (Phase 9) ───────────────────────┐
│  [YOLOv8 Training] → [mAP Testing] → [Report]│
└────────────────────────────────────────────────┘
```

## Getting Started

### Prerequisites

1. **ComfyUI Setup** (Phase 1)
   ```bash
   cd /mnt/e/The\ Data\ Mint/comfyui
   python main.py --listen 172.21.192.1 --port 8188
   ```

2. **LoRA Models** (Phase 3)
   - 5 pre-trained LoRA models in `/mnt/e/The Data Mint/kohya-ss/output/`
   - Models: crack, porosity, inclusion, lack_of_fusion, undercut (rank 32)

3. **Python Environment** (Phase 1)
   ```bash
   cd /mnt/e/The\ Data\ Mint/pipeline
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

### Quick Start: One-Click Launcher (Recommended)

**Start the Gradio UI** (easiest way to run the pipeline):
```bash
cd /mnt/e/The\ Data\ Mint/pipeline
python3 launcher/gradio_launcher_app.py
```

Then open your browser to `http://localhost:7860`

**Features**:
- Select preset: Pilot (500 images), Standard (20K), Full (100K)
- Click "Start" → monitor progress in real-time
- Temperature, throughput graphs, error alerts
- Download COCO/YOLO datasets after completion

### Run the Pipeline

**Option 1: Full Pipeline (recommended)**
```bash
cd /mnt/e/The\ Data\ Mint/pipeline

# 1. Generate 20K synthetic images
./run-batch-production.sh

# 2. Convert to COCO + YOLO format
./run-post-processing.sh

# 3. Run quality assurance checks
python3 qa/qa-pipeline-main.py --dataset-dir ../output/dataset

# 4. Validate with YOLOv8 training
python3 validation/validation-main.py --synth-yolo-dir ../output/dataset/yolo
```

**Option 2: Batch Production Only**
```bash
cd /mnt/e/The\ Data\ Mint/pipeline
python3 batch_manager/batch-production-main.py --config config/batch-config.yaml
```

**Option 3: Pilot Mode (500 test images)**
```bash
cd /mnt/e/The\ Data\ Mint/pipeline
python3 batch_manager/batch-production-main.py --config config/batch-config.yaml --pilot-mode
```

## Directory Structure

```
/mnt/e/The Data Mint/
├── README.md                              # This file
├── repomix-output.xml                     # Full codebase compaction
│
├── docs/                                  # Documentation
│   ├── project-overview-pdr.md            # Product requirements
│   ├── codebase-summary.md                # Component overview
│   ├── code-standards.md                  # Dev conventions
│   ├── system-architecture.md             # Architecture deep-dive
│   └── project-roadmap.md                 # Phase status & roadmap
│
├── pipeline/                              # Main pipeline code (~6,800 lines)
│   ├── batch_manager/                     # Phase 6: Batch orchestration
│   │   ├── batch-production-main.py       # Entry point
│   │   ├── batch-job-scheduler.py         # Job queue management
│   │   ├── comfyui-rest-api-client.py     # ComfyUI API wrapper
│   │   ├── mask-prefetch-worker-pool.py   # Parallel mask generation
│   │   ├── gpu-thermal-monitor.py         # Temperature management
│   │   └── checkpoint-state-manager.py    # Progress checkpoints
│   │
│   ├── mask_generator/                    # Phase 5: Procedural masks
│   │   ├── crack-mask-generator.py        # Crack defects
│   │   ├── porosity-mask-generator.py     # Porosity defects
│   │   ├── slag-inclusion-mask-generator.py
│   │   ├── lack-of-fusion-mask-generator.py
│   │   ├── undercut-mask-generator.py
│   │   └── base-defect-mask-generator.py  # Base class
│   │
│   ├── post_processing/                   # Phase 7: Annotation export
│   │   ├── post-processing-main.py        # Entry point
│   │   ├── mask-to-annotation-converter.py # Polygon generation
│   │   ├── coco-dataset-builder.py        # COCO JSON format
│   │   ├── yolo-dataset-builder.py        # YOLO TXT format
│   │   └── dataset-splitter.py            # Train/val/test split
│   │
│   ├── qa/                                # Phase 8: QA pipeline
│   │   ├── qa-pipeline-main.py            # Entry point
│   │   ├── ssim-background-checker.py     # Background similarity
│   │   ├── annotation-validator.py        # Annotation checks
│   │   └── visual-spot-check-grid.py      # HTML gallery generation
│   │
│   ├── validation/                        # Phase 9: YOLOv8 validation
│   │   ├── validation-main.py             # Experiment orchestrator
│   │   ├── yolo-trainer.py                # Model training
│   │   └── evaluation-metrics.py          # mAP & metrics
│   │
│   ├── launcher/                          # One-click Gradio UI
│   │   ├── gradio_launcher_app.py         # Main UI entry point
│   │   ├── pipeline_orchestrator.py       # Phase management
│   │   ├── phase_runner.py                # Subprocess executor
│   │   ├── progress_tracker.py            # Log parser
│   │   ├── ui_progress_panel.py           # Progress dashboard
│   │   ├── ui_results_panel.py            # Results view
│   │   ├── ui_dataset_panel.py            # Dataset explorer
│   │   ├── error_handler.py               # Error categorization
│   │   ├── config_preset_manager.py       # Preset management
│   │   └── demo_pipeline_runner.py        # Demo mode
│   │
│   ├── tests/                             # Unit & integration tests
│   │   ├── test-mask-generator-unit-tests.py
│   │   ├── test-comfyui-workflow-validation.py
│   │   ├── test-config-preset-manager.py
│   │   ├── test-progress-tracker.py
│   │   └── test-error-handler.py
│   │
│   ├── config/                            # Configuration files
│   │   ├── batch-config.yaml              # Batch parameters
│   │   └── mask-config.yaml               # Mask generation config
│   │
│   ├── comfyui-workflows/                 # ComfyUI JSON workflows
│   │   ├── sd15-lora-controlnet-inpaint-single-defect-workflow.json
│   │   └── defect-type-prompt-templates.yaml
│   │
│   ├── comfyui-api-batch-inpaint-client.py # Phase 6: Core API client
│   ├── run-batch-production.sh             # Batch orchestration script
│   ├── run-post-processing.sh              # Post-processing script
│   └── PIPELINE-OVERVIEW.md                # Detailed pipeline guide
│
├── kohya-ss/                              # LoRA training (Phase 3)
│   ├── train-all-loras-wsl.sh             # Batch training orchestrator
│   ├── check-training-status.sh           # Progress monitor
│   ├── configs/                           # 5 TOML training configs
│   │   ├── crack-lora-training-config.toml
│   │   ├── porosity-lora-training-config.toml
│   │   ├── inclusion-lora-training-config.toml
│   │   ├── lack-of-fusion-lora-training-config.toml
│   │   └── undercut-lora-training-config.toml
│   ├── training_data/                     # Training images (5 defect types)
│   └── output/                            # Trained LoRA safetensors
│
├── dataset/                               # Phase 2: Data preprocessing
│   ├── gdxray/                            # GDXray W0003 raw images
│   ├── processed/                         # Preprocessed 512x512 patches
│   └── scripts/                           # Preprocessing utilities
│
├── output/                                # Generated outputs
│   ├── synthetic/                         # Phases 6 output
│   │   ├── crack/
│   │   ├── porosity/
│   │   ├── inclusion/
│   │   ├── lack_of_fusion/
│   │   └── undercut/
│   ├── dataset/                           # Phase 7 output
│   │   ├── annotations/                   # COCO JSON
│   │   ├── yolo/                          # YOLO format
│   │   └── post-processing-report.txt
│   ├── qa-reports/                        # Phase 8 output
│   │   ├── qa-report.md
│   │   ├── qa-results.json
│   │   └── spot-check-gallery.html
│   └── validation/                        # Phase 9 output
│       ├── validation-report.md
│       └── validation-results.json
│
├── plans/                                 # Implementation plans
│   └── 260130-0849-the-data-mint-xray-defect-pipeline/
│       ├── plan.md                        # Master plan (all 9 phases)
│       ├── phase-01 through phase-09.md   # Phase details
│       └── reports/                       # Research & analysis
│
└── comfyui/                               # Symlink to ComfyUI installation
```

## Key Features

### 1. Automated Batch Generation (Phase 6)
- Parallel mask prefetching (8 CPU workers)
- ComfyUI queue management with retry logic
- GPU thermal monitoring (pause at 85°C, resume at 75°C)
- Checkpoint every 100 images for fault tolerance
- ~1,097 images/hour throughput

### 2. Procedural Mask Generation (Phase 5)
- 5 defect-specific generators (crack, porosity, inclusion, LOF, undercut)
- Morphological operations for realistic defect shapes
- ROI constraint to keep defects within weld area
- Feathering for smooth inpainting boundaries

### 3. Annotation Export (Phase 7)
- **COCO Format**: Full bounding boxes + segmentation masks
- **YOLO Format**: Class + normalized bbox per image
- Automatic train/val/test split (70/20/10)
- Per-image metadata JSON (seed, LoRA strength, etc.)

### 4. Quality Assurance (Phase 8)
- SSIM background consistency check (target >0.90)
- Annotation validation (bbox bounds, polygon simplification)
- Visual spot-check gallery (HTML with 1-2% random images)
- Distribution analysis per defect type

### 5. Downstream Validation (Phase 9)
- YOLOv8 training on multiple synthetic ratios (20%, 50%, 100%)
- Evaluation on held-out real test set
- Per-class mAP breakdown
- Optimal ratio recommendation

## Configuration

Edit `/mnt/e/The Data Mint/pipeline/config/batch-config.yaml` to customize:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `total_images` | 20000 | Total synthetic images to generate |
| `resolution` | 512 | Output resolution (512×512 px) |
| `steps` | 20 | Diffusion sampling steps per image |
| `cfg` | 7.0 | Classifier-free guidance scale |
| `max_temp_celsius` | 85 | GPU thermal throttle threshold |
| `mask_prefetch_count` | 50 | Ahead-of-time mask generation |

## Performance Metrics

| Phase | Task | Throughput | 20K Images | 100K Images |
|-------|------|-----------|-----------|------------|
| 1-6 | Image Generation | 1,097 img/hr | ~18h | ~91h |
| 7 | Post-processing | ~450 img/s | ~45s | ~4min |
| 8 | QA | ~10-15min | ~10-15min | ~30min |
| 9 | Validation | ~50 epochs/hr | ~12h | ~12h |
| **Total** | End-to-End | - | **~30h** | **~4.5 days** |

## Quality Gates

All phases enforce quality checkpoints:

- **Phase 7**: COCO JSON loads, split ratios within 1%
- **Phase 8**: SSIM ≥0.90, zero annotation errors, <2% distribution deviation
- **Phase 9**: Synthetic improves mAP, optimal ratio identified

## Documentation

- **[Project Overview & PDR](./docs/project-overview-pdr.md)** — Requirements, scope, success criteria
- **[Codebase Summary](./docs/codebase-summary.md)** — Component descriptions, APIs
- **[Code Standards](./docs/code-standards.md)** — File naming, structure, conventions
- **[System Architecture](./docs/system-architecture.md)** — Data flow, components, integration
- **[Project Roadmap](./docs/project-roadmap.md)** — Phase status, next steps
- **[Pipeline Overview](./pipeline/PIPELINE-OVERVIEW.md)** — Detailed guide with troubleshooting

## Troubleshooting

**ComfyUI connection fails**: Check API at `http://172.21.192.1:8188/api/status`

**GPU thermal throttle**: Reduce `cfg` from 7.0 to 5.0, or increase `max_temp_celsius` to 88°C

**Low SSIM scores**: Adjust LoRA strength in ComfyUI workflow (default 0.7)

**Annotation errors**: Run `annotation-validator.py` with `--verbose` for details

**Low mAP in validation**: Check real test set quality, verify mask generation

## Requirements & Dependencies

**Python**: 3.8+

**Key Packages**:
- opencv-python, numpy, pillow, pyyaml, tqdm
- scikit-image (SSIM calculations)
- ultralytics (YOLOv8)
- torch, torchvision (GPU inference)

**System**:
- RTX 3090+ (24GB+ VRAM)
- 50GB+ free disk (20K images ≈ 25GB)
- ComfyUI running with SD 1.5 + ControlNet

## Support & References

- **GitHub Issues**: [Link]
- **ComfyUI Docs**: https://github.com/comfyanonymous/ComfyUI
- **LoRA Training**: kohya-ss documentation
- **ControlNet**: https://github.com/lllyasviel/ControlNet
- **YOLOv8**: https://docs.ultralytics.com

---

**Status**: Production Ready
**Last Updated**: 2026-02-14
**Version**: 1.1
**Maintainer**: [Project Team]
