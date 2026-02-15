# Phase 08: Quality Assurance

## Context Links
- [Plan Overview](plan.md)
- [Research: FID/LPIPS Metrics](research/researcher-02-masks-annotations-qa.md#3-fidlpips-quality-metrics-for-grayscale-images)
- [Brainstorm: QA Pipeline](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: pending
- **Effort**: 5h
- **Description**: Automated quality validation pipeline using FID, LPIPS, SSIM metrics. Reject low-quality images. Verify defect distribution balance. Manual spot-check protocol.

## Key Insights
- FID for grayscale: replicate to 3-channel (`gray.repeat(3,1,1)`) for Inception-v3 input
- FID requires ~10K images for statistical convergence -> compute after batch, not per-image
- LPIPS pairwise: use for online filtering during generation (per-image feasible)
- LPIPS <0.10 safe, <0.05 ideal; SSIM >=0.95 baseline for background preservation
- No established FID thresholds for industrial X-rays -> need empirical calibration
- KID (Kernel Inception Distance) more robust for small sample sizes

## Requirements

### Functional
- FID score: synthetic vs real GDXray distribution (target <50)
- LPIPS pairwise diversity: reject copies/near-duplicates (threshold >0.10)
- SSIM background: verify inpainting preserves background (>0.95 outside mask)
- Defect distribution check: actual matches config within 2%
- Annotation validation: COCO polygon overlaps mask, YOLO bbox encloses defect
- Manual spot-check: random 1-2% sample with visual review checklist

### Non-Functional
- FID/LPIPS computation on GPU (RTX 3090)
- Per-image LPIPS check during generation (online filtering, Phase 6 integration)
- Batch FID after full generation completes

## Architecture

```
pipeline/
├── quality/
│   ├── __init__.py
│   ├── fid_evaluator.py       # FID computation (pytorch-fid)
│   ├── lpips_evaluator.py     # LPIPS diversity + similarity check
│   ├── ssim_evaluator.py      # SSIM background preservation
│   ├── distribution_check.py  # Defect type balance verification
│   ├── annotation_validator.py # COCO/YOLO annotation consistency
│   ├── spot_check.py          # Random sample selector + checklist
│   └── qa_report.py           # Generate HTML/markdown QA report
├── config/
│   └── qa-config.yaml
└── reports/
    └── qa-report-{timestamp}.md
```

## Related Code Files
- Create: all files in `pipeline/quality/` (8 files)
- Create: `pipeline/config/qa-config.yaml`
- Depends on: `pipeline/batch_manager/` (Phase 6) for online LPIPS integration
- Depends on: `pipeline/post_processor/` (Phase 7) for annotation files

## Implementation Steps

1. **Create QA Config**
   ```yaml
   # qa-config.yaml
   fid:
     real_images_dir: "C:/DataMint/dataset/processed/patches_512"
     batch_size: 50
     dims: 2048
     target: 50          # FID < 50 = acceptable

   lpips:
     net: "alex"
     reject_threshold: 0.10     # Reject if LPIPS > 0.10 (too different)
     duplicate_threshold: 0.02  # Flag if LPIPS < 0.02 (near duplicate)
     sample_pairs: 1000         # Number of pairwise comparisons

   ssim:
     target: 0.95               # Background preservation outside mask

   distribution:
     tolerance_pct: 2.0         # Acceptable deviation from config

   spot_check:
     sample_pct: 1.5            # 1.5% random sample
     min_samples: 50
   ```

2. **Implement FID Evaluator**
   ```python
   # fid_evaluator.py
   from pytorch_fid import fid_score

   def compute_fid(real_dir, synthetic_dir, batch_size=50, device='cuda'):
       """Compute FID between real and synthetic datasets.
       Grayscale images auto-converted to 3-channel by pytorch-fid."""
       return fid_score.calculate_fid_given_paths(
           [real_dir, synthetic_dir],
           batch_size=batch_size,
           device=device,
           dims=2048
       )
   ```
   - Ensure real and synthetic dirs contain PNG files
   - Grayscale -> 3-channel conversion handled by pytorch-fid loader
   - If not, add preprocessing: replicate grayscale to 3ch before saving

3. **Implement LPIPS Evaluator**
   ```python
   # lpips_evaluator.py - two modes

   # Mode 1: Online (during generation, per-image)
   def check_single_image(new_image, reference_pool, threshold=0.10):
       """Compare new image against recent N images for diversity."""
       for ref in reference_pool[-50:]:  # Check last 50
           d = loss_fn(new_image, ref)
           if d.item() < 0.02:
               return "duplicate"
           if d.item() > threshold:
               return "reject"
       return "accept"

   # Mode 2: Batch (after generation, pairwise sample)
   def compute_diversity_score(image_dir, n_pairs=1000):
       """Random pairwise LPIPS to measure dataset diversity."""
       distances = []
       for _ in range(n_pairs):
           img1, img2 = random.sample(images, 2)
           d = loss_fn(load(img1), load(img2))
           distances.append(d.item())
       return np.mean(distances), np.std(distances)
   ```

4. **Implement SSIM Background Check**
   - Compare original clean background with inpainted result OUTSIDE mask region
   - `skimage.metrics.structural_similarity(bg_original, bg_inpainted, data_range=255)`
   - Target: SSIM > 0.95 outside mask

5. **Implement Distribution Checker**
   - Count images per defect type
   - Compare against config distribution
   - Flag if any type deviates >2% from target

6. **Implement Annotation Validator**
   - For each COCO annotation: verify polygon falls within image bounds
   - For each YOLO label: verify normalized coords in [0, 1]
   - Cross-check: COCO bbox should roughly match YOLO bbox (accounting for format diff)
   - Verify annotation count matches image count

7. **Implement Spot-Check Protocol**
   - Randomly select 1-2% of images (min 50)
   - Generate HTML gallery with image + overlaid annotation
   - Checklist per image:
     - [ ] Defect looks realistic
     - [ ] Defect is in correct weld zone
     - [ ] Background undistorted
     - [ ] No color artifacts
     - [ ] Annotation matches visible defect

8. **Generate QA Report**
   ```markdown
   # QA Report - {timestamp}
   ## Summary
   - Total images: 20,000
   - FID score: 38.2 (target <50) PASS
   - Mean LPIPS diversity: 0.42 +/- 0.12 PASS
   - SSIM background: 0.97 (target >0.95) PASS
   - Distribution deviation: max 1.2% PASS

   ## Rejected Images
   - Near-duplicates: 23 (0.12%)
   - Low quality (LPIPS>0.10): 45 (0.23%)

   ## Distribution
   | Defect | Target | Actual | Delta |
   | crack | 25.0% | 24.8% | -0.2% |
   ...

   ## Spot-Check
   - [Gallery link](spot-check-gallery.html)
   ```

## Todo List
- [ ] Create qa-config.yaml
- [ ] Implement FID evaluator (grayscale -> 3ch handling)
- [ ] Implement LPIPS evaluator (online + batch modes)
- [ ] Implement SSIM background preservation check
- [ ] Implement defect distribution checker
- [ ] Implement annotation validator (COCO + YOLO)
- [ ] Implement spot-check random sampler + gallery generator
- [ ] Implement QA report generator (markdown)
- [ ] Integrate online LPIPS into batch manager (Phase 6)
- [ ] Run QA on pilot batch (1000 images)
- [ ] Calibrate thresholds based on pilot results

## Success Criteria
- FID < 50 for full synthetic dataset vs real GDXray
- No near-duplicate images (LPIPS > 0.02 pairwise)
- SSIM > 0.95 for background preservation
- Defect distribution within 2% of config
- All COCO/YOLO annotations valid
- Spot-check: >95% of sampled images pass visual review
- QA report generated automatically

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| FID thresholds not calibrated for X-ray | High | Run on real-vs-real baseline first, establish reference FID |
| LPIPS too strict -> high reject rate | Medium | Start permissive (0.12), tighten after calibration |
| Spot-check reveals systematic issues | Medium | Feed back to Phase 3-4 for LoRA/workflow refinement |
| FID computation OOM on large dataset | Low | Process in chunks, compute statistics incrementally |

## Security Considerations
- QA report may contain image paths - sanitize for external sharing
- GPU memory management: release LPIPS model between batch computations

## Next Steps
- Phase 9: Use QA-validated dataset for downstream YOLOv8 training
- If QA fails: iterate Phase 3 (LoRA) or Phase 4 (workflow) before re-generation
