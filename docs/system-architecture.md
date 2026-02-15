# System Architecture - The Data Mint Pipeline

**Document Version**: 1.1
**Last Updated**: 2026-02-14
**Scope**: Full 9-phase synthetic data generation pipeline + Gradio UI

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        THE DATA MINT PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PHASE 1: Environment Setup                                             │
│  ├─ ComfyUI installation & API setup                                    │
│  ├─ Model downloads (SD 1.5, ControlNet v1.1)                          │
│  └─ Python venv & dependency installation                              │
│                                                                          │
│  PHASE 2: Dataset Preprocessing                                         │
│  ├─ Load GDXray W0003 raw X-ray images                                  │
│  ├─ Normalize to 512×512 resolution                                     │
│  └─ Extract clean background regions                                    │
│                                                                          │
│  PHASE 3: LoRA Fine-Tuning (kohya-ss)                                   │
│  ├─ Train 5 independent LoRA models (rank 32, 10 epochs)               │
│  ├─ Per-defect type: crack, porosity, inclusion, LOF, undercut         │
│  └─ Output: 5 safetensors files (~185 MB total)                        │
│                                                                          │
│  PHASE 4: ComfyUI Workflow Design                                       │
│  ├─ Create SD1.5 + LoRA + ControlNet inpaint workflow                  │
│  ├─ Define defect-type prompts (YAML)                                   │
│  └─ Sampler params: Euler, 20 steps, CFG 7.0                           │
│                                                                          │
│  PHASE 5: Procedural Mask Generation (CPU Parallel)                     │
│  ├─ 5 defect generators (crack, porosity, inclusion, LOF, undercut)    │
│  ├─ Morphological operations for realistic shapes                       │
│  ├─ ROI constraints (keep within weld area)                             │
│  └─ Feathering for smooth inpainting                                    │
│                                                                          │
│  PHASE 6: Batch Production (GPU Intensive)                              │
│  ├─ Parallel mask prefetching (8 CPU workers)                           │
│  ├─ ComfyUI job queue management (retry up to 3x)                      │
│  ├─ GPU thermal monitoring (pause at 85°C)                              │
│  ├─ Checkpoint every 100 images (fault tolerance)                      │
│  └─ Output: 20K-100K PNG + mask + metadata JSON                        │
│                                                                          │
│  PHASE 7: Post-Processing (Annotation Export)                          │
│  ├─ Mask → COCO JSON (bboxes + segmentation)                           │
│  ├─ Mask → YOLO TXT (normalized class + bbox)                          │
│  ├─ Train/Val/Test split (70/20/10 stratified)                         │
│  └─ Output: COCO JSON + YOLO directories                               │
│                                                                          │
│  PHASE 8: Quality Assurance                                             │
│  ├─ SSIM background consistency check (500 sample)                     │
│  ├─ Annotation validation (format + bounds)                            │
│  ├─ Distribution analysis (defect type ratios)                          │
│  ├─ Visual spot-check gallery (1-2% sample HTML)                       │
│  └─ Output: QA report (pass/fail + metrics)                            │
│                                                                          │
│  PHASE 9: Downstream Validation (YOLOv8)                                │
│  ├─ Train YOLOv8 on multiple synthetic ratios (20%, 50%, 100%)         │
│  ├─ Evaluate on held-out real test set                                 │
│  ├─ Compare mAP across ratios                                          │
│  └─ Output: Validation report + optimal ratio recommendation           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### Generation Pipeline (Phases 1-6)

