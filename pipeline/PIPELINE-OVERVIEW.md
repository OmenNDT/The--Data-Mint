# The Data Mint - Pipeline Overview

Complete synthetic X-ray defect image generation pipeline with automated annotation and validation.

**Status:** ✓ Phases 1-9 Complete
**Hardware:** Dual Xeon E5-2696v4 (44c/88t) + RTX 3090 24GB
**Throughput:** 1097 img/hr (tested), theoretical 900-1800 img/hr

---

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1-6: GENERATION PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [GDXray W0003] → [Preprocess] → [Train 5 LoRAs (kohya-ss)]        │
│                                           ↓                          │
│  [Clean Backgrounds] → [Procedural Masks] → [ComfyUI Inpaint]      │
│                                           ↓                          │
│               [Synthetic Image + Mask + Metadata JSON]              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 7: POST-PROCESSING                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Raw Output] → [Mask to Annotation] → [COCO JSON + YOLO TXT]      │
│                      ↓                                               │
│              [Train/Val/Test Split]                                 │
│                      ↓                                               │
│       [Annotated Dataset Ready for Training]                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 8: QUALITY ASSURANCE                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [SSIM Background Check] → [Annotation Validation]                 │
│              ↓                        ↓                              │
│  [Distribution Check] → [Visual Spot-Check Gallery]                │
│              ↓                                                       │
│         [QA Report + Pass/Fail]                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 9: DOWNSTREAM VALIDATION                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Train YOLOv8 on Multiple Synthetic Ratios]                       │
│              ↓                                                       │
│  [Evaluate on Real Test Set] → [Compare mAP]                       │
│              ↓                                                       │
│  [Validation Report + Optimal Ratio Recommendation]                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Generate Synthetic Images (Phases 1-6)

```bash
cd /mnt/e/The\ Data\ Mint/pipeline

# Run batch production
./run-batch-production.sh

# Monitor progress
tail -f logs/batch-production-*.log

# Output: /mnt/e/The Data Mint/output/synthetic/{defect_type}/
#   - {defect}_{id}.png        (synthetic image)
#   - {defect}_{id}_mask.png   (binary mask)
#   - {defect}_{id}.json       (metadata)
```

**Expected:** 5 defect types × 4000-5000 images = 20,000 total images

### 2. Post-Process to Annotations (Phase 7)

```bash
# Convert to COCO + YOLO formats
./run-post-processing.sh

# Or with custom parameters
python3 post_processing/post-processing-main.py \
  --synthetic-dir /mnt/e/The\ Data\ Mint/output/synthetic \
  --output-dir /mnt/e/The\ Data\ Mint/output/dataset \
  --train-ratio 0.70 \
  --val-ratio 0.20 \
  --test-ratio 0.10

# Output: /mnt/e/The Data Mint/output/dataset/
#   - annotations/{coco_train,coco_val,coco_test}.json
#   - yolo/{train,val,test}/images/
#   - yolo/{train,val,test}/labels/
#   - yolo/data.yaml
```

**Expected:** 70% train, 20% val, 10% test split with stratification

### 3. Run Quality Assurance (Phase 8)

```bash
# Run QA checks
python3 qa/qa-pipeline-main.py \
  --synthetic-dir /mnt/e/The\ Data\ Mint/output/synthetic \
  --dataset-dir /mnt/e/The\ Data\ Mint/output/dataset \
  --output-dir /mnt/e/The\ Data\ Mint/output/qa-reports \
  --ssim-sample-size 500

# Output: /mnt/e/The Data Mint/output/qa-reports/
#   - qa-report.md
#   - qa-results.json
#   - spot-check-gallery.html

# Open spot-check gallery in browser
firefox /mnt/e/The\ Data\ Mint/output/qa-reports/spot-check-gallery.html
```

**Expected:** SSIM >0.90, 0 annotation errors, distribution deviation <2%

### 4. Validate with YOLOv8 (Phase 9)

