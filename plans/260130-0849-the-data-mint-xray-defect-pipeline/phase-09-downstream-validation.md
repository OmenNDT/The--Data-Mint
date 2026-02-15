# Phase 09: Downstream Validation

## Context Links
- [Plan Overview](plan.md)
- [Research: Validation Strategy](research/researcher-02-masks-annotations-qa.md#4-downstream-validation-strategy)
- [Brainstorm: Downstream Validation](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P2 (validates overall pipeline success)
- **Status**: pending
- **Effort**: 4h
- **Description**: Train YOLOv8 defect detector using synthetic data. Compare performance across real-only, real+synthetic, synthetic-only experiments. Measure mAP improvement to prove pipeline value.

## Key Insights
- 2025 literature: YOLOv8 weld detection achieves mAP@50 up to 97.2%
- Synthetic augmentation: start 20% synthetic, max 50% of total dataset
- If mAP drops >3% when adding synthetic, reduce ratio or improve generation
- Domain gap: always evaluate on held-out REAL test set (never synthetic in test split)
- Train:val:test = 7:2:1, test set = 100% real images
- Active learning loop: misclassified real samples inform next generation iteration

## Requirements

### Functional
- 3 YOLOv8 training experiments: real-only, real+synthetic, synthetic-only
- Incremental synthetic ratio: 10% -> 20% -> 30% -> 50%
- Evaluation on held-out real test set: mAP@50, mAP@50-95, precision, recall
- Per-class performance breakdown (crack, porosity, LoF, LoP, slag)
- Domain gap analysis: confusion matrix, failure mode identification

### Non-Functional
- YOLOv8n (nano) for fast iteration; YOLOv8s (small) for final evaluation
- Epochs: 300, batch: 16, imgsz: 640
- Training on RTX 3090 (~2-4h per experiment)

## Architecture

```
validation/
├── configs/
│   ├── real-only.yaml           # 100% real data
│   ├── real-synth-10.yaml       # 90% real + 10% synthetic
│   ├── real-synth-20.yaml       # 80% real + 20% synthetic
│   ├── real-synth-30.yaml       # 70% real + 30% synthetic
│   ├── real-synth-50.yaml       # 50% real + 50% synthetic
│   └── synth-only.yaml          # 100% synthetic data
├── scripts/
│   ├── prepare-experiments.py   # Create dataset splits per experiment
│   ├── train-yolov8.py          # Training wrapper
│   └── evaluate-results.py      # Compare experiments, generate report
├── results/
│   ├── real-only/
│   ├── real-synth-10/
│   ├── real-synth-20/
│   ├── real-synth-30/
│   ├── real-synth-50/
│   └── synth-only/
└── reports/
    └── validation-report.md
```

## Related Code Files
- Create: all files in `validation/` structure above
- Depends on: `output/dataset/yolo/` (Phase 7 output)
- Depends on: `dataset/processed/` (Phase 2 real data)

## Implementation Steps

1. **Prepare Real Test Set**
   - Extract 10% of real GDXray patches as held-out test set
   - This set NEVER used in training (any experiment)
   - Annotate manually if not already in YOLO format
   - Store separately: `validation/test_real/`

2. **Create Experiment Datasets**
   ```python
   # prepare-experiments.py
   def create_mixed_dataset(real_dir, synth_dir, synth_ratio, output_dir):
       real_images = list_images(real_dir)
       synth_images = list_images(synth_dir)

       n_total = len(real_images)  # Keep total training size constant
       n_synth = int(n_total * synth_ratio)
       n_real = n_total - n_synth

       selected_real = random.sample(real_images, n_real)
       selected_synth = random.sample(synth_images, n_synth)

       # Copy images + labels to output_dir with train/val split
       create_split(selected_real + selected_synth, output_dir, train_ratio=0.875)
   ```

3. **Configure YOLOv8 Training**
   ```python
   # train-yolov8.py
   from ultralytics import YOLO

   def train_experiment(data_yaml, experiment_name):
       model = YOLO('yolov8n.pt')  # Nano for speed; 's' for final
       results = model.train(
           data=data_yaml,
           epochs=300,
           batch=16,
           imgsz=640,
           device=0,
           project='validation/results',
           name=experiment_name,
           patience=50,         # Early stopping
           save=True,
           plots=True
       )
       return results
   ```

4. **Run Experiments Sequentially**
   ```
   Experiment 1: real-only         (baseline)
   Experiment 2: real-synth-10     (10% synthetic)
   Experiment 3: real-synth-20     (20% synthetic)
   Experiment 4: real-synth-30     (30% synthetic)
   Experiment 5: real-synth-50     (50% synthetic)
   Experiment 6: synth-only        (upper bound of synthetic quality)
   ```
   - ~2-4h per experiment on RTX 3090
   - Total: ~12-24h for all 6 experiments

5. **Evaluate on Real Test Set**
   ```python
   # evaluate-results.py
   def evaluate_experiment(model_path, test_data_yaml):
       model = YOLO(model_path)
       metrics = model.val(data=test_data_yaml, split='test')
       return {
           'mAP50': metrics.box.map50,
           'mAP50_95': metrics.box.map,
           'precision': metrics.box.mp,
           'recall': metrics.box.mr,
           'per_class': metrics.box.maps  # Per-class mAP
       }
   ```

6. **Domain Gap Analysis**
   - Confusion matrix per experiment
   - Identify which defect types benefit most from synthetic data
   - Identify failure modes: false positives on synthetic-style artifacts?
   - Compare per-class mAP: which types improved, which degraded?

7. **Generate Validation Report**
   ```markdown
   # Downstream Validation Report

   ## Results Summary
   | Experiment | mAP@50 | mAP@50-95 | Precision | Recall |
   |-----------|--------|-----------|-----------|--------|
   | real-only | 0.82 | 0.61 | 0.85 | 0.79 |
   | real+10% synth | 0.85 | 0.64 | 0.87 | 0.82 |
   | real+20% synth | 0.88 | 0.67 | 0.89 | 0.85 |
   | real+30% synth | 0.90 | 0.69 | 0.90 | 0.87 |
   | real+50% synth | 0.89 | 0.68 | 0.88 | 0.86 |
   | synth-only | 0.72 | 0.52 | 0.78 | 0.70 |

   ## Key Findings
   - Optimal synthetic ratio: 30% (best mAP@50)
   - Diminishing returns beyond 30%
   - Porosity benefits most from synthetic augmentation
   - Synth-only proves domain gap exists but quality acceptable

   ## Per-Class Analysis
   ...

   ## Recommendation
   - Production ratio: 30% synthetic
   - Retrain LoRA for [weakest defect type] if needed
   ```

## Todo List
- [ ] Prepare held-out real test set (10% of real data)
- [ ] Create experiment dataset mixing scripts
- [ ] Generate 6 experiment datasets
- [ ] Train YOLOv8n on real-only (baseline)
- [ ] Train YOLOv8n on 10% synthetic
- [ ] Train YOLOv8n on 20% synthetic
- [ ] Train YOLOv8n on 30% synthetic
- [ ] Train YOLOv8n on 50% synthetic
- [ ] Train YOLOv8n on synth-only
- [ ] Evaluate all 6 experiments on real test set
- [ ] Generate confusion matrices and per-class analysis
- [ ] Write validation report with recommendations
- [ ] (Optional) Retrain best config with YOLOv8s for final numbers

## Success Criteria
- mAP@50 improvement with synthetic augmentation vs real-only baseline
- Optimal synthetic ratio identified (expected 20-30%)
- No catastrophic domain gap (synth-only mAP@50 > 60%)
- Per-class analysis identifies strengths and weaknesses
- Reproducible: seeds fixed, configs saved
- Target: real+synthetic mAP@50 > 0.90

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| Synthetic data hurts performance | High | Start small (10%), identify failing classes, fix generation |
| Too few real images for baseline | High | Use all GDXray series (W0001-W0003), augment with flips |
| YOLOv8 overfits on small real set | Medium | Use YOLOv8n, augmentation, early stopping (patience=50) |
| Domain gap too large | Medium | Improve LoRA training quality (Phase 3), add post-processing |
| Training takes too long | Low | Use YOLOv8n (fast), reduce epochs if convergence early |

## Security Considerations
- Model weights contain no sensitive data
- Training data paths in configs - sanitize before external sharing

## Next Steps
- If mAP improves: scale production to 100K images with validated settings
- If mAP degrades: iterate Phase 3 (LoRA quality) and Phase 4 (workflow settings)
- If specific defect type fails: collect more real examples for that type, retrain LoRA
