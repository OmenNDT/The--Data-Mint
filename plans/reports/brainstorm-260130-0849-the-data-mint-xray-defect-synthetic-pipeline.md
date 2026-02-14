# The Data Mint - Brainstorm Report

## Problem Statement

Build a **"Data Mint"** - automated synthetic data factory using Diffusion Models to generate realistic weld defect X-ray radiographic images. Goal: augment training data (20K-100K images) for defect detection models, producing both bounding box and segmentation mask annotations.

**Hardware:** Dual Xeon E5-2696v4 + RTX 3090 (24GB) + 64GB ECC LRDIMM
**Source Dataset:** BAM (Bundesanstalt fur Materialforschung) X-ray weld dataset (GDXray)
**Defect Types:** All NDT standard types (crack, porosity, lack of fusion/penetration, slag inclusion)

---

## Hardware Analysis

### Strengths
| Component | Spec | Advantage |
|---|---|---|
| RTX 3090 | 24GB VRAM, 10496 CUDA cores | Enough for SD 1.5 LoRA training + batch inference |
| Dual Xeon 2696v4 | 2x22 cores = 44 cores/88 threads | Parallel data preprocessing, captioning, batch management |
| 64GB ECC RAM | LRDIMM | Large dataset in-memory, stable long-running jobs |

### Constraints & Mitigations
| Constraint | Impact | Mitigation |
|---|---|---|
| PCIe 3.0 only (Broadwell) | ~16 GB/s vs 32 GB/s PCIe 4.0 | Single GPU training = minimal impact. Data stays on GPU during training/inference |
| Single RTX 3090 | Can't parallelize across GPUs | SD 1.5 is lightweight enough; use CPU cores for pre/post-processing pipeline |
| 350W GPU TDP | Thermal during 24/7 operation | Monitor GPU temp, set power limit to 300W if needed, ensure case airflow |
| No NVLink | Can't pool VRAM | Not needed - SD 1.5 uses ~4-6GB inference, ~12-16GB LoRA training |

### VRAM Budget (SD 1.5)
```
LoRA Training:    ~12-16GB (with gradient checkpointing)
Inference:        ~4-6GB base + ~2GB ControlNet + ~1GB LoRA = ~7-9GB
Batch inference:  Still fits in 24GB with batch_size=2-4
Remaining:        ~15-17GB during inference = comfortable headroom
```

**Verdict:** Hardware is well-suited for SD 1.5 pipeline. Dual Xeon excels at parallel preprocessing tasks.

---

## Evaluated Approaches

### Approach A: LoRA Fine-tuning + ControlNet Inpainting (RECOMMENDED)

**Architecture:**
```
[BAM Dataset] → [Preprocess/Crop] → [Train LoRA on SD 1.5]
                                          ↓
[Clean X-ray Background] → [ControlNet Canny/Depth] → [Inpaint Defects] → [Synthetic Image + Mask]
```

**Pipeline Steps:**
1. **Data Prep**: Crop BAM images into 512x512 patches with defect labels
2. **LoRA Training**: Fine-tune SD 1.5 to understand X-ray texture/style per defect type
3. **ControlNet**: Use Canny edge or custom-trained ControlNet for spatial control
4. **Inpainting**: Place defects into clean weld backgrounds at controlled locations
5. **Blending**: Post-process edges for seamless integration
6. **Auto-annotate**: Mask from inpainting region = ground truth annotation

**Pros:**
- ControlNet gives precise spatial control over defect placement → auto-generates bounding box + mask
- LoRA captures X-ray-specific texture and defect morphology
- Inpainting naturally blends defects into background → realistic output
- Low VRAM usage → high throughput batch processing
- Academic precedent: SD+LoRA+ControlNet achieves highest classification accuracy for industrial defects

**Cons:**
- Need to train separate LoRA per defect type (or multi-concept LoRA)
- ControlNet conditioning requires careful selection (Canny vs custom)
- Quality depends heavily on prompt engineering and training quality

---

### Approach B: DefectFill-style Few-shot Inpainting

