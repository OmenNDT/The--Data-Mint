# Research Report: ComfyUI LoRA & ControlNet for X-Ray Defect Synthesis

**Project**: The Data Mint - Automated Weld Defect X-Ray Factory
**Date**: 2026-01-30
**Researcher**: researcher-01

---

## 1. ComfyUI API Batch Processing

### Key Findings

**Architecture**: ComfyUI runs Python HTTP server with REST + WebSocket endpoints for programmatic control.

**Primary Endpoints**:
- `/prompt` (POST) - Queue workflows, returns prompt_id
- `/ws` - WebSocket for real-time status updates
- `/history/{prompt_id}` (GET) - Retrieve results
- `/view` - Get generated images by filename
- `/upload/{image_type}` - Upload images/masks

**Batch Processing Flow**:
1. Build workflow JSON → POST to /prompt → Receive prompt_id
2. (Optional) WebSocket /ws for live progress tracking
3. Poll /history/{prompt_id} or wait for WebSocket completion
4. GET /view to download outputs

**Best Practices for 20K-100K Jobs**:
- Use unique prompt_id per job for tracking
- WebSocket recommended for real-time feedback vs REST polling overhead
- Queue management built-in, handles sequential execution
- Error handling: Check prompt_id response for errors before waiting

**Citations**:
- [ComfyUI WebSockets API Part 2](https://medium.com/@yushantripleseven/comfyui-websockets-api-part-2-0ab988acfd97)
- [Production-Ready ComfyUI API Guide](https://www.viewcomfy.com/blog/building-a-production-ready-comfyui-api)
- [Official Routes Documentation](https://docs.comfy.org/development/comfyui-server/comms_routes)

---

## 2. kohya-ss/sd-scripts vs comfyUI-Realtime-Lora

### Key Findings

**NOT Direct Competitors**: comfyUI-Realtime-Lora USES kohya-ss sd-scripts as backend for SD 1.5/SDXL training.

**kohya-ss/sd-scripts**:
- Standalone CLI tool for LoRA training
- Best for: "Fast training, mature workflows, broad checkpoint compatibility"
- Supports SD 1.5, SDXL with extensive hyperparameter control
- Windows compatible via GUI wrapper (Kohya SS)
- Training speed: <2 min for SD 1.5 on modern GPUs

**comfyUI-Realtime-Lora**:
- ComfyUI integration wrapper around sd-scripts + Musubi Tuner
- Trains, analyzes, block-edits LoRAs inside ComfyUI UI
- Supports SD 1.5, SDXL, FLUX, Z-Image Turbo, Wan 2.2
- Same backend (sd-scripts) for SD 1.5 = same quality/speed
- User-friendly node-based interface

**Recommendation for Small Industrial Datasets (50-100 images)**:
- Use **kohya-ss/sd-scripts** directly for production pipelines (programmatic control)
- Use **comfyUI-Realtime-Lora** for rapid prototyping/testing inside ComfyUI
- Both produce identical SD 1.5 LoRAs since Realtime-Lora wraps sd-scripts

**Citations**:
- [comfyUI-Realtime-Lora GitHub](https://github.com/shootthesound/comfyUI-Realtime-Lora)
- [Kohya SS LoRA Training Guide 2025](https://apatero.com/blog/kohya-ss-lora-training-complete-guide-2025)
- [Opinionated Guide to LoRA Training](https://civitai.com/articles/1716/opinionated-guide-to-all-lora-training-2025-update)

---

## 3. ControlNet Inpainting Workflow for SD 1.5

### Model Setup

**Model**: `control_v11p_sd15_inpaint` (ControlNet v1.1)
**Base Checkpoint**: Stable Diffusion v1-5 (trained on this specifically)

### ComfyUI Node Structure

**Required Nodes**:
1. CheckpointLoaderSimple (SD 1.5)
2. ControlNetLoader (load control_v11p_sd15_inpaint)
3. LoadImage (input image)
4. InpaintPreprocessor (from ControlNet_Aux)
5. **VAE Encode (for Inpainting)** - CRITICAL, NOT standard VAE Encode
6. ControlNetApplyAdvanced
7. CLIPTextEncode (positive/negative prompts)
8. KSampler
9. VAEDecode
10. SaveImage

**Connection Flow**:
```
Image → InpaintPreprocessor → ControlNetApplyAdvanced
Image + Mask → VAE Encode (for Inpainting) → KSampler
ControlNet → ControlNetApplyAdvanced → KSampler
Model → KSampler → VAEDecode → SaveImage
```

**Mask Requirements**: Binary mask (white=inpaint region, black=preserve)

### Combining LoRA + ControlNet

**Method**: Chain LoRA nodes BEFORE ControlNet application
```
CheckpointLoader → LoadLoRA → ControlNetApplyAdvanced → KSampler
```

**Best Practice**:
- LoRAs handle identity/style (defect characteristics)
- ControlNet handles structure (preserve weld geometry)
- Start with modest strengths (LoRA: 0.6-0.8, ControlNet: 0.7-0.9) to avoid conflicts

**Citations**:
- [Inpainting with ControlNet SD1.5 Workflow](https://medium.com/@promptingpixels/inpainting-with-comfyui-basic-workflow-with-controlnet-911428c5c57c)
- [control_v11p_sd15_inpaint HuggingFace](https://huggingface.co/lllyasviel/control_v11p_sd15_inpaint)
- [Multi-LoRA Workflows Guide](https://neurocanvas.net/blog/multi-lora-workflows-comfyui/)

---

## 4. GDXray/BAM Dataset Structure

### Overview

**Source**: BAM Federal Institute for Materials Research and Testing, Berlin
**Size**: 3.5 GB total (Welds subset: 98 images, 3 series)
**License**: Free for research/educational use

### Weld Series Breakdown

**W0001 Series**:
- 10 X-ray images
- Resolution: 4K length, varying widths
- Format: TIFF

**W0002 Series**:
- Includes binary masks representing weld flaws
- Bounding box annotations available

**W0003 Series**:
- 67 images total (RRT01.zip: 31 images, RRT02.zip: 36 images)
- Original TIFF format
- Annotated defect regions

### Annotations

**Format**: Standard text files with bounding box coordinates
**Structure**: Object-of-interest labels + coordinates
**Defect Types**: Multiple weld flaw categories (porosity, cracks, inclusions)

### Download

**Official Repository**: [GitHub - GDXray](https://github.com/computervision-xray-testing/GDXray)
**Enhanced Version**: [GDXray+ Dataset Ninja](https://datasetninja.com/gdxray)

**Recommendation**: Use **W0003 series** (67 images, most comprehensive) as base dataset for LoRA training.

**Citations**:
- [GDXray Official GitHub](https://github.com/computervision-xray-testing/GDXray)
- [GDXray Paper (Springer)](https://link.springer.com/article/10.1007/s10921-015-0315-7)
- [GDXray+ Dataset Ninja](https://datasetninja.com/gdxray)

---

## Implementation Recommendations

1. **API Architecture**: Use ComfyUI /prompt REST endpoint + WebSocket for 20K+ batch jobs
2. **LoRA Training**: kohya-ss/sd-scripts directly for production, comfyUI-Realtime-Lora for prototyping
3. **Workflow**: SD 1.5 + LoRA (defect style) + control_v11p_sd15_inpaint (preserve geometry)
4. **Dataset**: GDXray W0003 series (67 images) as training foundation

---

## Unresolved Questions

1. Optimal LoRA hyperparameters for 50-100 X-ray images (learning rate, batch size, epochs)?
2. Mask generation strategy - manual annotation vs automated segmentation for defect regions?
3. ControlNet strength tuning - exact values to preserve weld structure while synthesizing defects?
4. Quality validation - metrics to ensure synthetic defects match real-world distribution?
5. Augmentation strategy - what transformations preserve X-ray physics realism?
