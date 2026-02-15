# Research Report: Masks, Annotations & QA Pipeline
**Date:** 2026-01-30
**Topics:** Defect mask generation, COCO/YOLO conversion, FID/LPIPS metrics, validation strategy

---

## 1. Defect-Specific Mask Generation Algorithms

### Procedural Generation Libraries
- **OpenCV + scikit-image + numpy**: Industry standard for procedural mask generation
- **SpongeBob** (GitHub): Calculates material porosity via image processing
- **IMPPY3D**: Proven for 3D analysis of internal pores/defects, concrete aggregates

### Defect Pattern Generation

**Crack (elongated linear shapes, branching)**
```python
import cv2, numpy as np
from skimage.draw import line, bezier_curve

# Linear crack with perturbation
def generate_crack_mask(h, w):
    mask = np.zeros((h, w), dtype=np.uint8)
    y_start, y_end = np.random.randint(0, h, 2)
    x_start, x_end = 0, w
    # Add random walk for realistic branching
    points = [(x_start, y_start)]
    for x in range(x_start, x_end, 10):
        y = y_start + int((y_end - y_start) * x / w) + np.random.randint(-5, 5)
        points.append((x, y))
    # Draw polyline with thickness
    cv2.polylines(mask, [np.array(points)], False, 255, thickness=2)
    return mask
```

**Porosity (circular clusters, scattered dots)**
```python
def generate_porosity_mask(h, w, n_pores=20):
    mask = np.zeros((h, w), dtype=np.uint8)
    cluster_center = (np.random.randint(w), np.random.randint(h))
    for _ in range(n_pores):
        # Clustered distribution
        r = np.random.rayleigh(30)  # distance from cluster center
        theta = np.random.uniform(0, 2*np.pi)
        x = int(cluster_center[0] + r * np.cos(theta))
        y = int(cluster_center[1] + r * np.sin(theta))
        radius = np.random.randint(2, 8)
        cv2.circle(mask, (x, y), radius, 255, -1)
    return mask
```

**Lack of Fusion/Penetration (linear/planar parallel to weld)**
```python
def generate_lof_mask(h, w, weld_axis='horizontal'):
    mask = np.zeros((h, w), dtype=np.uint8)
    if weld_axis == 'horizontal':
        y = h // 2 + np.random.randint(-20, 20)
        cv2.line(mask, (0, y), (w, y), 255, thickness=3)
    return mask
```

**Slag Inclusion (irregular blob shapes)**
```python
from scipy.ndimage import gaussian_filter

def generate_slag_mask(h, w):
    mask = np.zeros((h, w), dtype=np.uint8)
    # Random blob via gaussian noise thresholding
    blob = np.random.rand(h//4, w//4) > 0.7
    blob = gaussian_filter(blob.astype(float), sigma=2)
    blob = (blob > 0.3).astype(np.uint8) * 255
    # Resize and position
    blob = cv2.resize(blob, (w//2, h//3))
    x, y = np.random.randint(0, w-w//2), np.random.randint(0, h-h//3)
    mask[y:y+h//3, x:x+w//2] = blob
    return mask
```

### Randomization Strategy
- **Size**: Scale masks by 0.5x to 2x
- **Position**: Random placement within weld ROI (center ±30% of image)
- **Orientation**: `cv2.getRotationMatrix2D()` for -15° to +15° rotation
- **Weld zone constraint**: Multiply mask by binary weld seam mask before export