**Architecture:**
```
[Few Reference Defects] → [Fine-tune Inpainting SD] → [Generate Defects on Clean Backgrounds]
```

Based on DefectFill (arXiv 2503.13985): custom loss functions (defect loss + object loss + attention loss) for precise defect generation with few reference images.

**Pros:**
- Works with very few reference defect images
- Custom loss functions optimize for defect-specific features
- State-of-the-art approach (March 2025)

**Cons:**
- Requires custom training code beyond ComfyUI
- More complex implementation, not beginner-friendly
- Research code may not be production-ready

---

### Approach C: DCGAN/cGAN Augmentation (Traditional)

**Architecture:**
```
[BAM Defect Crops] → [Train GAN] → [Generate Defect Variants] → [Paste into Background]
```

**Pros:**
- Well-established in literature (BAM dataset + DCGAN = 587→7631 images)
- Simpler architecture than diffusion models

**Cons:**
- Lower quality than diffusion models
- Mode collapse risk
- Less control over defect placement/variation
- No native mask generation

---

## Recommended Solution: Approach A

### Rationale
1. **Beginner-friendly**: ComfyUI visual workflow, no custom training code
2. **Best quality**: SD+LoRA+ControlNet proven highest accuracy in industrial defect literature
3. **Auto-annotation**: Inpainting mask = segmentation ground truth = free bounding box
4. **Hardware optimal**: SD 1.5 + LoRA = ~7-9GB inference → batch processing feasible
5. **Scalable to 100K**: ComfyUI API + batch queue supports automated pipeline

---

## Detailed Pipeline Design

### Phase 1: Data Preparation

```
BAM Dataset (68 radiographs, 500x5000px, 630 DPI)
    ↓
[Crop] → 512x512 patches with overlap
    ↓
[Label] → Categorize: crack, porosity, lack_of_fusion, lack_of_penetration, slag_inclusion, clean
    ↓
[Split] → Training set (LoRA): defect patches
         → Background set: clean weld patches (for inpainting targets)
```

**Multi-resolution strategy:**
- Primary: 512x512 (native SD 1.5)
- Secondary: 768x768 (SD 1.5 supports with slight quality variation)
- Post-process: Resize/crop to target resolution as needed

**CPU utilization (Dual Xeon):**
- Python multiprocessing for parallel crop/resize
- CLAHE/histogram equalization for contrast normalization
- 44 cores handles preprocessing of entire dataset rapidly

### Phase 2: LoRA Training (per defect type)

**ComfyUI Workflow: Realtime-Lora node**

```
Training Config (SD 1.5):
├── Base: sd-v1-5-pruned-noema-fp16
├── LoRA rank: 32-64 (start 32, increase if quality insufficient)
├── Learning rate: 1e-4 (LoRA default)
├── Epochs: 50-100 (small dataset → more epochs)
├── Resolution: 512x512
├── Batch size: 4 (fits in 24GB with gradient checkpointing)
├── Mixed precision: fp16
├── Optimizer: AdamW8bit
├── Gradient checkpointing: ON
├── Cache latents to disk: ON
└── Train UNet only: YES (X-ray has no text-style variance)
```

**LoRA Strategy:**
- **Option 1 (Recommended start):** 1 LoRA per defect type (5 LoRAs)
  - crack_lora, porosity_lora, fusion_lora, penetration_lora, slag_lora
  - Clear separation, easy to control
- **Option 2 (Advanced):** Multi-concept LoRA with trigger words
  - Single LoRA, prompt-based defect selection
  - Harder to train but more flexible

**Estimated training per LoRA on RTX 3090:**
- ~50-100 images per defect type
- SD 1.5 LoRA trains fast (minutes per epoch)

### Phase 3: ControlNet Setup

**Required ControlNet models:**
1. **Canny Edge** (`control_v11p_sd15_canny`): Control defect shape/outline
2. **Inpainting** (`control_v11p_sd15_inpaint`): Mask-based defect placement
3. **(Optional) Custom ControlNet**: Train on defect mask → defect image pairs

