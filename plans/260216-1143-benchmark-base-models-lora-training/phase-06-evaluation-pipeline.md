# Phase 6: Evaluation Pipeline

## Context Links
- [Plan Overview](plan.md)
- [Phase 5: Pilot Generation](phase-05-pilot-generation.md)
- [Research: Evaluation Pipeline Design](research/researcher-02-evaluation-pipeline-design.md)
- Existing SSIM code: `pipeline/qa/ssim-background-checker.py`
- Existing visual grid: `pipeline/qa/visual-spot-check-grid.py`

## Overview
- **Priority**: P1 (determines top 2 models for Phase 7)
- **Status**: complete
- **Effort**: 4h
- **Description**: Automated evaluation of 2500 generated images using FID, SSIM, edge sharpness. Produce composite scores, ranking, and HTML visual comparison grid. Select top 2 models for YOLOv8 validation.

## Key Insights
- FID requires 3-channel images; replicate grayscale to RGB (`img.repeat(1, 3, 1, 1)`)
- FID needs real reference dataset -- use GDXray or existing real X-ray training data from `kohya-ss/training_data/`
- SSIM: compare synthetic vs real per-defect-type (not pairwise per image; use distribution mean)
- Edge sharpness (Laplacian variance): apply on defect ROI if masks available, else full image
- Composite score: `0.4*FID_norm + 0.4*SSIM + 0.2*Sharpness_norm`
- HTML grid: 5 models x 5 defects = 25 cells, same seed per row

## Requirements

### Functional
- Compute FID per model (pooled across all defects against real dataset)
- Compute SSIM per model per defect type (synthetic vs real distribution)
- Compute Laplacian sharpness per model per defect type
- Normalize all metrics to [0, 1] range
- Compute weighted composite score per model
- Rank models by composite score
- Generate HTML visual comparison grid (5x5 with metrics)
- Output JSON results file for downstream consumption

### Non-functional
- Single script entry point
- Process all 2500 images in <15 min on CPU
- Reusable for future benchmarks

## Architecture

### Metrics Summary

| Metric | Library | Scope | Direction |
|--------|---------|-------|-----------|
| FID | `torch-fidelity` or `torchmetrics` | Per model (all defects pooled) | Lower = better |
| SSIM | `scikit-image` | Per model per defect | Higher = better |
| Laplacian Sharpness | `opencv-python` | Per model per defect | Higher = better |

### Real Reference Dataset
Use existing training data as "real" reference:
```
kohya-ss/training_data/
├── crack/1_xray_crack/*.png        # real crack images
├── porosity/1_xray_porosity/*.png
├── inclusion/1_xray_inclusion/*.png
├── lack_of_fusion/1_xray_lof/*.png
└── undercut/1_xray_undercut/*.png
```

For FID: pool all real images (all defects) into one set vs all synthetic per model.
For SSIM: compare per defect type.

### Script Structure
```
pipeline/benchmark/
├── benchmark-evaluation-pipeline.py     # main entry point
├── benchmark-metrics-calculator.py      # FID, SSIM, sharpness functions
└── benchmark-html-report-generator.py   # HTML grid generation
```

## Related Code Files
- **Read**: `pipeline/qa/ssim-background-checker.py` (reuse SSIM pattern)
- **Read**: `pipeline/qa/visual-spot-check-grid.py` (reuse grid pattern)
- **Create**: `pipeline/benchmark/benchmark-evaluation-pipeline.py`
- **Create**: `pipeline/benchmark/benchmark-metrics-calculator.py`
- **Create**: `pipeline/benchmark/benchmark-html-report-generator.py`
- **Create**: `output/benchmark/evaluation-results.json`
- **Create**: `output/benchmark/evaluation-report.html`

## Implementation Steps

### Step 1: Create `benchmark-metrics-calculator.py`

**FID Calculation:**
```python
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from torchmetrics.image.fid import FrechetInceptionDistance

def compute_fid(real_dir: Path, synthetic_dir: Path, batch_size: int = 32) -> float:
    """Compute FID between real and synthetic image directories.

    Args:
        real_dir: Directory with real images (all defect types pooled)
        synthetic_dir: Directory with synthetic images for one model
        batch_size: Batch size for feature extraction

    Returns:
        FID score (lower = better)
    """
    fid = FrechetInceptionDistance(feature=2048, normalize=True)

    # Load real images, convert grayscale -> 3-channel
    real_images = load_images_as_tensor(real_dir, batch_size)
    for batch in real_images:
        batch_rgb = batch.repeat(1, 3, 1, 1) if batch.shape[1] == 1 else batch
        fid.update(batch_rgb, real=True)

    # Load synthetic images
    synth_images = load_images_as_tensor(synthetic_dir, batch_size)
    for batch in synth_images:
        batch_rgb = batch.repeat(1, 3, 1, 1) if batch.shape[1] == 1 else batch
        fid.update(batch_rgb, real=False)

    return fid.compute().item()
```

