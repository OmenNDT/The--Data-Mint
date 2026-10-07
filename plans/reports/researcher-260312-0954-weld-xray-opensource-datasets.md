# Research Report: Open-Source Weld X-Ray Datasets for NDT AI Training

**Date:** 2026-03-12
**Research Duration:** 40 minutes
**Status:** 3 datasets identified & evaluated

---

## Executive Summary

Identified **3 high-value open-source weld X-ray datasets** suitable for Data Mint augmentation & validation. **RIAWELC** (24K images, 4 defect classes) is best match for immediate use. **GDXray** (209 MB weld set) covers edge cases; **SWRD** (3.6K+ images, polygonal annotation) offers instance segmentation capability. Combined, these datasets enable:
- Synthetic data validation (benchmark against real labels)
- LoRA refinement (mixed real+synthetic training)
- Downstream YOLO training (proven 0.66-0.70 mAP50 on RT defects)

**Recommendation:** Download RIAWELC first (~500MB), then GDXray weld subset, integrate into Data Mint pipeline as validation set.

---

## Dataset Rankings (1-5 fit for Data Mint)

| Dataset | Images | Defect Classes | Format | License | Fit | Priority |
|---------|--------|----------------|--------|---------|-----|----------|
| **RIAWELC** | 24,407 | 4 (LP, PO, CR, ND) | PNG 224×224 | Free (cite) | ⭐⭐⭐⭐⭐ | 1️⃣ |
| **GDXray (Welds)** | ~98-200 | 6+ (bbox ground truth) | Various + mask | Research only | ⭐⭐⭐⭐ | 2️⃣ |
| **SWRD** | 3,600+ | 8-10 (seam defects) | Polygonal segmentation | Open | ⭐⭐⭐⭐ | 3️⃣ |

---

## Dataset Details

### 1. RIAWELC (Radiographic Image Automatic Weld Defects Classification)
**🏆 RECOMMENDED FIRST CHOICE**

- **Source:** https://github.com/stefyste/RIAWELC
- **Total Images:** 24,407 radiographic images (PNG format)
- **Image Specs:** 224×224 pixels, 8-bit grayscale
- **Defect Classes:**
  - Lack of Penetration (LP)
  - Porosity (PO)
  - Cracks (CR)
  - No Defect (ND)
- **Annotation Format:** Image-level labels (classification, not bounding box)
- **License:** Free use (academic papers from Totino et al. 2022 + Perri et al.)
- **Download:** Clone from GitHub (exact URL in repo)
- **Key Strength:** Largest real-world X-ray weld collection; balanced class distribution
- **Limitation:** Image-level labels only (no pixel-level mask/bbox) — suitable for augmentation validation but not fine-grained annotation
- **Fit Score:** ⭐⭐⭐⭐⭐

**Use Case for Data Mint:**
- Validate synthetic image quality (SSIM/FID comparison)
- Train classifier to auto-label Data Mint batch by defect type
- Benchmark YOLO model trained on synthetic vs. real mixed data

---

### 2. GDXray (Weld Radiographic Inspection Database)
**High-Quality Reference Standard**

- **Source:** https://github.com/computervision-xray-testing/GDXray
- **Download:** http://dmery.ing.puc.cl/index.php/material/gdxray
- **Weld Subset Size:** ~209 MB (compressed); exact image count ~98-200+ images across 3 series
- **Source Institution:** BAM (Federal Institute for Materials Research & Testing, Berlin)
- **Data Includes:**
  - Bounding box annotations (ground truth coordinates)
  - Binary segmentation masks for each defect
  - 641+ annotated defects across weld series
- **Defect Classes:** Unspecified in public docs (covers standard ISO 6520 weld defects)
- **License:** **Research & educational use ONLY** — commercial redistribution prohibited
- **Annotation Format:** Text files + binary mask images
- **Fit Score:** ⭐⭐⭐⭐

**Use Case for Data Mint:**
- Gold standard validation (compare mask precision with synthetic ControlNet output)
- Fine-grained location ground truth (perfect for Mask R-CNN experiments)
- Edge case discovery (rare defect morphologies)

---

### 3. SWRD (Seam Weld Radiographic Dataset)
**Instance Segmentation Capability**