**References:**
- [Expert-aware multi-stage AI-assisted weld defect detection (2025)](https://www.tandfonline.com/doi/full/10.1080/10589759.2025.2575884)
- [WeldVGG: VGG-Inspired Weld Defect Classification](https://www.mdpi.com/1424-8220/25/19/6183)
- [GitHub: SpongeBob - Porosity Calculation](https://github.com/Bill2462/SpongeBob)

---

## 2. COCO + YOLO Annotation Format Conversion

### Mask → COCO Polygon
```python
from pycocotools import mask as maskUtils
import cv2

def mask_to_coco_polygon(binary_mask):
    """Convert binary mask to COCO polygon format"""
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    for contour in contours:
        if contour.size >= 6:  # min 3 points
            segmentation = contour.flatten().tolist()
            polygons.append(segmentation)

    # Compute bbox from mask
    pos = np.where(binary_mask)
    xmin, ymin = int(np.min(pos[1])), int(np.min(pos[0]))
    xmax, ymax = int(np.max(pos[1])), int(np.max(pos[0]))
    bbox = [xmin, ymin, xmax - xmin, ymax - ymin]
    area = int(np.sum(binary_mask > 0))

    return {
        "segmentation": polygons,
        "bbox": bbox,
        "area": area,
        "iscrowd": 0
    }
```

### Mask → YOLO Bounding Box
```python
def mask_to_yolo_bbox(binary_mask, img_w, img_h):
    """Convert binary mask to YOLO format (x_center, y_center, width, height) normalized"""
    pos = np.where(binary_mask)
    xmin, ymin = np.min(pos[1]), np.min(pos[0])
    xmax, ymax = np.max(pos[1]), np.max(pos[0])

    x_center = ((xmin + xmax) / 2) / img_w
    y_center = ((ymin + ymax) / 2) / img_h
    width = (xmax - xmin) / img_w
    height = (ymax - ymin) / img_h

    return f"{x_center} {y_center} {width} {height}"
```

### Tools & Libraries
- **pycocotools**: `pip install pycocotools` for RLE/polygon conversion
- **Ultralytics convert_coco()**: Integrated COCO→YOLO converter (replaces JSON2YOLO)
- **supervision**: High-level API for multi-format conversions
- **yolo2coco** (GitHub b-niu): Requires shapely≥2.0, geos≥3.11.0

### Multi-Defect Annotation Best Practice
- Single image with multiple defects → one annotation per defect instance
- Use unique category_id for each defect type (crack=1, porosity=2, etc.)
- Ensure non-overlapping segmentations where possible
- Validate with `pycocotools.coco.COCO()` to catch malformed polygons

**References:**
- [Ultralytics JSON2YOLO → convert_coco()](https://docs.ultralytics.com/usage/simple-utilities/)
- [COCO & YOLO Formats Explained](https://towardsdatascience.com/object-detection-coco-and-yolo-formats-and-conversion-between-them-0e0638f4ffc1/)
- [GitHub: yolo2coco](https://github.com/b-niu/yolo2coco)
- [GitHub: Mask2polygon_tool](https://github.com/Mortyzhang/Mask2polygon_tool)

---

## 3. FID/LPIPS Quality Metrics for Grayscale Images

### PyTorch-FID for Grayscale
**Challenge**: FID uses Inception-v3 (expects RGB 3-channel). For grayscale X-rays:
1. **Replicate channels**: `gray_3ch = gray.repeat(3, 1, 1)` (most common)
2. **Custom encoder**: Use grayscale-trained ResNet or domain-specific feature extractor
3. **Use CleanFID**: More robust to artifacts, available in IQA-PyTorch

```python
from pytorch_fid import fid_score

# Convert grayscale to 3-channel
real_dir = "real_xrays/"  # contains .png grayscale images
fake_dir = "synthetic_xrays/"

fid_value = fid_score.calculate_fid_given_paths(
    [real_dir, fake_dir],
    batch_size=50,
    device='cuda',
    dims=2048
)
print(f"FID: {fid_value}")
```

### LPIPS for Grayscale
**Standard LPIPS**: Expects `Nx3xHxW` in range `[-1, +1]`
```python
import lpips

loss_fn = lpips.LPIPS(net='alex')  # or 'vgg'

# Replicate grayscale to 3-channel
gray1_3ch = gray1.repeat(1, 3, 1, 1)  # shape: (1, 3, H, W)
gray2_3ch = gray2.repeat(1, 3, 1, 1)

d = loss_fn(gray1_3ch, gray2_3ch)
print(f"LPIPS distance: {d.item()}")
```

### Threshold Values (Industrial X-ray Domain)
- **FID**: <50 acceptable, <20 good quality (no established X-ray standard found)
- **LPIPS**: <0.10 visually safe, aim for <0.05 for industrial inspection
- **SSIM**: ≥0.95 (recommended baseline alongside LPIPS)
- **Alternative**: KID (Kernel Inception Distance) more robust to small sample sizes

### Recommended Pipeline
```python
from IQA_pytorch import LPIPS, FID

# Multi-metric validation
lpips_metric = LPIPS(net='alex')
fid_metric = FID()

for syn_img, real_img in zip(synthetic_batch, real_batch):
    lpips_score = lpips_metric(syn_img, real_img)
    if lpips_score > 0.10:
        reject_image(syn_img)  # Automated filtering
```

**References:**
- [IQA-PyTorch: Multi-metric Toolbox (2025)](https://github.com/chaofengc/IQA-PyTorch)
- [LPIPS Practical Guide 2025](https://unifiedimagetools.com/en/articles/ai-image-quality-metrics-lpips-ssim-2025)
- [PyTorch-FID](https://github.com/mseitzer/pytorch-fid)
- [PyTorch Image Quality Metrics Review](https://ar5iv.labs.arxiv.org/html/2208.14818)

---

## 4. Downstream Validation Strategy

### Optimal Synthetic-to-Real Ratio
**Current literature**: 30-50% synthetic data mixed with real data
- **YOLOv8-WD (2025)**: 3000 real defect images → 5200 after augmentation (73% boost)
- **Weld Ultrasonic Study (2025)**: GAN/DDPM augmentation addressed data scarcity, no fixed ratio reported
- **Best practice**: Start 20% synthetic, incrementally increase to 50% while monitoring mAP

### Training Protocol
```python
# Dataset split: train:val:test = 7:2:1 or 10:1:1
total_images = real_images + synthetic_images
train_split = 0.7
val_split = 0.2
test_split = 0.1

# YOLOv8 training config
model = YOLO('yolov8n.pt')
results = model.train(
    data='weld_defects.yaml',
    epochs=300,
    batch=16,
    imgsz=640,
    device=0
)
```

### Evaluation Metrics
- **mAP@50**: Primary metric (target: >95% for industrial deployment)
- **mAP@50-95**: Stricter localization (target: >75%)
- **mIoU**: Segmentation quality (target: >0.80)
- **Precision/Recall**: Balance FP vs FN based on cost (missed defect > false alarm)

### Cross-Validation Protocol
1. **Baseline**: Train on 100% real data → establish mAP baseline
2. **Incremental synthetic mixing**:
   - 10% synthetic → measure mAP delta
   - 20% synthetic → measure mAP delta
   - 30% synthetic → measure mAP delta
3. **Threshold**: If mAP drops >3%, reduce synthetic ratio or improve generation quality
4. **Domain gap test**: Evaluate on held-out real test set (never seen during training)

### Reported Performance (2025 Studies)
- **YOLOv8 automated weld detection**: 95% accuracy
- **Improved YOLOv8**: mAP@50 = 97.2% (+17.1% over baseline)
- **SLF-YOLO (metal defects)**: mAP = 80.0% (vs YOLOv8 75.9%)
- **Synthetic augmentation (ultrasonic)**: Matched or outperformed 100% real data in niche settings

### Validation Best Practices (2025 Industry Standards)
- **SME-in-the-loop**: Quality inspectors flag unrealistic synthetic defects during generation
- **Periodic revalidation**: Test on new batches/environments every 3 months
- **Active learning**: Retrain on misclassified real samples to close domain gap
- **Human-in-the-loop**: 72% of manufacturers use AI vision with 97-99% detection accuracy

**References:**
- [YOLOv8-WD: Deep Learning Brake Joint Weld Defects (2025)](https://www.mdpi.com/2076-3417/15/3/1184)
- [Automated Weld Defect Detection YOLOv8 (2025)](https://www.tandfonline.com/doi/full/10.1080/09507116.2025.2516827)
- [Data Enhanced YOLOv8s for X-ray Weld Defects (2025)](https://www.tandfonline.com/doi/full/10.1080/10589759.2024.2421941?af=R)
- [Synthetic Data in Industrial Ultrasonic Inspection (2025)](https://www.mdpi.com/2076-3417/15/23/12811)
- [Generating Realistic 3D Surface Defects (2025)](https://link.springer.com/article/10.1007/s00170-025-16851-7)
- [GenAI & Synthetic Data in Manufacturing (2025)](https://www.dataspan.ai/blog/automated-defect-detection-how-genai-and-synthetic-data-are-transforming-visual-inspection-in-manufacturing)

---

## Unresolved Questions

1. **Grayscale FID normalization**: No consensus on domain-specific FID thresholds for industrial X-rays vs natural images. Need empirical calibration.
2. **Synthetic ratio upper bound**: Literature stops at 50% synthetic—does 70-80% synthetic work if generation quality is high (FID<20, LPIPS<0.05)?
3. **Multi-defect mask overlap handling**: How to handle annotations when slag inclusion overlaps porosity in same region? COCO iscrowd flag or separate instances?
4. **Real-time FID computation**: FID requires statistical convergence (~10k images). Can we use LPIPS pairwise for online filtering during batch generation?
5. **Domain adaptation for FID encoder**: Should we fine-tune Inception-v3 on real weld X-rays before computing FID, or use off-the-shelf?