```
                      Input Data Sources
                              │
                    ┌─────────┴─────────┐
                    │                   │
            ┌───────▼────────┐  ┌──────▼──────────┐
            │   GDXray W0003 │  │  Preprocessed   │
            │   (Raw Images) │  │  Backgrounds    │
            └────────────────┘  └─────────┬───────┘
                                          │
                     ┌────────────────────┘
                     │
            ┌────────▼────────────┐
            │  5 LoRA Models      │
            │  (rank 32, 37MB ea) │
            └────────┬────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    │     ┌──────────▼──────────┐     │
    │     │ Mask Generator Pool │     │ (CPU Parallel)
    │     │ (8 workers, 50 buf) │     │
    │     └──────────┬──────────┘     │
    │                │                │
    │     ┌──────────▼──────────┐     │
    │     │ Procedural Masks    │     │
    │     │ (5 defect types)    │     │
    │     └──────────┬──────────┘     │
    │                │                │
    ├────────────────┼────────────────┤
    │                │                │
    │     ┌──────────▼────────────────────┐
    │     │ Batch Production Main          │
    │     │ - Job Scheduler                │
    │     │ - ComfyUI REST API Client      │
    │     │ - GPU Thermal Monitor          │
    │     │ - Checkpoint Manager           │
    │     └──────────┬─────────────────────┘
    │                │
    │     ┌──────────▼──────────┐
    │     │  ComfyUI API        │
    │     │  (http://....:8188) │
    │     │  ↓ Upload bg image  │
    │     │  ↓ Queue prompt     │
    │     │  ↓ Poll progress    │
    │     └──────────┬──────────┘
    │                │
    │     ┌──────────▼──────────────────┐
    │     │  SD 1.5 + LoRA + ControlNet  │
    │     │  (GPU: RTX 3090)             │
    │     │  Sampler: Euler, 20 steps    │
    │     └──────────┬──────────────────┘
    │                │
    └────────────────┼────────────────────┘
                     │
            ┌────────▼────────┐
            │ Synthetic Output │
            │ - PNG image      │
            │ - Binary mask    │
            │ - Metadata JSON  │
            │ (organized by    │
            │  defect type)    │
            └──────────────────┘
```

### Annotation Pipeline (Phase 7)

```
            Synthetic Output
          (PNG + Mask + JSON)
                  │
        ┌─────────┴──────────┐
        │                    │
    ┌───▼──────────┐  ┌──────▼───────┐
    │ Image File   │  │ Binary Mask   │
    └────┬─────────┘  └──────┬────────┘
         │                   │
         └─────────┬─────────┘
                   │
        ┌──────────▼───────────┐
        │ Mask→Annotation      │
        │ Converter            │
        │ - Connected comps     │
        │ - Bbox extraction     │
        │ - Polygon simplify    │
        └──────────┬───────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
    ┌───▼───────┐      ┌──────▼─────────┐
    │COCO JSON  │      │  YOLO TXT      │
    │- bboxes   │      │  - normalized  │
    │- polygons │      │    coords      │
    └───┬───────┘      └──────┬─────────┘
        │                     │
        │      ┌──────────────┴────┐
        │      │                   │
        │  ┌───▼───────┐   ┌───────▼──┐
        │  │Split Data │   │Split Data │
        │  │  70/20/10 │   │ 70/20/10  │
        │  └─────┬─────┘   └────┬──────┘
        │        │              │
        │    ┌───▼─────────┐  ┌─▼────────────┐
        │    │COCO Train   │  │YOLO Train    │
        │    │COCO Val     │  │YOLO Val      │
        │    │COCO Test    │  │YOLO Test     │
        │    └─────────────┘  │data.yaml     │
        │                     └──────────────┘
        │
        └─ Output: /output/dataset/
           ├── annotations/
           │   ├── coco_train.json
           │   ├── coco_val.json
           │   └── coco_test.json
           └── yolo/
               ├── train/images & labels
               ├── val/images & labels
               ├── test/images & labels
               └── data.yaml
```

### QA Pipeline (Phase 8)