**ComfyUI Workflow:**
```
[Clean Background Image]
    ↓
[Generate Random Mask] → defines WHERE defect appears
    ↓
[ControlNet Canny] → defines defect SHAPE reference
    ↓
[SD 1.5 + LoRA] → generates defect with X-ray texture
    ↓
[Inpaint/Blend] → seamless integration
    ↓
[Output: Image + Mask + BBox]
```

### Phase 4: Inpainting & Blending Pipeline

**Core ComfyUI Nodes:**
- `KSampler` with inpainting model
- `ControlNetApply` for spatial guidance
- `LoraLoader` for defect-specific style
- `ImageCompositeMasked` for blending
- `MaskToImage` → export segmentation mask
- Custom script node → compute bounding box from mask

**Blending techniques:**
1. **Feathered mask**: Gaussian blur on mask edges before compositing
2. **Denoise strength**: 0.6-0.8 for inpainting (enough variation, maintains background)
3. **Multi-pass**: First pass generates defect, second pass refines edges

### Phase 5: Batch Production ("The Data Mint")

**Architecture for 20K-100K scale:**
```
┌─────────────────────────────────────────────────┐
│              THE DATA MINT                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  [Config YAML]                                   │
│      ├── defect_distribution: {                  │
│      │     crack: 25%,                           │
│      │     porosity: 25%,                        │
│      │     lack_fusion: 20%,                     │
│      │     lack_penetration: 15%,                │
│      │     slag: 15%                             │
│      │   }                                       │
│      ├── total_images: 50000                     │
│      ├── resolutions: [512, 768]                 │
│      └── output_format: COCO + YOLO             │
│                                                  │
│  [Batch Queue Manager] (Python, runs on CPU)     │
│      ├── Generate random masks                   │
│      ├── Select background images                │
│      ├── Queue ComfyUI API calls                 │
│      └── Track progress                          │
│                                                  │
│  [ComfyUI Server] (GPU)                          │
│      ├── REST API endpoint                       │
│      ├── Process queue                           │
│      └── Output: image + mask + metadata         │
│                                                  │
│  [Post-processor] (CPU, multiprocessing)         │
│      ├── Convert mask → BBox (YOLO format)       │
│      ├── Convert mask → COCO polygon             │
│      ├── Quality filter (FID/LPIPS check)        │
│      ├── Resize for multi-resolution             │
│      └── Organize output directory               │
│                                                  │
│  [Output]                                        │
│      └── dataset/                                │
│          ├── images/                             │
│          ├── masks/                              │
│          ├── annotations/                        │
│          │   ├── coco.json                       │
│          │   └── yolo/                           │
│          └── metadata.csv                        │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Throughput estimate (SD 1.5 on RTX 3090):**
- ~2-4 seconds per image (512x512, 20 steps)
- ~900-1800 images/hour
- ~20K images: ~11-22 hours
- ~100K images: ~55-111 hours (2.3-4.6 days)

**CPU parallel tasks (Dual Xeon 44 cores):**
- Mask generation: async, ahead of GPU queue
- Post-processing: parallel with GPU generation
- Quality filtering: background process
- COCO/YOLO annotation conversion: batch after generation

### Phase 6: Quality Assurance

**Automated QA pipeline:**
1. **FID Score**: Compare synthetic vs real BAM distribution
2. **LPIPS**: Perceptual similarity check
3. **Defect coverage**: Verify all defect types adequately represented
4. **Manual spot-check**: Random sample review (recommended 1-2% of output)
5. **Downstream validation**: Train defect detection model, compare performance real-only vs augmented

---

## Implementation Roadmap

| Phase | Description | Dependencies |
|---|---|---|
| 1 | Install ComfyUI + extensions + ControlNet models | Hardware ready |
| 2 | Preprocess BAM dataset → 512x512 patches + labels | BAM dataset access |
| 3 | Train LoRA per defect type (start with crack + porosity) | Phase 1,2 |
| 4 | Build ComfyUI inpainting workflow with ControlNet | Phase 1,3 |
| 5 | Test single-image generation quality | Phase 4 |
| 6 | Build batch queue manager (Python + ComfyUI API) | Phase 5 validated |
| 7 | Build post-processor (mask→BBox, COCO/YOLO export) | Phase 6 |
| 8 | Full production run + QA | Phase 6,7 |
| 9 | Downstream model training + A/B validation | Phase 8 |

---

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| LoRA doesn't capture X-ray texture well | High | Medium | Increase training data, try rank 64-128, add text encoder training |
| Generated defects look unrealistic | High | Medium | Increase denoise strength, refine prompts, add negative prompts for artifacts |
| Thermal throttling during 24/7 runs | Medium | Medium | Power limit 300W, monitor temps, add cooling breaks in batch script |
| PCIe 3.0 bottleneck | Low | Low | SD 1.5 fits entirely in VRAM, minimal CPU↔GPU transfer |
| Annotation quality (mask accuracy) | Medium | Low | Inpainting mask IS the ground truth; validate edge precision |
| Dataset bias | High | Medium | Ensure balanced defect distribution, vary background diversity |

---

## Key Technical Decisions

1. **SD 1.5 over SDXL/FLUX**: X-ray is grayscale, 512x512 sufficient. VRAM headroom enables batch processing. ControlNet ecosystem is most mature.

2. **Separate LoRA per defect type**: Clearer control, easier debugging, can adjust per-defect quality independently. Multi-concept LoRA can be explored later.

3. **ControlNet Inpainting over img2img**: Inpainting gives precise spatial control AND automatic mask annotation. img2img would require separate annotation step.

4. **ComfyUI over code-only pipeline**: Visual workflow debugging critical for beginners. API mode enables batch automation. Best of both worlds.

5. **COCO + YOLO dual format**: Maximum downstream compatibility. COCO for segmentation models, YOLO for detection models.

---

## Required Software Stack

| Component | Tool | Purpose |
|---|---|---|
| Diffusion UI | ComfyUI (latest) | Visual workflow + API server |
| LoRA Training | comfyUI-Realtime-Lora or kohya-ss | Fine-tune SD 1.5 |
| Base Model | sd-v1-5-pruned-noema-fp16 | Stable Diffusion 1.5 |
| ControlNet | control_v11p_sd15_canny + inpaint | Spatial control |
| Batch Manager | Python (custom script) | Queue management |
| Post-processor | Python + OpenCV + pycocotools | Annotation export |
| QA | pytorch-fid, lpips | Quality metrics |
| Monitoring | TensorBoard or simple logging | Training + generation monitoring |

---

## References

- [Synthetic Data Augmentation with GANs for Weld Defects](https://www.tandfonline.com/doi/full/10.1080/09507116.2025.2539827)
- [Lightweight DCGAN for X-ray Welding Defects](https://www.nature.com/articles/s41598-025-89558-0)
- [Automated Categorization of Multiclass Welding Defects using X-ray Augmentation](https://www.mdpi.com/1424-8220/23/14/6422)
- [DefectFill: Realistic Defect Generation with Inpainting Diffusion Model](https://arxiv.org/html/2503.13985v1)
- [Industrial Surface Defect Image Generation Overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC10575288/)
- [Latent Diffusion Models for Steel Surface Defect Segmentation](https://www.mdpi.com/1424-8220/24/18/6016)
- [RIAWELC: Radiographic Image Dataset for Weld Defects](https://github.com/stefyste/RIAWELC)
- [ComfyUI Realtime-Lora Extension](https://github.com/shootthesound/comfyUI-Realtime-Lora)
- [LoRA Training 2025 Guide](https://sanj.dev/post/lora-training-2025-ultimate-guide)
- [ComfyUI VRAM Optimization Guide](https://apatero.com/blog/vram-optimization-flags-comfyui-explained-guide-2025)
- [RTX 3090 Deep Learning Hardware Analysis](https://lambda.ai/blog/deep-learning-hardware-deep-dive-rtx-30xx)
- [Puget Systems LoRA Training GPU Analysis](https://www.pugetsystems.com/labs/articles/stable-diffusion-lora-training-consumer-gpu-analysis/)
