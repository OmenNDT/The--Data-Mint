# Weld X-Ray Datasets — Quick Reference for Data Mint

## 3 Recommended Open-Source Datasets

### 1. GDXray W0003 (Weld Series)
- **Size:** 153 images | **Format:** 512-1K px 8-bit PNG + XML
- **Defects:** 5 classes (crack, porosity, LOF, incomplete penetration, artifact)
- **Download:** `git clone https://github.com/computervision-xray-testing/GDXray.git`
- **Best for:** Validation baseline (ISO 17636-1 certified by BAM)
- **Fit:** ⭐⭐⭐ (3/5) — too small for training, perfect for SSIM validation
- **Effort:** 5 min to download

### 2. RIAWELC
- **Size:** 24,407 images | **Format:** 224×224 px PNG, class-labeled folders
- **Defects:** 4 classes (Lack of Penetration, Porosity, Cracks, No Defect)
- **Download:** `git clone https://github.com/stefyste/RIAWELC.git`
- **Best for:** Large-scale classification baseline, pretraining feature extractors
- **Fit:** ⭐⭐⭐⭐ (4/5) — plenty of data, but no bounding boxes + low resolution
- **Effort:** 10 min to download

### 3. SWRD (Seam Weld Radiographic Dataset)
- **Size:** 3,600+ images | **Format:** 16-bit PNG up to 3600×3600, polygon segmentation masks
- **Defects:** ≥5 classes (specific classes undisclosed, need to contact authors)
- **Download:** ⚠️ GitHub repo not yet publicly visible — need to contact paper authors
- **Best for:** Instance segmentation, YOLOv8 Seg fine-tuning (after polygon→mask conversion)
- **Fit:** ⭐⭐⭐⭐⭐ (5/5) — ideal resolution + annotation detail IF accessible
- **Effort:** TBD (depends on author response)
- **Paper:** [Springer 2025](https://link.springer.com/article/10.1007/s10921-025-01186-w)

---

## Coverage vs. Data Mint Target

| Defect Class | GDXray | RIAWELC | SWRD | Data Mint (10 target) |
|---|---|---|---|---|
| Crack | ✅ | ✅ | ? | ✅ |
| Porosity | ✅ | ✅ | ? | ✅ |
| Inclusion | ❌ | ❌ | ? | ✅ |
| Lack of Fusion | ✅ | ❌ | ? | ✅ |
| Undercut | ❌ | ❌ | ? | ✅ |
| Lack of Penetration | ✅ | ✅ | ? | ✅ |
| Clustered Porosity | ❌ | ❌ | ? | ✅ |
| Slag Inclusion | ❌ | ❌ | ? | ✅ |
| Linear Porosity | ❌ | ❌ | ? | ✅ |
| Elongated Cavity | ❌ | ❌ | ? | ✅ |

**Insight:** No single public dataset covers all 10 ISO 6520 classes Sơn needs. **Data Mint differentiates here.**

---

## Recommended Hybrid Strategy

```
Sơn's Validation Pipeline
│
├─ GDXray W0003 (153) ─→ SSIM/Inception baseline
├─ RIAWELC (24.4K) ─→ Class distribution + pretrain CNN
└─ SWRD (3.6K+) ─→ Fine-tune YOLOv8 Seg (if accessible)
                ↓
        Data Mint Synthetic (20K-100K)
                ↓
        Hybrid Training: Real + Synthetic
                ↓
        Publish benchmark on HuggingFace
```

---

## Action Items (Priority)

### Week 1 (Immediate)
- [ ] Clone GDXray + RIAWELC
- [ ] Convert annotations to YOLO format
- [ ] Analyze RIAWELC class distribution

### Week 2 (Follow-up)
- [ ] Benchmark Data Mint synthetic SSIM vs. GDXray baseline
- [ ] Email SWRD authors requesting dataset access
- [ ] Create `/docs/dataset-validation.md` summary

### Week 3+ (If SWRD available)
- [ ] Convert SWRD polygons → YOLOv8 segmentation masks
- [ ] Test hybrid training pipeline

---

## Full Research Report

Detailed analysis saved: `/home/sontn/Projects/The Data Mint/plans/reports/researcher-260312-1000-weld-xray-datasets.md`

Covers:
- Download commands
- Hardware feasibility checks (RTX 3090)
- Annotation format conversion guidance
- Unresolved questions + follow-up actions