```
        Synthetic Dataset + Annotations
                    │
        ┌───────────┼───────────┐
        │           │           │
    ┌───▼────┐  ┌───▼──────┐  ┌─▼──────────┐
    │ SSIM   │  │Annotation│  │Distribution│
    │Checker │  │Validator │  │Analyzer    │
    │        │  │          │  │            │
    │- BG    │  │- COCO OK │  │- Per-type  │
    │  consist│  │- YOLO OK │  │  ratios    │
    │- >0.90 │  │- Bounds  │  │- Deviation │
    │  mean  │  │- Polygons│  │  < 2%      │
    └───┬────┘  └────┬─────┘  └─┬──────────┘
        │            │          │
        └────────────┼──────────┘
                     │
        ┌────────────▼─────────────┐
        │ Visual Spot Check (HTML) │
        │ - 1-2% random sample     │
        │ - Grid layout            │
        │ - SSIM overlays          │
        └────────────┬─────────────┘
                     │
        ┌────────────▼──────────────────┐
        │ QA Report (Markdown)          │
        │ - Summary stats               │
        │ - Pass/Fail per check         │
        │ - Recommendations             │
        └───────────────────────────────┘
```

### Validation Pipeline (Phase 9)

```
        YOLO Dataset + Real Test Set
                    │
        ┌───────────┴────────────┐
        │                        │
    ┌───▼──────────────┐   ┌─────▼─────────┐
    │ Synthetic Data   │   │Real Test Set   │
    │ (organized in    │   │(held-out from  │
    │  train/val/test) │   │ GDXray)        │
    └───┬──────────────┘   └────────────────┘
        │
        ├─ Experiment 1: Real-only (0% synthetic)
        ├─ Experiment 2: 20% synthetic + 80% real
        ├─ Experiment 3: 50% synthetic + 50% real
        └─ Experiment 4: 100% synthetic only
                 │
        ┌────────▼──────────┐
        │  YOLOv8n Training  │
        │  - 100 epochs      │
        │  - Batch size 16   │
        │  - Data augment    │
        └────────┬───────────┘
                 │
        ┌────────▼─────────────────┐
        │ Evaluate on Real Test Set │
        │ - mAP@0.5                 │
        │ - mAP@0.5:0.95            │
        │ - Per-class metrics       │
        │ - Inference time          │
        └────────┬─────────────────┘
                 │
        ┌────────▼──────────────────┐
        │ Compare & Analyze         │
        │ - Plot mAP curves         │
        │ - Find optimal ratio      │
        │ - Per-class breakdown     │
        └────────┬──────────────────┘
                 │
        ┌────────▼────────────────────┐
        │ Validation Report           │
        │ - Optimal ratio identified  │
        │ - mAP improvement metrics   │
        │ - Recommendation            │
        └─────────────────────────────┘
```

---

## Component Architecture

### Core Module Hierarchy

