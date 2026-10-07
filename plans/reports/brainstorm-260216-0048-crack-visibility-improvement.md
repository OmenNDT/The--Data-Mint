# Brainstorm: Crack Visibility Improvement

**Date:** 2026-02-16
**Status:** Agreed — Ready for implementation

---

## Problem Statement

Generated X-ray images show no visible crack defect despite mask clearly showing crack line. Masks and generated images don't visually correlate — crack is invisible in output.

## Root Cause Analysis

### 1. Mask too thin (PRIMARY CAUSE)
- `crack-mask-generator.py:28`: `width_range: (1, 4)` pixels
- At 512x512, 2px = 0.4% of image width
- Inpainting only regenerates masked pixels → 2px is insufficient area for visible crack

### 2. Feathered mask reduces effective coverage
- `mask-prefetch-worker-pool.py:71`: Uses feathered mask for inpainting
- `blur_radius=3` softens already thin mask further

### 3. Parameter tuning insufficient alone
- LoRA 0.85, denoise 0.92, CFG 8.5 still can't overcome 2px mask limitation
- Model physically cannot paint a visible crack within 2 pixels

## Evaluated Approaches

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| A: Dilate mask + remove ControlNet | Simplest, highest impact, natural blending | Removes ControlNet guidance | Not chosen |
| B: Dilate mask, keep ControlNet | Less disruptive, keeps ControlNet guidance | ControlNet may still constrain | **CHOSEN** |
| C: Two-pass txt2img → composite | Maximum crack visibility | Complex, texture mismatch, 2x slower | Not chosen |
| D: Parameter tuning only | Fastest to try | Won't fix 2px fundamental limit | Not chosen |

## Agreed Solution: Option B

**Dilate inpainting masks to ~15-25px. Keep ControlNet. Keep thin original masks as ground truth annotation.**

### What Changes

1. **Mask prefetch worker** (`mask-prefetch-worker-pool.py`):
   - After generating mask, apply `cv2.dilate()` with kernel ~15-25px
   - Apply feathering to dilated mask
   - Use dilated+feathered mask for ComfyUI inpainting

2. **Batch production main** (`batch-production-main.py`):
   - Upload dilated mask for inpainting
   - Save original thin mask as annotation ground truth

3. **Config** (`batch-config.yaml` or `mask-config.yaml`):
   - Add `inpaint_mask_dilation: 20` parameter
   - Configurable dilation amount per defect type

4. **ControlNet strength** — may need reducing from 0.55 since mask is now wider
   - Suggest trying 0.4-0.5 with dilated mask

### Annotation Decision
- **Ground truth label = original thin mask (1-4px)**
- Dilated mask is ONLY for inpainting guidance
- Thin mask accurately represents real defect boundary for YOLO training

## Implementation Considerations

- Dilation kernel shape: elliptical (matches crack morphology better than square)
- Feathering after dilation: `blur_radius=5-8` for smooth inpainting transition
- Need to save BOTH masks per image: thin (annotation) + dilated (inpainting debug)
- ControlNet strength may need iterative tuning after mask dilation

## Success Criteria

- Crack clearly visible in generated images at normal viewing distance
- Crack location matches mask position
- Background texture around crack looks natural (no blending artifacts)
- Thin annotation mask still accurately outlines the visible crack

## Risk Assessment

- **Low risk**: If dilation too small → crack still faint → increase dilation
- **Medium risk**: If dilation too large → crack area looks unnatural/blobby → reduce dilation
- **Mitigation**: Make dilation configurable, test with pilot batch (5-10 images) first

## Next Steps

1. Implement mask dilation in prefetch worker
2. Add dilation config parameter
3. Update batch-production-main to save both mask versions
4. Run pilot batch (10 images) to validate
5. Tune ControlNet strength if needed
6. Scale to full 100-image batch
