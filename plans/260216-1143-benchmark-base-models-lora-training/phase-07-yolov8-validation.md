# Phase 7: YOLOv8 Downstream Validation

## Context Links
- [Plan Overview](plan.md)
- [Phase 6: Evaluation Pipeline](phase-06-evaluation-pipeline.md)
- Existing validation: `pipeline/validation/validation-main.py`
- YOLO trainer: `pipeline/validation/yolo-trainer.py`
- Evaluation metrics: `pipeline/validation/evaluation-metrics.py`

## Overview
- **Priority**: P1 (final decision gate)
- **Status**: complete
- **Effort**: 3 days (mostly GPU training time; ~2h scripting)
- **Description**: For top 2 models from Phase 6 + baseline, generate 2000 images each, train YOLOv8 detectors on synthetic data, evaluate mAP on held-out real test set. This is the ultimate success metric.

## Key Insights
- Existing `validation-main.py` already handles: dataset preparation, YOLOv8 training, mAP evaluation, comparison reports
- `run_validation()` accepts `real_yolo_dir`, `synth_yolo_dir`, `output_dir` -- can reuse directly
- Current validation tests synthetic-to-real transfer: trains on synthetic, tests on real
- Need 2000 images per model (400 per defect) for statistically meaningful YOLO training
- YOLOv8n training on 2000 images: ~2-4h on RTX 3090 (100 epochs, early stopping)
- 3 models x 4h = 12h YOLO training total

## Requirements

### Functional
- Generate 2000 synthetic images for each of top 2 models + baseline (6000 total)
- Convert to YOLO format (images + labels with bounding boxes from masks)
- Train YOLOv8n on each model's synthetic dataset
- Evaluate all 3 on same held-out real test set
- Compare mAP@50, mAP@50-95, per-class AP
- Produce final recommendation report

### Non-functional
- Reuse existing `validation-main.py` pipeline (no reinvention)
- Identical YOLO hyperparams across all 3 runs
- Same real test set for all evaluations
- Results reproducible (fixed random seeds)

## Architecture

### Data Flow
```
Phase 6 selects: top2 = [model_A, model_B]
    |
    v
Generate 2000 images each (model_A, model_B, baseline)
    |
    v
Convert to YOLO format (image + label with bbox from mask)
    |
    v
Train YOLOv8n on each synthetic dataset (3 training runs)
    |
    v
Evaluate all 3 on held-out real test set
    |
    v
Compare mAP -> select winner
```

### Directory Structure
```
output/benchmark/validation/
├── datasets/
│   ├── baseline/
│   │   ├── images/
│   │   │   ├── train/ (2000 synthetic)
│   │   │   └── val/ (real validation split)
│   │   ├── labels/
│   │   │   ├── train/ (YOLO format .txt)
│   │   │   └── val/
│   │   └── data.yaml
│   ├── model_a/
│   │   └── ... (same structure)
│   └── model_b/
│       └── ... (same structure)
├── runs/
│   ├── baseline/
│   │   └── detect/train/ (YOLOv8 output)
│   ├── model_a/
│   │   └── detect/train/
│   └── model_b/
│       └── detect/train/
└── final-benchmark-report.md
```

### YOLO Label Format
Each synthetic image needs a `.txt` label with bounding box derived from its binary mask:
```
# class_id center_x center_y width height (normalized 0-1)
0 0.5234 0.4891 0.1562 0.0312
```

Class IDs: `0=crack, 1=porosity, 2=inclusion, 3=lack_of_fusion, 4=undercut`

## Related Code Files
- **Reuse**: `pipeline/validation/validation-main.py` (main entry point)
- **Reuse**: `pipeline/validation/yolo-trainer.py` (YOLOv8 training wrapper)
- **Reuse**: `pipeline/validation/evaluation-metrics.py` (mAP computation)
- **Create**: `pipeline/benchmark/run-benchmark-validation.py` (orchestrator)
- **Create**: `pipeline/benchmark/convert-synthetic-to-yolo-format.py` (mask -> bbox labels)

## Implementation Steps

### Step 1: Generate 2000 Images per Selected Model

Reuse `run-benchmark-generation.py` from Phase 5 with increased count:

```bash
# Update batch config total_images to 2000
# Or pass as CLI argument
python3 pipeline/benchmark/run-benchmark-generation.py \
    --model baseline --count 2000
python3 pipeline/benchmark/run-benchmark-generation.py \
    --model model_a --count 2000
python3 pipeline/benchmark/run-benchmark-generation.py \
    --model model_b --count 2000
```

Already have 500 per model from Phase 5; generate additional 1500 (new seeds).

### Step 2: Create `convert-synthetic-to-yolo-format.py`

Convert binary mask to YOLO bounding box label:

```python
import cv2
import numpy as np
from pathlib import Path

DEFECT_CLASS_MAP = {
    "crack": 0,
    "porosity": 1,
    "inclusion": 2,
    "lack_of_fusion": 3,
    "undercut": 4,
}

def mask_to_yolo_bbox(mask_path: str, class_id: int) -> str:
    """Convert binary mask to YOLO bbox format.

    Returns:
        YOLO label string: "class_id cx cy w h" (normalized)
    """
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    h, w = mask.shape

    # Threshold and find contours
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return ""

    # Get bounding rect of largest contour
    largest = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(largest)

    # Normalize to [0, 1]
    cx = (x + bw / 2) / w
    cy = (y + bh / 2) / h
    nw = bw / w
    nh = bh / h

    return f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"
```

For each synthetic image:
- Find corresponding mask (saved during Phase 5 generation)
- Convert mask -> YOLO bbox label
- Save `.txt` file alongside image

### Step 3: Prepare YOLO Dataset Structure

For each model:
```python
def prepare_yolo_dataset(
    model_short: str,
    synth_images_dir: Path,
    synth_labels_dir: Path,
    real_val_dir: Path,
    output_dir: Path
):
    """Create YOLO dataset directory with train (synthetic) and val (real)."""

    # Train split: all 2000 synthetic images + labels
    train_images = output_dir / "images" / "train"
    train_labels = output_dir / "labels" / "train"

    # Val split: real images + labels (same across all models)
    val_images = output_dir / "images" / "val"
    val_labels = output_dir / "labels" / "val"

    # Symlink or copy files
    # ...

    # Write data.yaml
    data_yaml = {
        "train": str(train_images),
        "val": str(val_images),
        "nc": 5,
        "names": ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
    }
```

### Step 4: Create `run-benchmark-validation.py`

Orchestrate the full validation:

```python
"""
Benchmark YOLOv8 Validation Runner.

Trains YOLOv8 on synthetic data from top 2 models + baseline,
evaluates on real test set, compares mAP.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

from validation.yolo_trainer import train_yolo
from validation.evaluation_metrics import evaluate_model, compare_experiments

def run_benchmark_validation(
    models: list,          # e.g., ["baseline", "medxray", "realvis"]
    real_test_dir: Path,   # held-out real test set
    output_dir: Path,
    epochs: int = 100,
    batch_size: int = 16,
    model_size: str = "n"  # YOLOv8n
):
    results = {}

    for model_short in models:
        dataset_dir = output_dir / "datasets" / model_short
        data_yaml = dataset_dir / "data.yaml"

        # Train YOLOv8
        train_result = train_yolo(
            data_yaml_path=data_yaml,
            experiment_name=f"benchmark_{model_short}",
            output_dir=output_dir / "runs" / model_short,
            model_size=model_size,
            epochs=epochs,
            batch_size=batch_size,
            patience=50
        )

        # Evaluate on real test set
        eval_result = evaluate_model(
            model_path=train_result["best_model_path"],
            data_yaml=data_yaml,
            output_dir=output_dir / "runs" / model_short / "eval"
        )

        results[model_short] = {
            "train": train_result,
            "eval": eval_result
        }

    # Compare all models
    comparison = compare_experiments(results)
    return comparison
```

### Step 5: Run Validation

```bash
python3 pipeline/benchmark/run-benchmark-validation.py \
    --models baseline model_a model_b \
    --real-test-dir path/to/real/test/yolo \
    --output-dir output/benchmark/validation \
    --epochs 100 \
    --batch-size 16
```

### Step 6: Generate Final Report

`output/benchmark/validation/final-benchmark-report.md`:

```markdown
# Base Model Benchmark - Final Results

## YOLOv8 Detection Performance (mAP on Real Test Set)

| Model | mAP@50 | mAP@50-95 | Crack AP | Porosity AP | Inclusion AP | LOF AP | Undercut AP |
|-------|--------|-----------|----------|-------------|--------------|--------|-------------|
| baseline | 0.XX | 0.XX | ... | ... | ... | ... | ... |
| model_a  | 0.XX | 0.XX | ... | ... | ... | ... | ... |
| model_b  | 0.XX | 0.XX | ... | ... | ... | ... | ... |

## Phase 6 Image Quality Metrics

| Model | FID | SSIM | Sharpness | Composite |
|-------|-----|------|-----------|-----------|
| ... | ... | ... | ... | ... |

## Recommendation
Winner: {model_name}
- mAP improvement: +X.X% over baseline
- Image quality: {composite score comparison}
- Setup complexity: {notes on VAE, etc.}

## Action Items
- [ ] Update production checkpoint to winner
- [ ] Retrain all 5 production LoRAs on winner base
- [ ] Update pipeline configs
- [ ] Run full production validation
```

### Step 7: Handle Real Test Set

<!-- Updated: Validation Session 1 - Real test set confirmed at output/dataset-test/ -->
**Known location**: Real test set exists at:
- YOLO format: `output/dataset-test/yolo/data.yaml`
- COCO format: `output/dataset-test/annotations/coco_test.json`

**Pre-validation steps required**:
1. Fix `data.yaml` paths (currently may have stale absolute paths)
2. Verify annotations cover all 5 defect classes (currently confirmed for crack only -- check porosity, inclusion, LOF, undercut)
3. Count images per class to ensure statistical significance (need ≥20 per class)
4. If missing classes: supplement from GDXray dataset with manual annotation

**Critical**: This test set must NOT overlap with LoRA training data.

## Todo List
- [ ] Verify real test set exists and is properly annotated
- [ ] Generate 2000 images for top 2 models + baseline
- [ ] Implement `convert-synthetic-to-yolo-format.py`
- [ ] Prepare YOLO datasets (3 variants)
- [ ] Implement `run-benchmark-validation.py`
- [ ] Train YOLOv8 on baseline synthetic data
- [ ] Train YOLOv8 on model_a synthetic data
- [ ] Train YOLOv8 on model_b synthetic data
- [ ] Evaluate all 3 on real test set
- [ ] Compare mAP and per-class AP
- [ ] Generate final benchmark report
- [ ] Document winner and recommended next steps

## Success Criteria
- All 3 YOLOv8 models trained successfully (no crashes, reasonable loss curves)
- mAP evaluated on identical real test set for all 3
- At least 1 challenger achieves higher mAP@50 than baseline
- Per-class AP breakdown shows which defect types benefit most
- Final report with clear recommendation and action items
- All results reproducible (configs, seeds, data splits documented)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| No annotated real test set available | High | Create from existing data; or use GDXray with manual annotation |
| All models perform similarly (within noise) | Medium | Increase synthetic count to 3000; check per-class performance |
| YOLO training diverges on some synthetic data | Low | Early stopping (patience=50); verify data format before training |
| Mask-to-bbox conversion loses defect location | Low | Visual spot-check: overlay bbox on images for 20 samples |
| Insufficient real test data (<100 images) | Medium | Augment real test set; or use k-fold cross-validation |

## Security Considerations
- No external data uploaded; all processing local
- Model weights stay on local machine
- Real test data paths should not be committed to git

## Unresolved Questions
1. **Real test set location and size**: Must verify before starting. Check `pipeline/validation/` for existing splits.
2. **Synthetic ratio experiment**: Should we also test mixed datasets (real + synthetic)? Existing `validation-main.py` supports `synthetic_ratios` param -- consider testing 100% synthetic vs 50/50 mix.
3. **Which epoch checkpoint to use**: Phase 4 saves at epochs 10, 15, 20. Should we YOLO-validate all 3 epochs for top models? This triples training runs but finds optimal epoch.

## Next Steps (Post-Benchmark)
If a challenger wins:
1. Update `defect-type-prompt-templates.yaml` production `model_paths.checkpoint`
2. Retrain all 5 production LoRAs on new base model
3. Run production validation pipeline to confirm
4. Update `batch-config.yaml` with new LoRA names
5. Archive benchmark data and report
