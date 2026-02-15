# Downstream Validation Pipeline

Validates synthetic dataset quality by training YOLOv8 detectors and measuring performance on real test data.

## Features

- **Multiple experiments**: Real-only, mixed ratios, synth-only
- **YOLOv8 training**: Automated training with Ultralytics
- **mAP evaluation**: Performance on held-out real test set
- **Per-class analysis**: Identifies which defect types benefit most
- **Recommendations**: Optimal synthetic ratio for production

## Usage

### Prerequisites

```bash
# Install ultralytics
pip install ultralytics

# Prepare real test set in YOLO format
# Must be separate from training data (held-out)
```

### Basic Usage

```bash
# From pipeline root directory
python3 validation/validation-main.py \
  --real-yolo-dir /path/to/real/dataset \
  --synth-yolo-dir /mnt/e/The\ Data\ Mint/output/dataset/yolo \
  --output-dir /mnt/e/The\ Data\ Mint/output/validation
```

### Fast Prototyping (Fewer Epochs)

```bash
python3 validation/validation-main.py \
  --real-yolo-dir /path/to/real \
  --model-size n \
  --epochs 50 \
  --batch-size 16
```

### Production Validation (Full Training)

```bash
python3 validation/validation-main.py \
  --real-yolo-dir /path/to/real \
  --model-size s \
  --epochs 300 \
  --batch-size 16 \
  --ratios 0.0 0.10 0.20 0.30 0.50 1.0
```

### Custom Ratios

```bash
python3 validation/validation-main.py \
  --real-yolo-dir /path/to/real \
  --ratios 0.0 0.15 0.25 0.35
```

### Evaluate Existing Models (Skip Training)

```bash
python3 validation/validation-main.py \
  --real-yolo-dir /path/to/real \
  --skip-training
```

## Experiments

### Default Experiment Suite

| Experiment      | Synthetic Ratio | Purpose                          |
|-----------------|-----------------|----------------------------------|
| real-only       | 0%              | Baseline (no synthetic data)     |
| real-synth-10   | 10%             | Minimal augmentation             |
| real-synth-20   | 20%             | Light augmentation               |
| real-synth-30   | 30%             | Moderate augmentation            |
| real-synth-50   | 50%             | Heavy augmentation               |
| synth-only      | 100%            | Upper bound of synthetic quality |

### Expected Results

**Good synthetic quality:**
- real-synth-20 or real-synth-30 achieves best mAP
- Improvement over real-only: +5% to +15%
- Synth-only mAP: 70-85% of real-only

**Poor synthetic quality:**
- All mixed experiments worse than real-only
- Synth-only mAP: <60% of real-only
- Action: Improve LoRA training (Phase 3)

## Output Structure

```
validation/
├── datasets/                      # Mixed datasets
│   ├── real-only/
│   ├── real-synth-10/
│   ├── real-synth-20/
│   ├── real-synth-30/
│   ├── real-synth-50/
│   └── synth-only/
├── results/                       # Training results
│   ├── real-only/
│   │   ├── weights/
│   │   │   └── best.pt
│   │   ├── confusion_matrix.png
│   │   └── results.csv
│   └── ...
├── validation-report.md           # Summary report
└── validation-results.json        # Machine-readable results
```

## Validation Report Example

```markdown
# Downstream Validation Report

## Executive Summary

✓ VALIDATION PASSED: Synthetic data improves performance

- Best Configuration: real-synth-30
- Best mAP@50: 0.896
- Baseline (Real-only): 0.823
- Improvement: +0.073 (+8.9%)

Recommendation: Use 30% synthetic data ratio for production dataset.

## Results Overview

| Experiment      | mAP@50 | mAP@50-95 | Precision | Recall |
|-----------------|--------|-----------|-----------|--------|
| real-synth-30   | 0.896  | 0.682     | 0.901     | 0.871  |
| real-synth-20   | 0.884  | 0.671     | 0.895     | 0.865  |
| real-synth-50   | 0.879  | 0.668     | 0.887     | 0.863  |
| real-synth-10   | 0.851  | 0.647     | 0.871     | 0.842  |
| real-only       | 0.823  | 0.621     | 0.854     | 0.801  |
| synth-only      | 0.715  | 0.521     | 0.782     | 0.704  |

## Per-Class Performance

| Defect Type     | Real-only | Best Mixed | Improvement |
|-----------------|-----------|------------|-------------|
| crack           | 0.842     | 0.901      | +0.059      |
| porosity        | 0.831     | 0.895      | +0.064      |
| inclusion       | 0.798     | 0.887      | +0.089      |
| lack_of_fusion  | 0.817     | 0.894      | +0.077      |
| undercut        | 0.828     | 0.903      | +0.075      |

## Recommendations

1. Production Configuration: Use 30% synthetic data ratio
2. Scale-Up: Generate 28,571 total images (to achieve 20K effective training samples)
3. Next Steps: Monitor performance on real-world test cases
```

## Model Sizes

| Size | Parameters | GPU Memory | Training Time | Use Case           |
|------|------------|------------|---------------|--------------------|
| n    | 3.2M       | ~2GB       | Fast          | Prototyping        |
| s    | 11.2M      | ~4GB       | Medium        | Production         |
| m    | 25.9M      | ~8GB       | Slow          | High accuracy      |
| l    | 43.7M      | ~12GB      | Very slow     | Maximum accuracy   |
| x    | 68.2M      | ~16GB      | Extremely slow| Research           |

**Recommendation**: Use `n` for fast iteration, `s` for final validation

## Training Time Estimates

**Hardware**: RTX 3090 24GB, batch_size=16

| Experiment Count | Model | Epochs | Total Time      |
|------------------|-------|--------|-----------------|
| 6                | n     | 50     | ~2-3 hours      |
| 6                | n     | 100    | ~4-6 hours      |
| 6                | n     | 300    | ~12-18 hours    |
| 6                | s     | 100    | ~8-12 hours     |
| 6                | s     | 300    | ~24-36 hours    |

## Dependencies

```bash
pip install ultralytics
```

Ultralytics will auto-install:
- torch
- torchvision
- opencv-python
- pillow
- pyyaml
- tqdm

## Performance Metrics

### mAP (Mean Average Precision)

- **mAP@50**: IoU threshold 0.50 (standard for COCO)
- **mAP@50-95**: Average over IoU 0.50 to 0.95 (stricter)

**Target**: mAP@50 > 0.85 for production

### Per-Class mAP

Identifies which defect types are well-detected vs struggling.

**Action**: If specific class underperforms, collect more real examples or retrain LoRA for that type.

## Tips

### Speed Up Training

```bash
# Reduce epochs for prototyping
--epochs 50

# Use smaller model
--model-size n

# Test fewer ratios
--ratios 0.0 0.30 1.0
```

### Improve Performance

1. **More real data**: Collect additional real examples
2. **Better LoRAs**: Retrain with higher quality (Phase 3)
3. **Data augmentation**: Enable in YOLO training
4. **Early stopping**: Use patience parameter
5. **Learning rate tuning**: Adjust YOLO hyperparameters

## Troubleshooting

### CUDA Out of Memory

```bash
# Reduce batch size
--batch-size 8

# Use smaller model
--model-size n
```

### Training Diverges

- Check learning rate (auto-adjusted by YOLO)
- Verify annotations are correct (run Phase 8 QA)
- Ensure test set is truly held-out (no overlap with train)

### Low mAP on All Experiments

- Verify test set quality (manual review)
- Check if enough real training data (>100 images per class)
- Validate annotation format (YOLO expects 0-indexed classes)
