# ComfyUI Inpainting Workflows

This directory contains ComfyUI workflow JSON files and configuration for automated defect inpainting in X-ray images.

## Files

### Workflows

1. **`sd15-lora-controlnet-inpaint-single-defect-workflow.json`**
   - Single-image inpainting workflow for manual testing in ComfyUI UI
   - Load this in ComfyUI to test defect generation interactively
   - Fixed parameters (edit JSON to change LoRA/images)

2. **`sd15-lora-controlnet-inpaint-batch-api-workflow.json`**
   - API-ready workflow with placeholder variables
   - Used by `comfyui-api-batch-inpaint-client.py` for batch automation
   - Placeholders: `{{LORA_NAME}}`, `{{POSITIVE_PROMPT}}`, `{{BACKGROUND_IMAGE}}`, `{{MASK_IMAGE}}`, `{{SEED}}`, `{{OUTPUT_PREFIX}}`

### Configuration

3. **`defect-type-prompt-templates.yaml`**
   - Prompt templates for each defect type
   - LoRA filenames and strength settings
   - ControlNet strength and denoise values
   - Optimized per defect morphology

## Workflow Architecture

```
CheckpointLoaderSimple (SD 1.5)
    ├─> MODEL ─> LoraLoader (defect-specific)
    ├─> CLIP ──────┘   │
    └─> VAE            ├─> MODEL ─> KSampler ─> VAEDecode ─> SaveImage
                       └─> CLIP ─> CLIPTextEncode (pos/neg)
                                        │
LoadImage (background) ────────────────┼─> InpaintModelConditioning ─> KSampler
LoadImage (mask) ──────────────────────┘         │
                                                  └─> ControlNetApplyAdvanced
ControlNetLoader (inpaint) ───────────────────────┘
```

## Node Details

| Node ID | Type | Purpose |
|---------|------|---------|
| 1 | CheckpointLoaderSimple | Load SD 1.5 base model |
| 2 | LoraLoader | Load defect-specific LoRA (0.7 strength) |
| 3 | CLIPTextEncode | Positive prompt with defect trigger words |
| 4 | CLIPTextEncode | Negative prompt (color, blur, artifacts) |
| 5 | LoadImage | Clean background image (512x512) |
| 6 | LoadImage | Binary mask (white=inpaint region) |
| 7 | ControlNetLoader | control_v11p_sd15_inpaint.pth |
| 8 | InpaintModelConditioning | Combine image+mask for inpainting |
| 9 | ControlNetApplyAdvanced | Apply ControlNet guidance (0.8 strength) |
| 10 | KSampler | 20 steps, CFG 7.0, euler, denoise 0.85 |
| 11 | VAEDecode | Decode latents to RGB image |
| 12 | SaveImage | Save result with prefix |

## Critical Implementation Notes

### VAE Encode Node
- **MUST use `InpaintModelConditioning`**, NOT standard `VAE Encode`
- Standard VAE Encode will fail for inpainting workflows
- InpaintModelConditioning properly handles mask latent encoding

### LoRA + ControlNet Interaction
- Chain order: Checkpoint → LoRA → ControlNet → Sampler
- LoRA handles defect identity/morphology
- ControlNet preserves background structure
- Modest strengths (0.7-0.8) prevent conflicts

### Denoise Strength
- **0.85** = high defect variation, good background preservation
- Lower (0.65-0.75) = more background fidelity, less defect variation
- Higher (0.90-0.95) = more creative defects, risk background alteration

## Model Requirements

Place these models in ComfyUI `models/` directory:

```
models/
├── checkpoints/
│   └── sd-v1-5-pruned-emaonly.safetensors
├── controlnet/
│   └── control_v11p_sd15_inpaint.pth
└── loras/
    ├── xray_crack_lora_r32.safetensors
    ├── xray_porosity_lora_r32.safetensors
    ├── xray_inclusion_lora_r32.safetensors
    ├── xray_lof_lora_r32.safetensors
    └── xray_undercut_lora_r32.safetensors
```

### Download Links

**SD 1.5**: https://huggingface.co/runwayml/stable-diffusion-v1-5
**ControlNet Inpaint**: https://huggingface.co/lllyasviel/control_v11p_sd15_inpaint
**LoRAs**: Train using Phase 2 pipeline (see `../lora-training/`)

## Usage

### Manual Testing (UI)

1. Launch ComfyUI
2. Load `sd15-lora-controlnet-inpaint-single-defect-workflow.json`
3. Edit node inputs:
   - Node 2: Change LoRA filename
   - Node 3: Change positive prompt
   - Node 5: Select background image
   - Node 6: Select mask image
   - Node 10: Change seed
4. Queue Prompt → View output

### Batch Automation (API)

Use `comfyui-api-batch-inpaint-client.py`:

```bash
python ../comfyui-api-batch-inpaint-client.py \
    --background /path/to/clean_bg.png \
    --mask /path/to/mask.png \
    --defect-type crack \
    --output /path/to/output.png \
    --seed 42
```

Parameters auto-loaded from `defect-type-prompt-templates.yaml`.

## Defect Type Prompts

### Crack
- **Trigger**: `xray_crack, weld crack defect`
- **Description**: Linear discontinuity, sharp edges, high contrast
- **Denoise**: 0.85

### Porosity
- **Trigger**: `xray_porosity, weld porosity defect`
- **Description**: Scattered dark spots, gas pockets, spherical voids
- **Denoise**: 0.80

### Inclusion
- **Trigger**: `xray_inclusion, slag inclusion defect`
- **Description**: Irregular dark region, non-metallic particles
- **Denoise**: 0.82

### Lack of Fusion
- **Trigger**: `xray_lof, lack of fusion defect`
- **Description**: Linear indication, unbonded region, interface separation
- **Denoise**: 0.85

### Undercut
- **Trigger**: `xray_undercut, weld undercut defect`
- **Description**: Groove along weld toe, material reduction, edge discontinuity
- **Denoise**: 0.83

## Performance Specs

- **Resolution**: 512x512 px
- **Inference Time**: <4s per image (RTX 3060 12GB)
- **VRAM Usage**: ~8GB during inference
- **Batch Throughput**: ~900 images/hour (single GPU)

## Troubleshooting

### "No VAE Encode (for Inpainting) node"
- Install ComfyUI-Manager
- Update core nodes
- Restart ComfyUI

### "ControlNet model not found"
- Verify `control_v11p_sd15_inpaint.pth` in `models/controlnet/`
- Check exact filename spelling

### Color Artifacts in Output
- Add `rgb, color, photograph` to negative prompt
- Increase CFG to 8.0-9.0
- Check source images are grayscale

### Background Not Preserved
- Lower denoise to 0.70-0.75
- Reduce ControlNet strength to 0.6-0.7
- Verify mask is binary (pure black/white)

## Next Steps

- **Phase 5**: Integrate mask generator outputs as inputs
- **Phase 6**: Batch automation script for 20K+ dataset generation
- **Phase 7**: Quality validation and defect distribution analysis