**SSIM Calculation:**
```python
from skimage.metrics import structural_similarity as ssim
import cv2

def compute_ssim_distribution(
    real_dir: Path,
    synthetic_dir: Path,
    sample_pairs: int = 50
) -> dict:
    """Compute mean SSIM between random pairs of real and synthetic images.

    Uses random pairing (not 1:1) since images aren't aligned.

    Returns:
        {"mean": float, "std": float, "min": float, "max": float}
    """
    real_images = sorted(real_dir.glob("*.png"))
    synth_images = sorted(synthetic_dir.glob("*.png"))

    scores = []
    for i in range(min(sample_pairs, len(synth_images))):
        real_img = cv2.imread(str(real_images[i % len(real_images)]), cv2.IMREAD_GRAYSCALE)
        synth_img = cv2.imread(str(synth_images[i]), cv2.IMREAD_GRAYSCALE)

        # Resize to same dimensions if needed
        if real_img.shape != synth_img.shape:
            real_img = cv2.resize(real_img, (512, 512))
            synth_img = cv2.resize(synth_img, (512, 512))

        score = ssim(real_img, synth_img, data_range=255,
                     gaussian_weights=True, sigma=1.5)
        scores.append(score)

    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "min": float(np.min(scores)),
        "max": float(np.max(scores))
    }
```

**Laplacian Sharpness:**
```python
def compute_sharpness(image_dir: Path) -> dict:
    """Compute mean Laplacian variance (sharpness) for directory of images.

    Returns:
        {"mean": float, "std": float, "per_image": list[float]}
    """
    scores = []
    for img_path in sorted(image_dir.glob("*.png")):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        scores.append(float(laplacian.var()))

    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "per_image": scores
    }
```

### Step 2: Create `benchmark-evaluation-pipeline.py`

Main entry point:

```python
"""
Benchmark Evaluation Pipeline.

Computes FID, SSIM, sharpness for all 5 models, produces composite ranking.
"""

MODELS = ["baseline", "medxray", "realvis", "absreal", "cyberreal"]
DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

REAL_DATA_DIR = PROJECT_ROOT / "kohya-ss" / "training_data"
BENCHMARK_DIR = PROJECT_ROOT / "output" / "benchmark"

# Mapping defect -> real data subdirectory pattern
REAL_DEFECT_DIRS = {
    "crack": "crack/1_xray_crack",
    "porosity": "porosity/1_xray_porosity",
    "inclusion": "inclusion/1_xray_inclusion",
    "lack_of_fusion": "lack_of_fusion/1_xray_lof",
    "undercut": "undercut/1_xray_undercut",
}
```

**Pipeline flow:**

1. For each model, compute FID (pool all 500 synthetic vs all real):
   ```python
   for model in MODELS:
       synth_dir = BENCHMARK_DIR / model  # all defect subdirs
       real_dir = collect_all_real_images()  # temporary flat dir or list
       results[model]["fid"] = compute_fid(real_dir, synth_dir)
   ```

2. For each model x defect, compute SSIM:
   ```python
   for model in MODELS:
       for defect in DEFECTS:
           synth_dir = BENCHMARK_DIR / model / defect
           real_dir = REAL_DATA_DIR / REAL_DEFECT_DIRS[defect]
           results[model]["ssim"][defect] = compute_ssim_distribution(real_dir, synth_dir)
   ```

3. For each model x defect, compute sharpness:
   ```python
   for model in MODELS:
       for defect in DEFECTS:
           synth_dir = BENCHMARK_DIR / model / defect
           results[model]["sharpness"][defect] = compute_sharpness(synth_dir)
   ```

4. Normalize and compute composite:
   ```python
   # FID normalization (inverted: lower FID = higher score)
   max_fid = max(r["fid"] for r in results.values())
   for model in MODELS:
       results[model]["fid_norm"] = 1.0 - (results[model]["fid"] / max_fid)

   # SSIM: already [0, 1], use mean across defects
   for model in MODELS:
       ssim_vals = [results[model]["ssim"][d]["mean"] for d in DEFECTS]
       results[model]["ssim_mean"] = np.mean(ssim_vals)

   # Sharpness normalization
   max_sharp = max(
       np.mean([results[m]["sharpness"][d]["mean"] for d in DEFECTS])
       for m in MODELS
   )
   for model in MODELS:
       sharp_vals = [results[model]["sharpness"][d]["mean"] for d in DEFECTS]
       results[model]["sharpness_norm"] = np.mean(sharp_vals) / max_sharp

   # Composite
   W_FID, W_SSIM, W_SHARP = 0.4, 0.4, 0.2
   for model in MODELS:
       results[model]["composite"] = (
           W_FID * results[model]["fid_norm"] +
           W_SSIM * results[model]["ssim_mean"] +
           W_SHARP * results[model]["sharpness_norm"]
       )
   ```

5. Rank and print results table

6. Write `evaluation-results.json`

### Step 3: Create `benchmark-html-report-generator.py`

HTML grid with:
- Rows = 5 defect types
- Columns = 5 models (baseline first)
- Each cell = representative image (same seed across row) + metric annotations
- Summary table at top with composite scores and ranking
- Use Jinja2 template with base64-encoded inline images

