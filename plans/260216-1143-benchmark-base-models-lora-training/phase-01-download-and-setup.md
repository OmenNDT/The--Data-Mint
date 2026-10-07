# Phase 1: Download & Setup

## Context Links
- [Plan Overview](plan.md)
- [Brainstorm](../../plans/reports/brainstorm-260216-1143-base-model-selection-for-lora-training.md)

## Overview
- **Priority**: P1 (blocking all subsequent phases)
- **Status**: complete
- **Effort**: 2h
- **Description**: Download 4 checkpoint models + external VAE, verify integrity, organize directory structure

## Key Insights
- Models 1-3 need external VAE (`sd-vae-ft-mse`); Model 4 (CyberRealistic) has built-in VAE
- Osama03 Medical X-Ray is a HuggingFace diffusers-format model -- may need conversion to single `.safetensors`
- All models ~2GB each; total download ~10GB including VAE

## Requirements

### Functional
- Download all 4 checkpoints to `models/checkpoints/benchmark/`
- Download `sd-vae-ft-mse` VAE to `models/vae/`
- Verify each file loads correctly (test checkpoint loading)
- Create model registry JSON for downstream scripts

### Non-functional
- Resumable downloads (use `huggingface-hub` or `wget -c`)
- Log download progress and file sizes
- Idempotent (skip already-downloaded files)

## Architecture

### Directory Structure
```
models/
├── checkpoints/
│   ├── sd-v1-5-pruned-emaonly.safetensors          # existing baseline
│   └── benchmark/
│       ├── medical-xray-sd15.safetensors            # Osama03
│       ├── realistic-vision-v51.safetensors          # SG161222
│       ├── absolute-reality-v181.safetensors         # Lykon/CivitAI
│       └── cyberrealistic-v42.safetensors            # sam749
├── vae/
│   └── sd-vae-ft-mse.safetensors                    # stabilityai
```

### Model Registry (`models/checkpoints/benchmark/model-registry.json`)
```json
{
  "baseline": {
    "short_name": "baseline",
    "checkpoint": "sd-v1-5-pruned-emaonly.safetensors",
    "checkpoint_path": "checkpoints/sd-v1-5-pruned-emaonly.safetensors",
    "vae": null,
    "source": "stabilityai/stable-diffusion-v1-5"
  },
  "medxray": {
    "short_name": "medxray",
    "checkpoint": "medical-xray-sd15.safetensors",
    "checkpoint_path": "checkpoints/benchmark/medical-xray-sd15.safetensors",
    "vae": "vae/sd-vae-ft-mse.safetensors",
    "source": "Osama03/Medical-X-ray-image-generation-stable-diffusion"
  },
  "realvis": {
    "short_name": "realvis",
    "checkpoint": "realistic-vision-v51.safetensors",
    "checkpoint_path": "checkpoints/benchmark/realistic-vision-v51.safetensors",
    "vae": "vae/sd-vae-ft-mse.safetensors",
    "source": "SG161222/Realistic_Vision_V5.1_noVAE"
  },
  "absreal": {
    "short_name": "absreal",
    "checkpoint": "absolute-reality-v181.safetensors",
    "checkpoint_path": "checkpoints/benchmark/absolute-reality-v181.safetensors",
    "vae": "vae/sd-vae-ft-mse.safetensors",
    "source": "civitai:81458"
  },
  "cyberreal": {
    "short_name": "cyberreal",
    "checkpoint": "cyberrealistic-v42.safetensors",
    "checkpoint_path": "checkpoints/benchmark/cyberrealistic-v42.safetensors",
    "vae": null,
    "source": "sam749/CyberRealistic-v4-2"
  }
}
```

## Related Code Files
- **Create**: `pipeline/benchmark/download-benchmark-models.py`
- **Create**: `models/checkpoints/benchmark/model-registry.json`

## Implementation Steps

1. Create directory structure:
   ```bash
   mkdir -p models/checkpoints/benchmark
   mkdir -p models/vae
   ```

2. Create `pipeline/benchmark/download-benchmark-models.py`:
   - Use `huggingface_hub.hf_hub_download()` for HuggingFace models
   - Use `requests` with progress bar for CivitAI (AbsoluteReality)
   - For Osama03: Check if diffusers format -- if so, use `diffusers` to load pipeline then extract UNet/text encoder/VAE and save as single checkpoint via `safetensors`
   - For CivitAI: Download API URL `https://civitai.com/api/download/models/{version_id}`
   - Skip download if file already exists and size matches expected

3. Download sequence:
   ```python
   MODELS = {
       "medxray": {
           "repo_id": "Osama03/Medical-X-ray-image-generation-stable-diffusion",
           "filename": "medical-xray-sd15.safetensors",
           "type": "huggingface_diffusers"  # may need conversion
       },
       "realvis": {
           "repo_id": "SG161222/Realistic_Vision_V5.1_noVAE",
           "filename": "Realistic_Vision_V5.1_fp16-no-ema.safetensors",
           "type": "huggingface_single"
       },
       "absreal": {
           "civitai_model_id": 81458,
           "filename": "absolute-reality-v181.safetensors",
           "type": "civitai"
       },
       "cyberreal": {
           "repo_id": "sam749/CyberRealistic-v4-2",
           "filename": "CyberRealistic_V4.2_FP16.safetensors",
           "type": "huggingface_single"
       }
   }
   VAE = {
       "repo_id": "stabilityai/sd-vae-ft-mse-original",
       "filename": "vae-ft-mse-840000-ema-pruned.safetensors"
   }
   ```

4. Verify each downloaded checkpoint:
   - Load with `safetensors.safe_open()` -- check it opens without error
   - Check file size is > 1.5GB (checkpoints) and ~335MB (VAE)
   - Log tensor count and dtypes for each model

5. Handle Osama03 model format:
   <!-- Updated: Validation Session 1 - Check single safetensors first before planning conversion -->
   - **First**: Check HuggingFace repo Files tab for a single `.safetensors` or `.ckpt` file
   - If single file exists: download directly (no conversion needed)
   - **Only if diffusers format**: Check if repo contains `model_index.json`
     - If so: load `StableDiffusionPipeline.from_pretrained()`, then use `convert_diffusers_to_original_stable_diffusion.py` from diffusers repo
   - **If neither works**: Flag as blocker and consider dropping this model from benchmark

6. Write `model-registry.json` with verified paths and metadata

7. Print summary table of downloaded models with sizes

## Todo List
- [ ] Create `pipeline/benchmark/` directory
- [ ] Create `models/checkpoints/benchmark/` directory
- [ ] Implement `download-benchmark-models.py`
- [ ] Handle Osama03 diffusers-to-single-file conversion if needed
- [ ] Download VAE `sd-vae-ft-mse`
- [ ] Download all 4 checkpoints
- [ ] Verify all files load correctly
- [ ] Write `model-registry.json`

## Success Criteria
- All 5 files present in correct directories
- Each file loads without error via `safetensors.safe_open()`
- `model-registry.json` written with accurate paths
- Total disk usage ~10GB

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Osama03 is diffusers format, not single file | Medium | Use diffusers conversion script; fallback: download UNet weights only |
| CivitAI download requires API key or rate-limits | Low | Use browser download as fallback; cache locally |
| Model file corrupted during download | Low | Verify with safetensors loader; re-download if fails |
| Insufficient disk space | Low | Check 15GB free before starting; alert if <20GB |

## Next Steps
- After all models verified -> proceed to Phase 2 (config generation)
- If Osama03 model quality looks poor on inspection -> flag for early pilot test
