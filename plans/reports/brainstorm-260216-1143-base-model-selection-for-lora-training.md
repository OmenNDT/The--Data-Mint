# Brainstorm: Base Model Selection for LoRA Training

**Date**: 2026-02-16
**Status**: Agreed
**Scope**: 4 alternative SD 1.5 checkpoints to benchmark against current `sd-v1-5-pruned-emaonly.safetensors`

---

## Problem Statement

Current LoRA training uses vanilla `sd-v1-5-pruned-emaonly.safetensors` as base. This is the most generic SD 1.5 checkpoint — not optimized for X-ray/medical/industrial imagery. Want to find if domain-specific or photorealistic checkpoints produce better defect quality after LoRA fine-tuning.

**Goal**: Improve defect texture realism in generated synthetic weld X-ray images.
**Constraint**: Keep SD 1.5 architecture (reuse existing ControlNet v1.1 + workflow + 512x512 pipeline).
**Budget**: 1-2 weeks thorough testing.

---

## Agreed 4 Alternatives (+ Current Baseline)

### Baseline: sd-v1-5-pruned-emaonly.safetensors
- Vanilla SD 1.5, no domain specialization
- Currently in production, known behavior
- All existing LoRA models trained on this base

### Option 1: Osama03 Medical X-Ray Generation (SD 1.5)
- **Source**: [HuggingFace](https://huggingface.co/Osama03/Medical-X-ray-image-generation-stable-diffusion)
- **Why**: Already fine-tuned on medical X-ray dataset → understands grayscale/contrast/radiographic aesthetics
- **Drop-in**: Yes, direct checkpoint replacement
- **VAE**: Check model card (may need external)
- **Risk**: Unknown training data quality/size, less community validation
- **Expected benefit**: Better X-ray aesthetic baseline → LoRA needs less adaptation

### Option 2: Realistic Vision V5.1 (SG161222)
- **Source**: [HuggingFace](https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE) | [CivitAI](https://civitai.com/models/4201)
- **Why**: Most mature photorealistic SD 1.5 model, 160K+ downloads, production-ready inpainting variant
- **Drop-in**: Yes, but needs external VAE (`sd-vae-ft-mse`)
- **File**: `Realistic_Vision_V5.1_noVAE` (~3.95 GB) or V6.0 pruned (~1.99 GB)
- **Inpainting**: `Realistic_Vision_V5.1-inpainting.safetensors` available
- **Risk**: Photographic texture bias may interfere with X-ray domain
- **Expected benefit**: Sharper microdetail textures, proven ControlNet compatibility

### Option 3: AbsoluteReality v1.8.1 (Lykon)
- **Source**: [CivitAI](https://civitai.com/models/81458)
- **Why**: Precision-focused, optimized for simple prompts (matches technical X-ray workflow)
- **Drop-in**: Yes, needs external VAE (`sd-vae-ft-mse`)
- **File**: ~2.0 GB
- **Inpainting**: `v1.8.1-INP` variant available
- **Settings**: CFG 4.5-10, DPM++ SDE Karras, 25-30 steps
- **Risk**: Complex prompts reduce quality (CLIP bleeding) — but our prompts are simple
- **Expected benefit**: Technical precision without over-processing, good for industrial imagery

### Option 4: CyberRealistic V4.2
- **Source**: [HuggingFace](https://huggingface.co/sam749/CyberRealistic-v4-2) | [CivitAI](https://civitai.com/models/15003)
- **Why**: Built-in VAE (simplest setup), strong texture fidelity, inpainting available
- **Drop-in**: Yes, no external VAE needed
- **File**: `CyberRealistic_V4.2_FP16.safetensors` (2.13 GB)
- **Risk**: ControlNet v1.1 compatibility not explicitly documented (but should work — same SD 1.5 arch)
- **Expected benefit**: Reduced pipeline complexity, high texture detail

---

## Implementation Strategy

### Phase 1: Download & Setup (Day 1)
1. Download all 4 checkpoints + `sd-vae-ft-mse` VAE
2. Place in ComfyUI `models/checkpoints/` directory
3. Update `defect-type-prompt-templates.yaml` to support model_paths switching
4. Update `batch-config.yaml` with model selection parameter

### Phase 2: LoRA Training (Days 2-6)
For each base model:
1. Update `pretrained_model_name_or_path` in all 5 TOML configs
2. Train all 5 LoRA models (crack, porosity, inclusion, LOF, undercut)
3. Training time estimate: ~4-8 hours per defect type × 5 = 20-40 hours per base model
4. Total: 4 base models × 20-40h = 80-160 hours (~3.5-7 days sequential)
5. **Optimization**: Can run overnight, 1 base model per night

### Phase 3: Pilot Generation (Days 7-8)
For each base model + its trained LoRAs:
1. Generate 100 images per defect type (500 total per base model)
2. Use identical seeds across all models for fair comparison
3. Same ControlNet settings, same prompts, same masks

### Phase 4: Evaluation (Days 9-10)
Quantitative metrics:
- **SSIM**: Background consistency vs real GDXray images
- **FID**: Distribution distance between synthetic and real
- **Defect clarity**: Edge sharpness of generated defects (Sobel edge strength)

Qualitative:
- Visual side-by-side comparison grid (5 models × 5 defect types = 25 samples)
- Blind ranking by domain knowledge

### Phase 5: Validation (Days 11-14)
For top 2 performers:
- Generate 2,000 images each
- Train YOLOv8 on synthetic data
- Evaluate mAP on held-out real test set
- Compare against current baseline mAP

---

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | SD 1.5 only | Reuse ControlNet v1.1, workflow, pipeline. SDXL deferred to future |
| # of alternatives | 4 models | Balanced coverage: 1 medical + 3 photorealistic |
| Testing depth | Thorough (1-2 weeks) | Full train + generate + validate per model |
| Evaluation metric | mAP (primary) + visual quality | Downstream YOLO performance is ultimate judge |

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Photorealistic models hallucinate on X-ray domain | Medium | LoRA fine-tuning bridges domain gap |
| LoRA training fails on new base | Low | All models are SD 1.5 arch, same UNet |
| Medical model (Osama03) has poor quality training data | Medium | Pilot test 100 images before full commit |
| VAE mismatch causes artifacts | Low | Use `sd-vae-ft-mse` consistently; CyberRealistic has built-in |
| Time overrun (>2 weeks) | Medium | Parallelize overnight training, reduce pilot size if needed |

---

## Success Criteria

1. At least 1 alternative achieves **higher mAP** than current baseline on YOLOv8 validation
2. Generated defect textures judged **more realistic** in blind visual comparison
3. No regression in pipeline stability (generation speed, error rate)
4. Winner model documented and integrated as new default

---

## Config Changes Required

### kohya-ss configs (5 TOML files × 4 models = 20 configs)
```toml
[model_arguments]
pretrained_model_name_or_path = "/path/to/new-checkpoint.safetensors"
```

### defect-type-prompt-templates.yaml
```yaml
model_paths:
  checkpoint: "checkpoints/{selected_model}.safetensors"
  vae: "vae/sd-vae-ft-mse.safetensors"  # or null for built-in
```

### batch-config.yaml
```yaml
model:
  checkpoint: "checkpoints/{selected_model}.safetensors"
  vae: "vae/sd-vae-ft-mse.safetensors"  # optional
```

---

## Download Links Summary

| Model | Link | Size |
|-------|------|------|
| Osama03 Medical X-Ray | [HuggingFace](https://huggingface.co/Osama03/Medical-X-ray-image-generation-stable-diffusion) | TBD |
| Realistic Vision V5.1 | [HuggingFace](https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE) | ~2.0 GB (pruned) |
| AbsoluteReality v1.8.1 | [CivitAI](https://civitai.com/models/81458) | ~2.0 GB |
| CyberRealistic V4.2 | [HuggingFace](https://huggingface.co/sam749/CyberRealistic-v4-2) | 2.13 GB |
| sd-vae-ft-mse | [HuggingFace](https://huggingface.co/stabilityai/sd-vae-ft-mse-original) | ~335 MB |

---

## Next Steps

- [ ] Create detailed implementation plan (phases, TOML config generation, automation scripts)
- [ ] Download models and VAE
- [ ] Setup automated benchmark pipeline
- [ ] Execute training → generation → evaluation loop
- [ ] Document results and select winner

---

## Unresolved Questions

1. **Osama03 model quality**: Need to inspect model card and test output before committing to full training
2. **LoRA strength tuning**: May need different lora_strength per base model (current: 0.7-0.85)
3. **VAE grayscale performance**: Does `sd-vae-ft-mse` (trained on color images) introduce bias for grayscale X-ray?
4. **Sampler settings**: Current euler/normal may not be optimal for photorealistic checkpoints (they recommend DPM++ SDE Karras)

---

## References

- [Research: X-ray Diffusion Models Survey](./researcher-260216-1148-xray-diffusion-models-survey.md)
- [Research: Photorealistic SD 1.5 Checkpoints](./researcher-260216-1149-photorealistic-sd15-checkpoints-xray-weld-defects.md)
