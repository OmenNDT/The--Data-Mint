# Quality Assurance Pipeline

Automated quality validation for synthetic X-ray defect images.

## Features

- **SSIM background check**: Validates inpainting preserves background
- **Annotation validation**: Ensures COCO/YOLO format correctness
- **Distribution verification**: Checks defect type balance
- **Visual spot-check**: HTML gallery for manual review

## Usage

### Basic Usage

```bash
# From pipeline root directory
python3 qa/qa-pipeline-main.py \
  --synthetic-dir /mnt/e/The\ Data\ Mint/output/synthetic \
  --dataset-dir /mnt/e/The\ Data\ Mint/output/dataset \
  --output-dir /mnt/e/The\ Data\ Mint/output/qa-reports
```

### Custom Parameters

```bash
python3 qa/qa-pipeline-main.py \
  --ssim-sample-size 1000 \
  --ssim-target 0.95 \
  --spot-check-pct 1.5
```

## QA Checks

### 1. SSIM Background Preservation

Compares original background vs synthetic image outside mask region.

- **Target**: SSIM > 0.90
- **Method**: Structural Similarity Index (skimage)
- **Sampling**: Random sample (default 500 images)

**Pass criteria**: Mean SSIM ≥ 0.90, pass rate ≥ 90%

### 2. Annotation Validation

Validates COCO and YOLO annotation formats.

**COCO checks:**
- Polygon within image bounds
- Bbox format [x, y, width, height]
- Category IDs in valid range (1-5)
- Area > 0

**YOLO checks:**
- Normalized coords in [0, 1]
- Class IDs in valid range (0-4)
- Positive dimensions

**Pass criteria**: 0 errors

### 3. Distribution Verification

Checks actual defect distribution matches configuration.

**Expected distribution:**
- crack: 25%
- porosity: 25%
- inclusion: 20%
- lack_of_fusion: 15%
- undercut: 15%

**Pass criteria**: Max deviation ≤ 2%

### 4. Visual Spot-Check

Generates HTML gallery with random sample.

**Default**: 2% of dataset (min 50, max 200)

**Review checklist:**
- [ ] Defect looks realistic
- [ ] Correct weld zone placement
- [ ] Background undistorted
- [ ] No color artifacts
- [ ] Annotation matches defect

## Output

```
qa-reports/
├── qa-report.md              # Markdown summary
├── qa-results.json           # Machine-readable results
└── spot-check-gallery.html   # Visual review gallery
```

## QA Report Example

```markdown
# Quality Assurance Report

## Summary

### SSIM Background Preservation ✓ PASS
- Checked: 500 images
- Mean SSIM: 0.947 (target: 0.90)
- Pass Rate: 94.2%

### Annotation Validation ✓ PASS
- COCO: PASS (20000 images, 20000 annotations)
- YOLO: PASS (20000 images, 20000 labels)

### Defect Distribution ✓ PASS
- Total Images: 20000
- Max Deviation: 1.2% (tolerance: 2%)

### Visual Spot Check
- Gallery: spot-check-gallery.html (400 images)
```

## Dependencies

- opencv-python (cv2)
- numpy
- scikit-image (SSIM)
- tqdm

## Thresholds

| Metric               | Default | Recommended Range |
|----------------------|---------|-------------------|
| SSIM target          | 0.90    | 0.85 - 0.95       |
| SSIM pass rate       | 90%     | 85% - 95%         |
| Distribution tolerance| 2%      | 1% - 3%           |
| Spot-check sample    | 2%      | 1% - 5%           |

## Performance

- SSIM check: ~1 second per image (GPU accelerated)
- Annotation validation: ~100,000 annotations/second
- Spot-check generation: ~10 images/second
- Total for 20K dataset: ~10-15 minutes
