# Evaluation Pipeline Design for X-ray Base Model Benchmarking

**Date:** 2026-02-16
**Context:** Automated evaluation pipeline for comparing 5 SD 1.5 checkpoints generating 512x512 grayscale X-ray weld defect images

---

## 1. FID (Fréchet Inception Distance) for Grayscale X-rays

### Library Recommendations (Priority Order)

1. **torch-fidelity** (Recommended)
   - Most robust implementation with clean-resize support
   - Better grayscale handling via custom feature extractors
   - Reference: [torch-fidelity documentation](https://deepwiki.com/toshas/torch-fidelity/4.2-frechet-inception-distance-(fid))

2. **torchmetrics.image.FrechetInceptionDistance**
   - Part of PyTorch Lightning ecosystem, well-maintained
   - Requires torch-fidelity as dependency
   - Reference: [TorchMetrics FID](https://lightning.ai/docs/torchmetrics/stable/image/frechet_inception_distance.html)

3. **pytorch-fid** (Fallback)
   - Widely adopted, simpler API
   - Reference: [mseitzer/pytorch-fid](https://github.com/mseitzer/pytorch-fid)

### Grayscale Considerations

**Critical:** Standard FID uses Inception v3 trained on 3-channel RGB ImageNet data. For X-ray grayscale:

- Convert grayscale → RGB by channel replication (`image.repeat(3, 1, 1)`)
- Alternative: Train custom feature extractor on medical imaging dataset (overkill for this task)
- **Recommended approach:** Use 3-channel replication with torch-fidelity's clean-resize

**Implementation:**
```python
from torchmetrics.image.fid import FrechetInceptionDistance

fid = FrechetInceptionDistance(feature=2048, reset_real_features=False)
# Convert grayscale to 3-channel: imgs_rgb = imgs_gray.repeat(1, 3, 1, 1)
fid.update(real_images_rgb, real=True)
fid.update(fake_images_rgb, real=False)
score = fid.compute()
```

---

## 2. SSIM for Synthetic vs Real X-ray Comparison

### Library: scikit-image (Standard)

**Function:** `skimage.metrics.structural_similarity`

### Configuration for X-rays

- **Range:** `data_range=1.0` (if normalized 0-1) or `data_range=255` (uint8)
- **Gaussian weights:** `gaussian_weights=True, sigma=1.5`
- **Sample covariance:** `use_sample_covariance=False` (Wang et al. default)
- **Channel axis:** `channel_axis=None` (grayscale)

Reference: [scikit-image SSIM](https://scikit-image.org/docs/stable/auto_examples/transform/plot_ssim.html)

### Methodology

**Paired comparison:** Each synthetic image compared to corresponding real defect image
- Crack synthetic vs crack real
- Porosity synthetic vs porosity real
- etc.

**Aggregation:** Mean SSIM across all defect types per model

```python
from skimage.metrics import structural_similarity as ssim

ssim_score = ssim(
    real_xray,
    synthetic_xray,
    data_range=255,
    gaussian_weights=True,
    sigma=1.5,
    use_sample_covariance=False
)
```

---

## 3. Edge Sharpness Metrics for Defect Clarity

### Metrics Selection

**Laplacian Variance** (Primary)
- Measures focus/sharpness via second derivative
- Single scalar metric per image
- Higher variance = sharper edges
- Reference: [Image Quality Metrics](https://unimatrixz.com/blog/latent-space-measuring-image-quality-sharpness-clarity-resolution/)

**Sobel Gradient Magnitude** (Secondary)
- Directional edge strength (horizontal + vertical)
- Useful for resolution estimation
- Reference: [OpenCV Sobel](https://docs.opencv.org/3.4/d2/d2c/tutorial_sobel_derivatives.html)

### Implementation

```python
import cv2
import numpy as np

def laplacian_sharpness(image_gray):
    """Higher = sharper defect edges"""
    laplacian = cv2.Laplacian(image_gray, cv2.CV_64F)
    return laplacian.var()

def sobel_edge_strength(image_gray):
    """Mean gradient magnitude"""
    sobelx = cv2.Sobel(image_gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(image_gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobelx**2 + sobely**2)
    return magnitude.mean()
```

**Defect-specific ROI:** Apply metrics only to defect regions (use masks) for accurate clarity measurement

---

## 4. HTML Visual Comparison Grid

### Recommended Approach: Python + Jinja2 Templates

**Libraries:**
- `Jinja2` for templating
- `base64` for inline image embedding
- `matplotlib` / `PIL` for image processing

Reference: [scikit-image visual comparison](https://scikit-image.org/docs/stable/auto_examples/applications/plot_image_comparison.html)

### Grid Structure

```
┌─────────────┬────────┬────────┬────────┬────────┬────────┐
│ Defect Type │ Model1 │ Model2 │ Model3 │ Model4 │ Model5 │
├─────────────┼────────┼────────┼────────┼────────┼────────┤
│ Crack       │  img   │  img   │  img   │  img   │  img   │
│ Porosity    │  img   │  img   │  img   │  img   │  img   │
│ Inclusion   │  img   │  img   │  img   │  img   │  img   │
│ LOF         │  img   │  img   │  img   │  img   │  img   │
│ Undercut    │  img   │  img   │  img   │  img   │  img   │
└─────────────┴────────┴────────┴────────┴────────┴────────┘
```

**Features:**
- Inline base64 encoded images (portable single HTML file)
- Metric annotations below each image (FID, SSIM, Sharpness)
- CSS grid layout for responsive design
- Diff overlays (checkerboard, side-by-side) using scikit-image

### Template Snippet

```html
<table class="comparison-grid">
  {% for defect in defect_types %}
  <tr>
    <td>{{ defect }}</td>
    {% for model in models %}
    <td>
      <img src="data:image/png;base64,{{ images[model][defect] }}" />
      <div class="metrics">
        SSIM: {{ ssim_scores[model][defect]|round(3) }}<br>
        Sharp: {{ sharpness[model][defect]|round(1) }}
      </div>
    </td>
    {% endfor %}
  </tr>
  {% endfor %}
</table>
```

---

## 5. Composite Scoring Methodology

### Multi-Metric Ranking Framework

Reference: [Evaluation Metrics for Generative Models](https://www.mdpi.com/2504-4990/6/3/73)

### Recommended Composite Score

**Weighted average** with normalization:

```
Composite_Score = w1·FID_norm + w2·SSIM + w3·Sharpness_norm

Where:
- FID_norm = 1 - (FID / max_FID)  [inverted, lower is better]
- SSIM ∈ [0, 1]  [higher is better]
- Sharpness_norm = Sharpness / max_Sharpness  [higher is better]

Suggested weights:
- w1 = 0.4  (FID for distribution similarity)
- w2 = 0.4  (SSIM for perceptual quality)
- w3 = 0.2  (Sharpness for defect clarity)
```

### Rationale

- **FID:** Captures distribution match between synthetic and real datasets
- **SSIM:** Measures perceptual similarity at structural level
- **Sharpness:** Domain-specific metric for industrial NDT (defect visibility critical)

**Limitation:** FID and IS ranking can vary for close models (reference: [Pros and Cons of GAN Evaluation](https://arxiv.org/pdf/1802.03446)). Use composite score for coarse ranking, visual inspection for final selection.

### Alternative: Pareto Ranking

If no single "best" model needed:
- Plot models in 3D space (FID, SSIM, Sharpness)
- Identify Pareto frontier (non-dominated models)
- Select based on use-case priority (speed vs quality vs defect clarity)

---

## Implementation Pipeline Architecture

```
1. Generate images → 5 models × 5 defects × N samples
2. Calculate metrics:
   - FID: Per model (all defects pooled)
   - SSIM: Per model per defect (pairwise with real)
   - Sharpness: Per model per defect (ROI-based)
3. Normalize scores → [0, 1] range
4. Compute composite score → Rank models
5. Generate HTML grid → Visual + metrics table
```

### Tooling Stack

- **Metrics:** `torch-fidelity`, `scikit-image`, `opencv-python`
- **HTML:** `Jinja2`, `base64`
- **Data:** `pandas` (metric aggregation), `numpy`

---

## Unresolved Questions

1. **Real dataset availability:** Do we have paired real X-rays for each defect type for SSIM comparison?
2. **ROI masks:** Are defect masks available for ROI-based sharpness metrics, or compute on full image?
3. **Sample size:** How many images per defect type per model? (Affects FID reliability, min 50 recommended)
4. **Metric weights:** Should weights be empirically tuned via correlation with expert rankings?

---

## Sources

- [TorchMetrics FID](https://lightning.ai/docs/torchmetrics/stable/image/frechet_inception_distance.html)
- [torch-fidelity documentation](https://deepwiki.com/toshas/torch-fidelity/4.2-frechet-inception-distance-(fid))
- [pytorch-fid GitHub](https://github.com/mseitzer/pytorch-fid)
- [scikit-image SSIM](https://scikit-image.org/docs/stable/auto_examples/transform/plot_ssim.html)
- [Image Quality Metrics](https://unimatrixz.com/blog/latent-space-measuring-image-quality-sharpness-clarity-resolution/)
- [OpenCV Edge Detection](https://opencv.org/blog/edge-detection-using-opencv/)
- [OpenCV Sobel](https://docs.opencv.org/3.4/d2/d2c/tutorial_sobel_derivatives.html)
- [scikit-image visual comparison](https://scikit-image.org/docs/stable/auto_examples/applications/plot_image_comparison.html)
- [Evaluation Metrics for Generative Models](https://www.mdpi.com/2504-4990/6/3/73)
- [Pros and Cons of GAN Evaluation](https://arxiv.org/pdf/1802.03446)
- [GLIPS Perceptual Score](https://arxiv.org/html/2405.09426v2)