```
pipeline/
├── batch_manager/                    # Orchestration
│   ├── batch-production-main.py      # Main orchestrator (321 LOC)
│   │   └─ Coordinates all other modules
│   ├── batch-job-scheduler.py        # Job queue (263 LOC)
│   │   └─ Fair distribution across defect types
│   ├── comfyui-rest-api-client.py    # REST wrapper (183 LOC)
│   │   └─ Queue jobs, poll status, download results
│   ├── mask-prefetch-worker-pool.py  # Thread pool (173 LOC)
│   │   └─ Pre-generate masks while GPU busy
│   ├── gpu-thermal-monitor.py        # Thermal (143 LOC)
│   │   └─ Pause/resume based on temp
│   └── checkpoint-state-manager.py   # State (109 LOC)
│       └─ Save/resume progress
│
├── mask_generator/                   # Procedural masks (CPU)
│   ├── base-defect-mask-generator.py # Base class (58 LOC)
│   ├── crack-mask-generator.py       # Cracks (127 LOC)
│   ├── porosity-mask-generator.py    # Voids (94 LOC)
│   ├── slag-inclusion-mask-generator.py  # Inclusions (121 LOC)
│   ├── lack-of-fusion-mask-generator.py  # Seams (91 LOC)
│   ├── undercut-mask-generator.py    # Grooves (96 LOC)
│   ├── feathering-utility.py         # Edge blending (29 LOC)
│   └── weld-roi-constraint.py        # Region mask (40 LOC)
│
├── post_processing/                  # Annotation export
│   ├── post-processing-main.py       # Orchestrator (203 LOC)
│   ├── mask-to-annotation-converter.py  # Bbox+polygon (154 LOC)
│   ├── coco-dataset-builder.py       # COCO JSON (160 LOC)
│   ├── yolo-dataset-builder.py       # YOLO TXT (182 LOC)
│   └── dataset-splitter.py           # Train/val/test split (185 LOC)
│
├── qa/                               # Quality assurance
│   ├── qa-pipeline-main.py           # Orchestrator (347 LOC)
│   ├── ssim-background-checker.py    # SSIM validation (166 LOC)
│   ├── annotation-validator.py       # Format checking (273 LOC)
│   └── visual-spot-check-grid.py     # HTML gallery (244 LOC)
│
├── validation/                       # YOLOv8 testing
│   ├── validation-main.py            # Experiment runner (388 LOC)
│   ├── yolo-trainer.py               # Training wrapper (190 LOC)
│   └── evaluation-metrics.py         # Metrics analysis (208 LOC)
│
├── launcher/                             # Gradio UI
│   ├── gradio_launcher_app.py        # Main entry point (342 LOC)
│   ├── pipeline_orchestrator.py      # Phase manager (268 LOC)
│   ├── phase_runner.py               # Subprocess executor (194 LOC)
│   ├── progress_tracker.py           # Log parser (187 LOC)
│   ├── ui_progress_panel.py          # Progress UI (156 LOC)
│   ├── ui_results_panel.py           # Results UI (142 LOC)
│   ├── ui_dataset_panel.py           # Dataset UI (128 LOC)
│   ├── error_handler.py              # Error mapper (109 LOC)
│   ├── launcher_utils.py             # GPU/API checks (94 LOC)
│   ├── config_preset_manager.py      # Preset mgmt (87 LOC)
│   └── demo_pipeline_runner.py       # Demo mode (73 LOC)
│
├── comfyui-api-batch-inpaint-client.py  # Single-image client (376 LOC)
├── verify-comfyui-setup.py               # Pre-flight checks (197 LOC)
└── config/                               # Configuration
    ├── batch-config.yaml             # Main config (68 lines)
    └── mask-config.yaml              # Mask params (TBD)
```

### Dependency Graph

```
batch-production-main.py (entry point)
    ├─ BatchJobScheduler
    │   └─ load_config()
    ├─ ComfyUIClient
    │   └─ requests library
    ├─ MaskPrefetcher
    │   ├─ ThreadPoolExecutor
    │   └─ get_generator(defect_type)
    │       ├─ CrackMaskGenerator
    │       ├─ PorosityMaskGenerator
    │       ├─ SlagInclusionMaskGenerator
    │       ├─ LackOfFusionMaskGenerator
    │       └─ UndercutMaskGenerator
    ├─ GPUThermalMonitor
    │   └─ nvidia-smi (subprocess)
    └─ CheckpointManager
        └─ JSON serialization

post-processing-main.py (entry point)
    ├─ MaskToAnnotationConverter
    │   └─ cv2, numpy
    ├─ COCODatasetBuilder
    │   └─ pycocotools (optional)
    ├─ YOLODatasetBuilder
    │   └─ yaml
    └─ DatasetSplitter
        └─ random, numpy

qa-pipeline-main.py (entry point)
    ├─ SSIMBackgroundChecker
    │   └─ scikit-image
    ├─ AnnotationValidator
    │   └─ pycocotools, yaml
    └─ VisualSpotCheckGallery
        └─ PIL, numpy

validation-main.py (entry point)
    ├─ YOLOv8Trainer
    │   └─ ultralytics (YOLOv8)
    └─ EvaluationMetrics
        └─ numpy, pandas
```

---

## Launcher Architecture (UI Layer)

**Location**: `pipeline/launcher/` (11 modules, ~1,200 LOC)

### Flow

