# Phase 04: ComfyUI Workflow Design

## Context Links
- [Plan Overview](plan.md)
- [Research: ControlNet Inpainting](research/researcher-01-comfyui-lora-controlnet.md#3-controlnet-inpainting-workflow-for-sd-15)
- [Brainstorm: Inpainting Pipeline](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: completed
- **Effort**: 4h
- **Description**: Build ComfyUI inpainting workflow combining SD 1.5 + LoRA + ControlNet inpaint. Design prompt templates per defect type. Test single-image generation quality before batch automation.

## Key Insights
- CRITICAL: Use `VAE Encode (for Inpainting)` NOT standard `VAE Encode` - different latent handling
- Chain order: CheckpointLoader -> LoadLoRA -> ControlNetApplyAdvanced -> KSampler
- LoRA strength 0.6-0.8, ControlNet strength 0.7-0.9 to avoid conflicts
- InpaintPreprocessor from ControlNet-Aux required for proper mask conditioning
- Denoise 0.65-0.85: lower = more background preservation, higher = more defect variation

## Requirements

### Functional
- Working ComfyUI workflow that inpaints defects into clean X-ray backgrounds
- LoRA-selectable: switch defect type by loading different LoRA
- Mask input: binary PNG (white=defect region, black=preserve)
- Output: inpainted image + original mask (for annotation pipeline)

### Non-Functional
- Inference time: <4s per 512x512 image at 20 steps
- VRAM usage: <10GB during inference
- Workflow exportable as JSON for API use (Phase 6)

## Architecture

```
Node Graph:

CheckpointLoaderSimple (SD 1.5)
    |
    +-- MODEL --> LoraLoader (defect_lora.safetensors)
    |                 |
    |                 +-- MODEL --> ControlNetApplyAdvanced
    |                 |                    |
    |                 +-- CLIP            +-- positive (conditioned)
    |                                     +-- negative (conditioned)
    |
LoadImage (clean background)
    |
    +-- IMAGE --> InpaintPreprocessor --> ControlNetApplyAdvanced
    |                                         |
LoadImage (binary mask)                       |
    |                                         v
    +-- IMAGE + MASK --> VAE Encode (for Inpainting) --> KSampler
                                                           |
ControlNetLoader (control_v11p_sd15_inpaint)               |
    +-- CONTROL_NET --> ControlNetApplyAdvanced             |
                                                           v
                                                      VAEDecode --> SaveImage
```

## Related Code Files
- Create: `comfyui/workflows/defect-inpaint-workflow.json`
- Create: `comfyui/workflows/prompt-templates.yaml`

## Implementation Steps

1. **Build Base Workflow in ComfyUI UI**
   - Add nodes in this order:
     1. `CheckpointLoaderSimple` -> load SD 1.5
     2. `LoraLoader` -> connect MODEL+CLIP from checkpoint
     3. `CLIPTextEncode` x2 (positive + negative)
     4. `LoadImage` -> clean background
     5. `LoadImage` -> binary mask
     6. `InpaintPreprocessor` -> connect image + mask
     7. `ControlNetLoader` -> load `control_v11p_sd15_inpaint`
     8. `ControlNetApplyAdvanced` -> connect model, positive, negative, ControlNet, preprocessed image
     9. `VAE Encode (for Inpainting)` -> connect image + mask + VAE
     10. `KSampler` -> connect model, positive, negative, latent
     11. `VAEDecode` -> connect latent + VAE
     12. `SaveImage` -> connect decoded image

2. **Configure Prompt Templates**
   ```yaml
   # prompt-templates.yaml
   defect_prompts:
     crack:
       positive: "xray_crack, weld crack defect, radiographic image, high contrast, sharp edges"
       negative: "color, rgb, blurry, low quality, text, watermark"
     porosity:
       positive: "xray_porosity, weld porosity defect, radiographic image, scattered dark spots"
       negative: "color, rgb, blurry, low quality, text, watermark"
     lack_of_fusion:
       positive: "xray_lof, lack of fusion defect, radiographic image, linear indication"
       negative: "color, rgb, blurry, low quality, text, watermark"
     lack_of_penetration:
       positive: "xray_lop, lack of penetration defect, radiographic image, root indication"
       negative: "color, rgb, blurry, low quality, text, watermark"
     slag_inclusion:
       positive: "xray_slag, slag inclusion defect, radiographic image, irregular dark region"
       negative: "color, rgb, blurry, low quality, text, watermark"
   ```

3. **Configure Sampler Settings**
   ```
   sampler_name: euler_ancestral
   scheduler: normal
   steps: 20-30            # Start 20, increase for quality
   cfg: 7-9                # Start 7.5
   denoise: 0.65-0.85      # Start 0.75
   seed: random
   ```

4. **Test Single Image Generation**
   - Load one clean background + one mask
   - Generate with each of 5 LoRAs
   - Evaluate: defect realism, edge blending, background preservation
   - Adjust: LoRA strength, ControlNet strength, denoise, CFG

5. **Parameter Sweep (find optimal settings)**
   - Test matrix:
     - LoRA strength: [0.5, 0.6, 0.7, 0.8]
     - ControlNet strength: [0.6, 0.7, 0.8, 0.9]
     - Denoise: [0.65, 0.70, 0.75, 0.80, 0.85]
   - Generate 3 images per combination, visually rank
   - Record best combo per defect type

6. **Export Workflow JSON**
   - Save from ComfyUI: Dev Mode -> Save (API Format)
   - This JSON used by batch Python client in Phase 6
   - Verify JSON loads back correctly

7. **Test Batch-Ready API Call**
   ```python
   import json, requests
   workflow = json.load(open("defect-inpaint-workflow.json"))
   # Modify dynamic fields: LoRA path, image paths, seed
   response = requests.post("http://localhost:8188/prompt", json={"prompt": workflow})
   print(response.json())  # Should return prompt_id
   ```

## Todo List
- [x] Build inpainting node graph in ComfyUI
- [x] Connect all nodes correctly (especially VAE Encode for Inpainting)
- [x] Create prompt templates YAML
- [x] Export workflow as API-format JSON
- [x] Document final settings per defect type
- [x] Create Python API client for batch automation
- [x] Create validation tests for workflows
- [ ] Test with crack LoRA + clean background + mask (requires models + ComfyUI running)
- [ ] Test all 5 LoRAs (requires models + ComfyUI running)
- [ ] Parameter sweep: find optimal LoRA/ControlNet strength + denoise (requires actual generation)

## Success Criteria
- Workflow generates realistic defect at mask location
- Background preserved outside mask region (SSIM >0.95 outside mask)
- Each of 5 LoRAs produces distinct, recognizable defect morphology
- Inference time <4s per image
- Workflow JSON loads via API and produces same quality output
- No color artifacts in grayscale output

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| Wrong VAE Encode node | High | Triple-check: must be "VAE Encode (for Inpainting)" |
| LoRA + ControlNet conflict | Medium | Reduce strengths, test independently first |
| Prompt engineering fails | Medium | Iterate prompts, add more specific negative terms |
| Background bleeding into defect | Low | Increase denoise strength slightly |

## Security Considerations
- Workflow JSON contains file paths - sanitize before sharing
- API endpoint unauthenticated - only expose on localhost/trusted LAN

## Next Steps
- Phase 5: Build mask generation engine (provides mask input to workflow)
- Phase 6: Automate batch API calls using this workflow JSON