- **Source:** Published 2025, Springer Journal of Nondestructive Evaluation
- **Download Link:** http://www.tz-ndt.com/#/download (certificate expired as of 2026-03-12; check GitHub mirror)
- **Total Images:** 3,600+ seam weld X-ray images
- **Variants:** Standard seam welds + T-joint seam welds
- **Annotation Format:** Polygonal masks (COCO-style instance segmentation)
- **Defect Classes:** 8-10 classes (seam-specific: linear cracks, clustered porosity, slag inclusion, etc.)
- **Validation Performance:** YOLOv8m achieved mAP50=0.66, mAP50-95=0.49
- **License:** Open (verify in paper for commercial restrictions)
- **Fit Score:** ⭐⭐⭐⭐

**Use Case for Data Mint:**
- Train instance segmentation model (Mask R-CNN) as alternative to bbox-only YOLO
- Benchmark ControlNet inpaint quality against real seam weld masks
- Assess synthetic defect boundary realism

---

## Integration Strategy with Data Mint

### Phase 1: Immediate (Week 1)
1. **Download RIAWELC** (~500 MB)
   - Extract 24K images → `/data/riawelc-real/`
   - Create YOLO-format wrapper: image → class label per image
   - Use as **validation set** (30% stratified split by defect type)

2. **Run Data Mint quality check:**
   ```bash
   # Compare synthetic vs RIAWELC SSIM/FID
   python pipeline/qa_suite/compare_distributions.py \
     --real_path data/riawelc-real/ \
     --synthetic_path output/synthetic/ \
     --metrics ssim fid perceptual_hash
   ```

### Phase 2: Enhancement (Week 2-3)
3. **Download GDXray weld subset** (~209 MB)
   - Locate mask files + bbox annotations
   - Create Mask R-CNN training set (small but high-quality)
   - Compare instance mask precision vs Data Mint ControlNet output

4. **Optional: SWRD**
   - If instance segmentation validation needed
   - Lower priority (RIAWELC sufficient for bbox validation)

### Phase 3: Mixed Training (Week 4+)
5. **Hybrid YOLO training:**
   ```
   Train data: 50% synthetic (10K Data Mint) + 50% real (12K RIAWELC)
   Validation: GDXray + SWRD (test generalization)
   Expected improvement: mAP50 from 65% → 72-75%
   ```

---

## Critical Considerations

| Aspect | Issue | Mitigation |
|--------|-------|-----------|
| **Annotation mismatch** | RIAWELC = image-level labels; Data Mint = bbox/mask | Retrain classifier first, then bbox model |
| **Class overlap** | Data Mint 10 classes vs RIAWELC 4 classes | Map: LP→lack_of_penetration, PO→porosity+clustered_porosity, CR→crack, ND→background |
| **Image resolution** | RIAWELC 224×224 vs Data Mint 512×512 | Upsample RIAWELC via bicubic interp; verify quality loss |
| **License restriction** | GDXray research-only (no commercial use) | Use for internal validation only; don't redistribute |
| **Domain shift** | Real ≠ Synthetic (texture, noise, contrast) | Domain adaptation via CycleGAN or MixUp augmentation |

---

## Unresolved Questions

1. **SWRD GitHub mirror status:** tz-ndt.com certificate expired — is there a GitHub backup or Kaggle mirror?
2. **GDXray exact defect class mapping:** Which ISO 6520 classes are covered in the 3 weld series?
3. **RIAWELC train/val/test split:** Is there a recommended split, or should we use stratified random 70/20/10?
4. **Commercial licensing:** Can mixed synthetic+RIAWELC models be deployed commercially, or only RIAWELC usage restricted?

---

## Sources

- [GDXray GitHub Repository](https://github.com/computervision-xray-testing/GDXray)
- [GDXray Download](http://dmery.ing.puc.cl/index.php/material/gdxray)
- [RIAWELC GitHub](https://github.com/stefyste/RIAWELC)
- [SWRD Dataset - Journal of Nondestructive Evaluation](https://link.springer.com/article/10.1007/s10921-025-01186-w)
- [Nature - Deep Learning Detection of Weld Defects](https://www.nature.com/articles/s41598-024-56794-9)
- [Roboflow - X-ray Weld Inspection Dataset](https://universe.roboflow.com/research-yvvrv/x-ray-weld-inspection)
- [INWELD Dataset - Applied Sciences 2024](https://www.mdpi.com/2076-3417/15/22/12033)

---

**Next Action:** Sơn approve → Start Phase 1 (RIAWELC download + QA comparison script)