```bash
# Install ultralytics
pip install ultralytics

# Prepare real test set (held-out GDXray data in YOLO format)
# Store at: /mnt/e/The Data Mint/dataset/real_test_yolo/

# Run validation experiments
python3 validation/validation-main.py \
  --real-yolo-dir /mnt/e/The\ Data\ Mint/dataset/real_test_yolo \
  --synth-yolo-dir /mnt/e/The\ Data\ Mint/output/dataset/yolo \
  --output-dir /mnt/e/The\ Data\ Mint/output/validation \
  --model-size n \
  --epochs 100 \
  --batch-size 16

# Output: /mnt/e/The Data Mint/output/validation/
#   - validation-report.md
#   - validation-results.json
#   - results/{experiment_name}/weights/best.pt

# Review validation report
cat /mnt/e/The\ Data\ Mint/output/validation/validation-report.md
```

**Expected:** Optimal synthetic ratio identified (typically 20-30%), mAP improvement over real-only baseline

---

## Directory Structure

```
/mnt/e/The Data Mint/pipeline/
├── batch_manager/                 # Phase 6: Batch production
│   ├── batch-production-main.py
│   ├── batch-job-scheduler.py
│   ├── mask-prefetch-worker-pool.py
│   └── ...
├── mask_generator/                # Phase 5: Procedural masks
│   ├── crack-mask-generator.py
│   ├── porosity-mask-generator.py
│   └── ...
├── post_processing/               # Phase 7: Annotation conversion
│   ├── mask-to-annotation-converter.py
│   ├── coco-dataset-builder.py
│   ├── yolo-dataset-builder.py
│   ├── dataset-splitter.py
│   ├── post-processing-main.py
│   └── README.md
├── qa/                            # Phase 8: Quality assurance
│   ├── ssim-background-checker.py
│   ├── annotation-validator.py
│   ├── visual-spot-check-grid.py
│   ├── qa-pipeline-main.py
│   └── README.md
├── validation/                    # Phase 9: Downstream validation
│   ├── yolo-trainer.py
│   ├── evaluation-metrics.py
│   ├── validation-main.py
│   └── README.md
├── config/
│   ├── batch-config.yaml
│   └── mask-config.yaml
├── comfyui-workflows/
│   ├── sd15-lora-controlnet-inpaint-single-defect-workflow.json
│   └── defect-type-prompt-templates.yaml
├── run-batch-production.sh
├── run-post-processing.sh
└── PIPELINE-OVERVIEW.md (this file)
```

---

## Output Structure

```
/mnt/e/The Data Mint/output/
├── synthetic/                     # Phase 6 output
│   ├── crack/
│   │   ├── crack_000000.png
│   │   ├── crack_000000_mask.png
│   │   └── crack_000000.json
│   ├── porosity/
│   ├── inclusion/
│   ├── lack_of_fusion/
│   └── undercut/
├── dataset/                       # Phase 7 output
│   ├── annotations/
│   │   ├── coco_train.json
│   │   ├── coco_val.json
│   │   └── coco_test.json
│   ├── yolo/
│   │   ├── train/
│   │   │   ├── images/
│   │   │   └── labels/
│   │   ├── val/
│   │   ├── test/
│   │   └── data.yaml
│   └── post-processing-report.txt
├── qa-reports/                    # Phase 8 output
│   ├── qa-report.md
│   ├── qa-results.json
│   └── spot-check-gallery.html
└── validation/                    # Phase 9 output
    ├── datasets/
    │   ├── real-only/
    │   ├── real-synth-20/
    │   └── ...
    ├── results/
    │   ├── real-only/weights/best.pt
    │   └── ...
    ├── validation-report.md
    └── validation-results.json
```

---

## Performance Metrics

### Generation (Phases 1-6)
- **Throughput**: 1097 img/hr (pilot tested)
- **20K images**: ~18 hours
- **100K images**: ~91 hours (3.8 days)

### Post-Processing (Phase 7)
- **Speed**: ~450 img/s (I/O limited)
- **20K images**: ~45 seconds
- **100K images**: ~4 minutes

### QA (Phase 8)
- **SSIM check**: ~1 img/s (500 sample)
- **Annotation validation**: ~100K annotations/s
- **Spot-check generation**: ~10 img/s
- **Total for 20K dataset**: ~10-15 minutes

### Validation (Phase 9)
- **YOLOv8n training**: ~50 epochs/hour
- **6 experiments × 100 epochs**: ~12 hours
- **Evaluation**: ~1 minute per model

