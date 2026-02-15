# Phase 01: Environment Setup

## Context Links
- [Plan Overview](plan.md)
- [Research: ComfyUI/LoRA/ControlNet](research/researcher-01-comfyui-lora-controlnet.md)

## Overview
- **Priority**: P1 (blocking all other phases)
- **Status**: in_progress
- **Effort**: 3h
- **Description**: Install ComfyUI, CUDA toolkit, Python environment, SD 1.5 checkpoint, ControlNet models, and required extensions. Verify GPU detection and VRAM availability.

## Key Insights
- RTX 3090 24GB VRAM: ~7-9GB inference, ~12-16GB LoRA training = comfortable headroom
- PCIe 3.0 minimal impact since SD 1.5 fits entirely in VRAM
- ComfyUI supports `--lowvram` and `--gpu-only` flags but likely unnecessary on 24GB

## Requirements

### Functional
- ComfyUI running with GPU acceleration
- SD 1.5 checkpoint loaded and generating test images
- ControlNet v1.1 inpaint model loaded
- All required extensions installed and functional

### Non-Functional
- Python 3.10+ virtual environment isolated from system Python
- CUDA 12.x with cuDNN for RTX 3090 (Ampere)
- Stable operation under sustained GPU load

## Architecture

```
E:\The Data Mint\
├── comfyui/          -> symlink to E:\ComfyUI_windows_portable\ComfyUI (reused)
│   ├── models/
│   │   ├── checkpoints/   # SD 1.5 + existing SDXL
│   │   ├── loras/         # trained LoRAs (Phase 3)
│   │   ├── controlnet/    # ControlNet v1.1 inpaint + canny
│   │   └── vae/
│   ├── custom_nodes/      # extensions (existing + 3 new)
│   └── output/
├── kohya-ss/              # LoRA training (clone, venv setup in Phase 3)
├── pipeline/              # Python batch scripts + WSL venv
│   └── .venv/             # requests, pillow, numpy, opencv, pycocotools
├── dataset/
│   ├── gdxray/            # Raw GDXray W0003
│   └── processed/         # Preprocessed 512x512
└── output/
    ├── synthetic/         # Generated images
    └── annotations/       # COCO + YOLO
```

## Related Code Files
- No code files to modify (fresh install)
- Create: directory structure above

## Implementation Steps

1. **Install CUDA Toolkit 12.x**
   - Download from NVIDIA developer site
   - Verify: `nvidia-smi` shows RTX 3090, `nvcc --version` returns 12.x

2. **Install ComfyUI**
   ```powershell
   cd C:\DataMint
   git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
   cd comfyui
   python -m venv venv
   venv\Scripts\activate
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt
   ```

3. **Download SD 1.5 Checkpoint**
   - File: `sd-v1-5-pruned-emaonly.safetensors` (4.27 GB)
   - Source: HuggingFace `stable-diffusion-v1-5/stable-diffusion-v1-5`
   - Place in: `comfyui/models/checkpoints/`

4. **Download ControlNet Models**
   - `control_v11p_sd15_inpaint.pth` -> `comfyui/models/controlnet/`
   - `control_v11p_sd15_canny.pth` -> `comfyui/models/controlnet/`
   - Source: HuggingFace `lllyasviel/control_v11p_sd15_inpaint`

5. **Install ComfyUI Extensions**
   ```powershell
   cd C:\DataMint\comfyui\custom_nodes
   git clone https://github.com/shootthesound/comfyUI-Realtime-Lora.git
   git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git
   git clone https://github.com/kijai/ComfyUI-KJNodes.git
   git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git
   ```
   - Install each extension's requirements.txt

6. **Install kohya-ss/sd-scripts (separate env)**
   ```powershell
   cd C:\DataMint
   git clone https://github.com/kohya-ss/sd-scripts.git kohya-ss
   cd kohya-ss
   python -m venv venv
   venv\Scripts\activate
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt
   accelerate config  # select fp16, single GPU
   ```

7. **Verify Installation**
   - Start ComfyUI: `python main.py --listen 0.0.0.0 --port 8188`
   - Open `http://localhost:8188` in browser
   - Load default workflow, generate test image with SD 1.5
   - Confirm GPU utilization via `nvidia-smi`
   - Check VRAM usage during generation (~4-6GB expected)

## Todo List
- [x] GPU verified: RTX 3090 24GB, CUDA 13.1 driver (exceeds 12.x requirement)
- [x] Reuse existing ComfyUI portable (E:\ComfyUI_windows_portable), symlinked
- [x] Download SD 1.5 checkpoint (4.0GB, sd-v1-5-pruned-emaonly.safetensors)
- [x] Download ControlNet v1.1 inpaint (1.4GB) + canny (1.4GB) models
- [x] Install 3 missing extensions (Realtime-Lora, Impact-Pack, KJNodes); ControlNet-Aux already present
- [x] Clone kohya-ss/sd-scripts repo + setup script created
- [ ] Run kohya-ss venv setup + `accelerate config` (deferred to Phase 3, requires Windows PowerShell)
- [x] Create pipeline WSL venv with deps (requests, pillow, numpy, opencv, pycocotools)
- [ ] Start ComfyUI, generate test image, verify GPU usage (requires Windows-side execution)

## Success Criteria
- `nvidia-smi` shows RTX 3090 with CUDA 12.x
- ComfyUI generates 512x512 image using SD 1.5 checkpoint
- ControlNet inpaint model loads without errors
- All 4 extensions show in ComfyUI node list
- kohya-ss `accelerate config` completed (fp16, single GPU)

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| CUDA version mismatch | High | Match PyTorch CUDA version to installed toolkit |
| Extension conflicts | Medium | Install one at a time, test after each |
| Disk space (~15GB models) | Low | Verify available space before downloads |

## Security Considerations
- Download models only from official HuggingFace repos
- Verify .safetensors files (safer than .ckpt pickle format)
- ComfyUI `--listen 0.0.0.0` exposes to network; use only on trusted LAN

## Next Steps
- Phase 2: Download and preprocess GDXray dataset
- Phase 3: Begin LoRA training once environment verified