```
Gradio UI (gradio_launcher_app.py)
    ↓ User selects preset & clicks "Start"
    ↓
PipelineOrchestrator (validates dependencies, state machine)
    ↓
PhaseRunner (spawns subprocess, captures logs)
    ↓
Phase Script (batch-production-main.py, etc.)
    ↓
ProgressTracker (polls logs every 2s, extracts metrics)
    ↓
UI Components (progress bar, temp gauge, throughput graph)
```

**Key Features**:
- Real-time progress tracking via log polling
- GPU temperature monitoring with visual gauge
- Error categorization and mitigation suggestions
- Preset configs: pilot (500 img), standard (20K), full (100K)
- Demo mode for UX testing (no GPU required)
- Download COCO/YOLO datasets post-generation

---

## Data Structures

### Job Definition (Scheduler)

```python
Job = {
    "job_id": int,                          # Unique incrementing ID
    "defect_type": str,                     # crack|porosity|inclusion|lof|undercut
    "seed": int,                            # Random seed for reproducibility
    "background_image": Path,               # Path to background PNG
    "lora_model": str,                      # LoRA filename (e.g., xray_crack_lora_r32.safetensors)
}
```

### Checkpoint State

```python
Checkpoint = {
    "job_id": int,                          # Last completed job
    "timestamp": str,                       # ISO format timestamp
    "defect_counts": {                      # Cumulative counts
        "crack": int,
        "porosity": int,
        "inclusion": int,
        "lack_of_fusion": int,
        "undercut": int,
    }
}
```

### COCO Annotation

```python
COCOAnnotation = {
    "id": int,
    "image_id": int,
    "category_id": int,                     # 1=crack, 2=porosity, etc.
    "bbox": [x, y, width, height],          # Top-left + dimensions
    "area": float,                          # width * height
    "segmentation": [                       # Polygon vertices
        [x1, y1, x2, y2, x3, y3, ...]
    ],
    "iscrowd": 0
}
```

### YOLO Label

```
<class_id> <x_center_norm> <y_center_norm> <width_norm> <height_norm>
# Example: 0 0.5 0.5 0.2 0.3  (class 0, center at 50%, 20% width)
```

---

## Error Handling & Recovery

### Fault Tolerance Strategy

```
┌─ Image Generation Failure
│  ├─ Retry up to 3 times (with 5s delay)
│  ├─ Log warning if all retries fail
│  └─ Continue to next job (don't abort)
│
├─ ComfyUI API Unreachable
│  ├─ Check connection at startup (verify-comfyui-setup.py)
│  ├─ Retry on transient failures (ConnectionError)
│  ├─ Alert if persistent (log CRITICAL)
│  └─ Support manual restart if needed
│
├─ GPU Thermal Throttle
│  ├─ Monitor every 30 seconds
│  ├─ Pause generation if temp > 85°C
│  ├─ Resume when temp < 75°C (hysteresis)
│  └─ Log pause/resume events
│
└─ Batch Production Crash
   ├─ Save checkpoint every 100 images
   ├─ On restart, auto-resume from checkpoint
   ├─ Verify checkpoint file integrity (JSON)
   └─ Restart ComfyUI if needed
```

### Checkpoint & Recovery

```
Normal Execution:
┌─ Job 0
├─ Job 1
├─ ...
└─ [CHECKPOINT] Job 99 (save to checkpoint.json)
   ├─ Job 100
   ├─ ...
   └─ [CHECKPOINT] Job 199
      ...

On Crash at Job 145:
├─ Manual restart: python batch-production-main.py ...
├─ Auto-load checkpoint (Job 99 completed)
├─ Resume from Job 100
├─ Continue normally
```

---

## Performance Characteristics

### Batch Production (Phase 6)

| Component | Throughput | Bottleneck |
|-----------|-----------|-----------|
| Mask Generation | ~100 masks/sec | CPU (not limiting) |
| GPU Generation | ~1,097 img/hr | GPU (RTX 3090) |
| Prefetch Buffer | Pre-fills 50 masks | Ahead of GPU |
| Checkpoint Write | <100ms per 100 images | Negligible |
| **End-to-End** | **~1,097 img/hr** | **GPU** |