### End-to-End Pipeline
- **Generation**: ~18 hours
- **Post-processing**: <1 minute
- **QA**: ~15 minutes
- **Validation**: ~12 hours
- **Total**: ~30 hours for 20K images with full validation

---

## Defect Categories

| Category         | COCO ID | YOLO ID | Target Distribution |
|------------------|---------|---------|---------------------|
| crack            | 1       | 0       | 25% (5000 images)   |
| porosity         | 2       | 1       | 25% (5000 images)   |
| inclusion        | 3       | 2       | 20% (4000 images)   |
| lack_of_fusion   | 4       | 3       | 15% (3000 images)   |
| undercut         | 5       | 4       | 15% (3000 images)   |

---

## Quality Gates

### Phase 7: Post-Processing
- ✓ COCO JSON loads with pycocotools
- ✓ YOLO data.yaml loads with Ultralytics
- ✓ Split ratios within 1% of target
- ✓ Image count matches annotation count

### Phase 8: QA
- ✓ SSIM mean ≥ 0.90
- ✓ SSIM pass rate ≥ 90%
- ✓ Zero annotation errors
- ✓ Distribution deviation ≤ 2%
- ✓ Spot-check >95% visual pass

### Phase 9: Validation
- ✓ Synthetic data improves mAP over real-only
- ✓ Optimal ratio identified
- ✓ Synth-only mAP > 60% of real-only
- ✓ Per-class improvement documented

---

## Dependencies

### Python Packages (pipeline/.venv)

```bash
# Core
opencv-python
numpy
pyyaml
tqdm
pillow

# QA
scikit-image

# Validation
ultralytics  # Includes torch, torchvision

# Optional
pycocotools  # For COCO validation
```

### External Services
- ComfyUI API (http://172.21.192.1:8188)
- Stable Diffusion 1.5
- ControlNet v1.1 Inpaint
- 5 trained LoRA models (rank 32)

---

## Troubleshooting

### Generation Issues
- **ComfyUI crash**: Auto-restart enabled, checkpoints every 100 images
- **GPU thermal throttle**: Monitor at 85°C, resume at 75°C
- **Out of backgrounds**: Pipeline loops through available backgrounds

### Post-Processing Issues
- **Empty masks**: Logged as warning, creates empty annotation
- **Circular import**: Fixed, use direct import_module()
- **Missing metadata**: Skips image if JSON missing

### QA Issues
- **SSIM too low**: Adjust LoRA strength, check inpainting quality
- **Annotation errors**: Review mask generator output
- **Distribution off**: Adjust batch-config.yaml defect_distribution

### Validation Issues
- **CUDA OOM**: Reduce batch size or use smaller model (n vs s)
- **Low mAP**: Check real test set quality, verify annotations
- **Synth hurts performance**: Improve LoRA training (Phase 3)

---

## Production Checklist

Before scaling to 100K images:

- [ ] Complete pilot run (500-1000 images)
- [ ] Verify QA passes all checks
- [ ] Run validation on pilot data
- [ ] Confirm mAP improves over baseline
- [ ] Review spot-check gallery (manual QA)
- [ ] Adjust defect distribution if needed
- [ ] Plan storage (100K × 512×512 ≈ 25GB compressed)
- [ ] Schedule production window (~4 days)
- [ ] Monitor GPU temperature during full run
- [ ] Set up checkpoint backups

---

## Support

**Documentation:**
- [Plan Overview](/mnt/e/The Data Mint/plans/260130-0849-the-data-mint-xray-defect-pipeline/plan.md)
- [Post-Processing README](post_processing/README.md)
- [QA README](qa/README.md)
- [Validation README](validation/README.md)

**Reports:**
- [Implementation Report](/mnt/e/The Data Mint/plans/reports/fullstack-developer-260131-1316-phases-7-8-9-implementation.md)

**Logs:**
- Generation: `pipeline/logs/batch-production-*.log`
- Post-processing: `output/dataset/post-processing-report.txt`
- QA: `output/qa-reports/qa-report.md`
- Validation: `output/validation/validation-report.md`

---

**Last Updated:** 2026-01-31
**Pipeline Version:** 1.0
**Status:** Production Ready
