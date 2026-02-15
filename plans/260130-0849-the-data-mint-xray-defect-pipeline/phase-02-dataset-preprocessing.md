# Phase 02: Dataset Preprocessing

## Context Links
- [Plan Overview](plan.md)
- [Research: GDXray/BAM Dataset](research/researcher-01-comfyui-lora-controlnet.md#4-gdxraybam-dataset-structure)
- [Brainstorm: Data Prep](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: complete
- **Effort**: 4h
- **Description**: Download GDXray W0003 series, crop 512x512 patches with overlap, classify defect/clean regions, create caption files with trigger words, apply CLAHE normalization.

## Key Insights
- W0003 series: 67 images (RRT01: 31, RRT02: 36), TIFF format, annotated
- Images are large (~500x5000px, 630 DPI) - must crop to 512x512 for SD 1.5
- Dual Xeon 44 cores enables parallel preprocessing
- CLAHE normalizes contrast across varying exposure levels
- Need separate sets: defect patches (LoRA training) + clean patches (inpainting backgrounds)

## Requirements

### Functional
- 512x512 patches extracted with 50% overlap
- Each patch classified: defect type or clean
- Caption .txt file per image with defect-specific trigger word
- CLAHE contrast normalization applied uniformly
- Train/background split: defect patches -> LoRA training, clean patches -> inpainting targets

### Non-Functional
- Multiprocessing for patch extraction (use 44 CPU cores)
- Consistent naming convention for patches
- Reproducible pipeline (save random seeds, config)

## Architecture

```
dataset/
├── raw/                        # Downloaded GDXray
│   └── Welds/W0003/
│       ├── RRT01/              # 31 TIFF images
│       └── RRT02/              # 36 TIFF images
├── processed/
│   ├── patches_512/            # All 512x512 crops
│   │   ├── crack/              # Defect-type subdirs
│   │   │   ├── crack_0001.png
│   │   │   └── crack_0001.txt  # Caption file
│   │   ├── porosity/
│   │   ├── lack_of_fusion/
│   │   ├── lack_of_penetration/
│   │   ├── slag_inclusion/
│   │   └── clean/              # Background patches
│   ├── annotations/            # Original bbox annotations
│   └── metadata.csv            # Patch source, coords, label
└── scripts/
    └── preprocess-gdxray.py
```

## Related Code Files
- Create: `dataset/scripts/preprocess-gdxray.py`

## Implementation Steps

1. **Download GDXray Dataset**
   ```python
   # Clone from GitHub
   git clone https://github.com/computervision-xray-testing/GDXray.git
   # Or download W0003 ZIPs directly
   ```

2. **Parse Existing Annotations**
   - Read bounding box annotation files from W0003
   - Map bbox coords to defect categories
   - Build annotation index: {image_id: [{bbox, defect_type}]}

3. **CLAHE Normalization**
   ```python
   clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
   normalized = clahe.apply(grayscale_img)
   ```
   - Apply before cropping for consistent local contrast

4. **Crop 512x512 Patches**
   - Sliding window: stride 256 (50% overlap)
   - For each patch, check intersection with defect bboxes
   - Classify: if IoU > 0.3 with any defect bbox -> defect type, else -> clean
   - Use `multiprocessing.Pool(44)` for parallel extraction

5. **Create Caption Files**
   - One `.txt` per image, same basename
   - Trigger word format per defect type:
     ```
     crack:              "xray_crack, weld crack defect, radiographic image"
     porosity:           "xray_porosity, weld porosity defect, radiographic image"
     lack_of_fusion:     "xray_lof, lack of fusion defect, radiographic image"
     lack_of_penetration:"xray_lop, lack of penetration defect, radiographic image"
     slag_inclusion:     "xray_slag, slag inclusion defect, radiographic image"
     ```
   - Trigger word prefix (`xray_crack`, etc.) enables LoRA activation during inference

6. **Generate Metadata CSV**
   ```csv
   patch_id,source_image,x,y,width,height,label,defect_subtype
   crack_0001,W0003_RRT01_001.tiff,512,1024,512,512,defect,crack
   clean_0042,W0003_RRT01_001.tiff,0,0,512,512,clean,none
   ```

7. **Quality Check**
   - Verify patch count per defect type (expect imbalance -> note for Phase 3 regularization)
   - Visual spot-check 10 patches per category
   - Verify caption files match image files 1:1

## Todo List
- [x] Download GDXray Welds (478MB zip, Dropbox)
- [x] Extract W0003 (68 PNGs, ~5000x1250px grayscale, 630 DPI)
- [x] Parse real-values.xls (NOT ground_truth.txt — W0003 uses Excel with ISO 6520 codes)
- [x] Map ROC film numbers to W0003_NNNN.png via readme (67 mapped)
- [x] Enumerate defect types: 5 groups (porosity:123, crack:21, inclusion:21, lack_of_fusion:20, undercut:16)
- [x] Implement CLAHE normalization
- [x] Implement sliding window cropper (512x512, stride 256, 50% overlap)
- [x] Classify patches by x-range overlap with defect positions (20% threshold)
- [x] Create caption .txt files with trigger words per defect group
- [x] Generate metadata.csv (4731 rows)
- [x] Run multiprocessing extraction on all 68 images (8 workers)
- [x] Verify: 4731 PNG = 4731 TXT (PASS)
- [ ] Visual spot-check (user manual task)

## Results
| Group | Patches | % of Total |
|-------|---------|-----------|
| clean | 3524 | 74.5% |
| porosity | 510 | 10.8% |
| lack_of_fusion | 269 | 5.7% |
| crack | 228 | 4.8% |
| inclusion | 114 | 2.4% |
| undercut | 86 | 1.8% |
| **Total** | **4731** | **100%** |

**Disk usage:** 708MB output | **Script:** `dataset/scripts/preprocess-gdxray-w0003-patches.py`

## Success Criteria
- All 67 W0003 images processed
- 512x512 patches in defect-type subdirectories
- Each defect patch has matching .txt caption with trigger word
- Clean background patches separated for inpainting use
- metadata.csv with full provenance tracking
- CLAHE applied uniformly

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| Too few defect patches per type | High | Supplement with W0001/W0002 series or augment (flip/rotate) |
| Annotation format inconsistency | Medium | Manually verify bbox parsing against visual inspection |
| TIFF compatibility issues | Low | PIL/tifffile handles TIFF; convert to PNG after crop |

## Security Considerations
- GDXray license: free for research/educational use only
- No PII in dataset
- Verify downloaded files match expected checksums

## Next Steps
- Phase 3: Feed defect patches + captions into LoRA training
- Phase 5: Use clean patches as inpainting backgrounds