**For 20K images**:
- Total time: 20,000 ÷ 1,097 ≈ 18.2 hours
- Checkpoints: 200 (every 100 images)
- Storage: ~25 GB (PNG 8-bit, lossy compression)

### Post-Processing (Phase 7)

| Component | Throughput | Time for 20K |
|-----------|-----------|-----------|
| Mask→Annotation | ~450 img/s | ~45 seconds |
| COCO JSON Build | Negligible | <5 seconds |
| YOLO TXT Write | ~500 labels/s | ~40 seconds |
| Split Metadata | ~1000 ops/s | <5 seconds |
| **Total** | - | **~2 minutes** |

### Quality Assurance (Phase 8)

| Component | Throughput | Sample Size | Time |
|-----------|-----------|-----------|------|
| SSIM Check | ~1 img/s | 500 images | ~8 min |
| Annotation Validation | ~100K annot/s | All (~20K annot) | <1 sec |
| Distribution Analysis | ~500K ops/s | Per-type counts | <1 sec |
| Spot-Check Gallery | ~10 img/s | 200-400 images | ~30 sec |
| **Total** | - | - | **~9-10 min** |

### Validation (Phase 9)

| Component | Count | Time per Experiment | Notes |
|-----------|-------|-----------|-------|
| YOLOv8 Training | 100 epochs | ~1.2 hours | 50 epochs/hr on RTX 3090 |
| Evaluation | Per-model | ~30 sec | Quick inference on test set |
| Report Generation | Summary stats | ~10 sec | Aggregation & plotting |
| **Total for 4 experiments** | - | **~4.8 hours** | Sequential |

---

## Scalability & Limitations

### Current Hardware

```
Hardware: Dual Xeon E5-2696v4 + RTX 3090 24GB + 64GB ECC
Constraints:
  - Single GPU (no DDP)
  - ~18GB vRAM available for inference
  - 8 CPU workers for mask generation (saturates CPU)
```

### Scalability Options (Future)

1. **Multi-GPU Batch Processing**
   - Distribute jobs across multiple GPUs
   - Share checkpoint state via network
   - Requires DDP-aware scheduler

2. **Larger Models**
   - SDXL instead of SD 1.5 (higher quality)
   - Requires 48GB+ vRAM
   - Would need A100/H100 GPU

3. **Advanced LoRA Techniques**
   - Multi-LoRA merging (blend multiple defect types)
   - Lycoris (extended LoRA) for better quality
   - Requires retraining (Phase 3)

4. **Faster Inference**
   - Reduced diffusion steps (15 instead of 20)
   - Distilled VAE encoder
   - Would require quality validation

### Storage Requirements

```
Phase 6 Output (20K images):
  - PNG images (512×512, 8-bit): ~3 bytes/pixel × 262K pixels = 786 KB/image
  - 20K images × 786 KB = ~15.7 GB
  - Binary masks: ~250 KB/image = ~5 GB
  - Metadata JSON: ~1 KB/image = ~20 MB
  Total: ~20-25 GB (with compression)

Phase 7 Output (Annotations):
  - COCO JSON: ~50-100 MB
  - YOLO TXT files: ~5 MB
  - Copy of images: ~15.7 GB
  Total: ~16 GB

Cumulative:
  - Synthetic raw: ~20-25 GB
  - Annotated dataset: ~16 GB
  - QA reports: ~50 MB
  - Validation results: ~100 MB
  Total: ~36-41 GB for 20K images
```

---

## Integration Points

**ComfyUI REST API**: `http://172.21.192.1:8188/api/` (HTTP JSON RPC, local network)

**File I/O**:
- Input: Background images from training_data/reg/
- Output: `/output/synthetic/`, `/output/dataset/`, `/output/qa-reports/`, `/output/validation/`

**Logging**: Phase-specific logs in `/pipeline/logs/` and output reports

---

**Last Updated**: 2026-02-14
**Version**: 1.1