```python
from jinja2 import Template
import base64

def generate_html_report(
    results: dict,
    benchmark_dir: Path,
    seeds_manifest: dict,
    output_path: Path
):
    """Generate HTML visual comparison report.

    Picks 3 representative seeds per defect (best SSIM, worst SSIM, median)
    for visual inspection.
    """
    # Select 1 representative seed per defect for the grid
    # Use the first seed from seeds.json for consistency
    representative_seeds = {
        defect: seeds[0] for defect, seeds in seeds_manifest.items()
    }

    # Build image grid data
    grid = {}
    for defect in DEFECTS:
        grid[defect] = {}
        for model in MODELS:
            # Find image matching representative seed
            img_path = find_image_by_seed(benchmark_dir / model / defect, representative_seeds[defect])
            if img_path:
                grid[defect][model] = encode_image_base64(img_path)
```

Template structure:
```html
<h1>Benchmark Evaluation Report</h1>
<h2>Composite Ranking</h2>
<table><!-- ranking table with scores --></table>

<h2>Visual Comparison Grid</h2>
<table class="comparison-grid">
  <tr><th>Defect</th>{% for m in models %}<th>{{ m }}</th>{% endfor %}</tr>
  {% for defect in defects %}
  <tr>
    <td>{{ defect }}</td>
    {% for model in models %}
    <td>
      <img src="data:image/png;base64,{{ grid[defect][model] }}" width="256"/>
      <div class="metrics">
        SSIM: {{ results[model].ssim[defect].mean | round(3) }}<br>
        Sharp: {{ results[model].sharpness[defect].mean | round(1) }}
      </div>
    </td>
    {% endfor %}
  </tr>
  {% endfor %}
</table>

<h2>Per-Defect Metric Charts</h2>
<!-- Bar charts via inline SVG or matplotlib base64 -->
```

### Step 4: Image Filename-to-Seed Mapping

Problem: `SaveImage` node generates filenames like `crack_000001_00001_.png` -- no seed in filename.

Solutions (pick one):
1. **Save metadata sidecar**: During Phase 5 generation, save `{img_name}.json` with seed info
2. **Use filename index**: Since generation is deterministic and sequential, image index maps to seed index
3. **Use ComfyUI metadata**: PNG metadata may contain seed in EXIF/tEXt chunks

**Recommended**: Option 2 (simplest). In Phase 5, save images with predictable naming: `{defect}_{seed}.png`. This requires custom save logic in `run-benchmark-generation.py` instead of relying on ComfyUI's SaveImage node.

Alternative: Download from ComfyUI output, rename locally using seed from job metadata.

### Step 5: Run Evaluation

```bash
python3 pipeline/benchmark/benchmark-evaluation-pipeline.py \
    --benchmark-dir output/benchmark \
    --real-data-dir kohya-ss/training_data \
    --output-dir output/benchmark
```

Output files:
- `output/benchmark/evaluation-results.json`
- `output/benchmark/evaluation-report.html`

### Step 6: Select Top 2 Models

From composite ranking, select top 2 models for Phase 7 (YOLOv8 validation).

If baseline is in top 2, select top 3 to ensure at least 2 challengers are tested.

## Dependencies (Python packages)
```
torch
torchmetrics          # FID
torch-fidelity        # FID backend
scikit-image          # SSIM
opencv-python         # Laplacian sharpness
Pillow                # Image loading
numpy
jinja2                # HTML report
```

## Todo List
- [ ] Implement `benchmark-metrics-calculator.py` (FID, SSIM, sharpness)
- [ ] Implement `benchmark-evaluation-pipeline.py` (orchestrator)
- [ ] Implement `benchmark-html-report-generator.py` (visual grid)
- [ ] Verify real reference dataset paths exist and have images
- [ ] Test FID calculation on small sample (10 real + 10 synthetic)
- [ ] Run full evaluation on 2500 images
- [ ] Generate HTML report
- [ ] Select top 2 models for Phase 7

## Success Criteria
- `evaluation-results.json` contains FID, SSIM, sharpness for all 5 models x 5 defects
- Composite scores computed and models ranked
- HTML report renders correctly with images and metrics
- Top 2 models identified with clear reasoning
- All metrics are reproducible (deterministic computation)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Not enough real images for reliable FID | Medium | Min 50 real images needed; check training data counts |
| FID unreliable for grayscale (Inception bias) | Medium | Use as relative ranking only, not absolute; weight equally with SSIM |
| SSIM scores all similar (no differentiation) | Low | Also compare sharpness + visual inspection |
| Jinja2 not installed | Low | `pip install jinja2`; or use string formatting fallback |
| Memory issues with torchmetrics FID | Low | Process in batches of 32; use GPU if available |

## Unresolved Questions
1. **Real dataset size per defect**: Need to verify count -- FID needs 50+ real images minimum
2. **Image naming convention**: Phase 5 must output predictable filenames for seed-to-image mapping
3. **Metric weights**: 0.4/0.4/0.2 are initial; may adjust after seeing first results

## Next Steps
- Top 2 models -> Phase 7 (full YOLOv8 validation with 2000 images each)
- If results are inconclusive, generate more images (200 per defect) and re-evaluate
