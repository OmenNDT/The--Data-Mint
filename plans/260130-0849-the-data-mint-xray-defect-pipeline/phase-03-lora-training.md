# Phase 03: LoRA Training

## Context Links
- [Plan Overview](plan.md)
- [Research: LoRA Training](research/researcher-01-comfyui-lora-controlnet.md#2-kohya-sssd-scripts-vs-comfyui-realtime-lora)
- [Brainstorm: LoRA Strategy](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: pending
- **Effort**: 6h
- **Description**: Train 5 separate LoRA models (one per defect type) using kohya-ss/sd-scripts on SD 1.5. Each LoRA captures X-ray texture + defect morphology for its specific defect class.

## Key Insights
- kohya-ss/sd-scripts for production (CLI, reproducible); comfyUI-Realtime-Lora wraps same backend
- Train UNet only - X-ray has no text-style variance, text encoder training unnecessary
- Rank 32-64: start 32, increase to 64 if quality insufficient
- Gradient checkpointing + fp16 + AdamW8bit -> fits in 24GB VRAM
- Noise offset 0.05-0.1 helps with high-contrast grayscale images
- ~50-100 images per defect type, SD 1.5 LoRA trains fast (minutes per epoch)
- Regularization images (clean X-rays) prevent style drift

## Requirements

### Functional
- 5 LoRA .safetensors files: crack, porosity, lack_of_fusion, lack_of_penetration, slag_inclusion
- Each LoRA responds to its trigger word (e.g., `xray_crack`)
- Generated samples visually match defect morphology of real examples

### Non-Functional
- Training time: <2h per LoRA on RTX 3090
- VRAM usage: <16GB with gradient checkpointing
- Reproducible: config TOML saved per LoRA

## Architecture

```
kohya-ss/
├── configs/
│   ├── crack-lora.toml
│   ├── porosity-lora.toml
│   ├── lof-lora.toml
│   ├── lop-lora.toml
│   └── slag-lora.toml
├── training_data/
│   ├── crack/                # Defect patches + captions from Phase 2
│   ├── porosity/
│   ├── lack_of_fusion/
│   ├── lack_of_penetration/
│   └── slag_inclusion/
├── reg_images/               # Regularization: clean X-ray patches
├── outputs/
│   ├── crack_lora.safetensors
│   ├── porosity_lora.safetensors
│   ├── lof_lora.safetensors
│   ├── lop_lora.safetensors
│   └── slag_lora.safetensors
└── logs/                     # TensorBoard logs per training run
```

## Related Code Files
- Create: 5x TOML config files in `kohya-ss/configs/`
- Create: training launch script `kohya-ss/train-all-loras.ps1`

## Implementation Steps

1. **Prepare Training Data Directory**
   - Symlink or copy defect patches from Phase 2 output
   - Verify caption .txt files present for each image
   - Place clean X-ray patches in `reg_images/` (1:1 ratio with training images)

2. **Create Base Training Config (TOML)**
   ```toml
   [model]
   pretrained_model_name_or_path = "C:/DataMint/comfyui/models/checkpoints/sd-v1-5-pruned-emaonly.safetensors"

   [network]
   network_module = "networks.lora"
   network_dim = 32          # LoRA rank (increase to 64 if needed)
   network_alpha = 16        # alpha = rank/2 is common default

   [training]
   resolution = 512
   train_batch_size = 4
   max_train_epochs = 150
   learning_rate = 1e-4
   lr_scheduler = "cosine_with_restarts"
   lr_warmup_steps = 50
   mixed_precision = "fp16"
   gradient_checkpointing = true
   cache_latents = true
   optimizer_type = "AdamW8bit"
   noise_offset = 0.07
   seed = 42
   save_every_n_epochs = 25
   sample_every_n_epochs = 25

   [dataset]
   train_data_dir = "training_data/crack"
   reg_data_dir = "reg_images"

   [output]
   output_dir = "outputs"
   output_name = "crack_lora"
   save_model_as = "safetensors"
   logging_dir = "logs"
   ```

3. **Clone Config per Defect Type**
   - Modify `train_data_dir` and `output_name` for each of 5 defect types
   - Adjust epochs if patch count varies significantly between types

4. **Train LoRAs Sequentially**
   ```powershell
   # Train each LoRA (sequential - single GPU)
   cd C:\DataMint\kohya-ss
   venv\Scripts\activate

   accelerate launch --num_cpu_threads_per_process 8 train_network.py --config_file configs/crack-lora.toml
   accelerate launch --num_cpu_threads_per_process 8 train_network.py --config_file configs/porosity-lora.toml
   # ... repeat for lof, lop, slag
   ```

5. **Monitor Training**
   - TensorBoard: `tensorboard --logdir logs/`
   - Check loss curves: should decrease steadily, no spikes after warmup
   - Review sample outputs every 25 epochs for visual quality

6. **Evaluate LoRA Quality**
   - Load each LoRA in ComfyUI with SD 1.5
   - Generate 10 test images per LoRA using trigger word prompts
   - Compare side-by-side with real defect patches
   - Check: correct defect morphology, X-ray texture, no color artifacts

7. **Iterate if Needed**
   - If quality poor at rank 32 -> increase to rank 64
   - If overfitting (training loss drops, samples look like copies) -> reduce epochs, add augmentation
   - If underfitting -> increase learning rate to 2e-4 or increase epochs

8. **Deploy LoRAs**
   - Copy final .safetensors to `C:\DataMint\comfyui\models\loras\`
   - Verify each loads in ComfyUI LoadLoRA node

## Todo List
- [ ] Organize training data directories from Phase 2 output
- [ ] Prepare regularization image set (clean patches)
- [ ] Create base TOML config
- [ ] Clone and customize config for all 5 defect types
- [ ] Train crack LoRA (pilot run, validate pipeline)
- [ ] Train remaining 4 LoRAs
- [ ] Monitor TensorBoard, review sample outputs
- [ ] Generate 10 test images per LoRA in ComfyUI
- [ ] Visual comparison: synthetic vs real defects
- [ ] Copy final .safetensors to ComfyUI models/loras/
- [ ] Document final hyperparameters per LoRA

## Success Criteria
- 5 .safetensors files generated without errors
- Each LoRA produces recognizable defect type when triggered
- Training loss converges (no divergence or plateau)
- Generated samples: correct morphology, grayscale X-ray texture, no color bleeding
- VRAM usage stays under 16GB during training
- Total training time: <10h for all 5 LoRAs

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| LoRA doesn't capture X-ray texture | High | Increase rank to 64-128, add noise_offset, more epochs |
| Too few training images per defect | High | Augment with flips/rotations, supplement from W0001/W0002 |
| Overfitting on small dataset | Medium | Use regularization images, reduce epochs, increase alpha |
| Color artifacts in grayscale | Medium | Negative prompt: "color, rgb, chromatic" during inference |
| Training divergence | Low | Reduce learning rate, check data quality |

## Security Considerations
- LoRA files are .safetensors (no arbitrary code execution risk)
- Training data stays local, no cloud upload needed

## Next Steps
- Phase 4: Integrate trained LoRAs into ComfyUI inpainting workflow
- If quality insufficient: iterate hyperparameters before proceeding
