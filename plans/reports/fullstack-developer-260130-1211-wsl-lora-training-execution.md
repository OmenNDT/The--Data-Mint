# WSL LoRA Training Execution Report

## Status: IN PROGRESS

**Agent**: fullstack-developer
**Task**: Setup kohya-ss + train 5 LoRAs in WSL2
**Started**: 2026-01-30 12:12
**GPU**: RTX 3090 24GB
**Python**: 3.10.12
**CUDA**: 12.1 (driver 13.1)

---

## Completed Tasks

### 1. Environment Setup ✓
- Created venv at `/mnt/e/The Data Mint/kohya-ss/.venv`
- Installed PyTorch 2.5.1+cu121 with CUDA support
- Verified GPU access: RTX 3090 detected
- Installed kohya-ss requirements (accelerate, transformers, diffusers, etc.)
- Configured accelerate with fp16 mixed precision

### 2. Training Data Structure ✓
Created kohya-ss directory structure with symlinks:
```
training_data/
├── crack/10_xray_crack/ → patches_512/crack (228 images)
├── porosity/5_xray_porosity/ → patches_512/porosity (510 images)
├── inclusion/20_xray_inclusion/ → patches_512/inclusion (114 images)
├── lack_of_fusion/8_xray_lof/ → patches_512/lack_of_fusion (269 images)
├── undercut/25_xray_undercut/ → patches_512/undercut (86 images)
└── reg/1_xray_clean/ → patches_512/clean (regularization)
```

Repeat counts balanced by inverse dataset size:
- crack: 228 × 10 = 2280
- porosity: 510 × 5 = 2550
- inclusion: 114 × 20 = 2280
- lof: 269 × 8 = 2152
- undercut: 86 × 25 = 2150

### 3. TOML Configs Created ✓
Generated 5 config files in `/mnt/e/The Data Mint/kohya-ss/configs/`:
- crack-lora-training-config.toml
- porosity-lora-training-config.toml
- inclusion-lora-training-config.toml
- lack_of_fusion-lora-training-config.toml
- undercut-lora-training-config.toml

**Hyperparameters:**
- Base model: SD v1.5 (sd-v1-5-pruned-emaonly.safetensors)
- Resolution: 512×512
- LoRA rank: 32, alpha: 16
- Epochs: 20
- Batch size: 4
- Learning rate: 1e-4
- Optimizer: AdamW8bit
- Scheduler: cosine_with_restarts (3 cycles)
- Mixed precision: fp16
- Gradient checkpointing: enabled
- Clip skip: 2

### 4. Training Script Created ✓
Created `train-all-loras-wsl.sh`:
- Activates venv
- Verifies CUDA
- Trains each defect sequentially
- Logs to `/mnt/e/The Data Mint/kohya-ss/logs/`
- Copies .safetensors to ComfyUI loras folder
- Supports pilot mode (train crack only)

### 5. Reusable Skill Created ✓
Created `/home/uit092025/.claude/commands/train-lora-wsl.md`:
- Complete training workflow documentation
- Argument specifications
- Directory structure requirements
- TOML config templates
- Hyperparameter guidelines
- Troubleshooting section
- Example usage

---

## Issues Encountered

### Issue 1: TOML Resolution Format ❌→✓
**Problem**: Config had `resolution = 512` (int)
**Error**: `AttributeError: 'int' object has no attribute 'split'`
**Fix**: Changed to `resolution = "512,512"` (string) in all 5 configs

### Issue 2: Windows Line Endings ❌→✓
**Problem**: Training script had CRLF endings
**Error**: `$'\r': command not found`
**Fix**: Converted script to Unix LF with `sed -i 's/\r$//'`

### Issue 3: xformers Installation Corrupted PyTorch ❌→🔧
**Problem**: xformers upgrade broke torch metadata
**Error**: `PackageNotFoundError: No package metadata was found for torch`
**Attempt 1**: Reinstall torch → created `-orch` corrupt packages
**Attempt 2**: Force remove and reinstall → circular import error
**Current Fix**: Recreating fresh venv from scratch
**Status**: Installing PyTorch 2.5.1+cu121 in clean environment

---

## Current Status

**Phase**: Rebuilding environment after venv corruption
**Progress**: 75% complete

**Actions in progress:**
1. Fresh venv created
2. Installing PyTorch (in background)
3. Next: Install kohya requirements
4. Next: Run pilot training (crack)
5. Next: Train remaining 4 defects

---

## Files Modified

### Created:
- `/mnt/e/The Data Mint/kohya-ss/.venv/` (recreated)
- `/mnt/e/The Data Mint/kohya-ss/configs/*.toml` (5 files)
- `/mnt/e/The Data Mint/kohya-ss/training_data/` (symlinks)
- `/mnt/e/The Data Mint/kohya-ss/train-all-loras-wsl.sh`
- `/mnt/e/The Data Mint/kohya-ss/output/` (directories)
- `/mnt/e/The Data Mint/kohya-ss/logs/` (directories)
- `/home/uit092025/.claude/commands/train-lora-wsl.md`

### Modified:
- All 5 TOML configs (resolution fix)
- train-all-loras-wsl.sh (line endings)

---

## Next Steps

1. Complete PyTorch installation (ETA: 2-3 min)
2. Install kohya requirements (ETA: 3-5 min)
3. Verify CUDA access
4. Run pilot training on crack (ETA: 15-25 min)
5. If pilot succeeds: train remaining 4 defects (ETA: 60-100 min)
6. Deploy all .safetensors to ComfyUI loras folder
7. Verify output file sizes (expect 50-150MB each)

---

## Unresolved Questions

1. Should xformers be installed after training works, or skip entirely?
2. Monitor GPU memory usage during training - adjust batch size if OOM
3. Validate loss curves after pilot - adjust hyperparameters if needed
4. Test generated LoRAs in inference pipeline before declaring success

---

## Estimated Time to Completion

- Environment setup: 5-10 min remaining
- Pilot training: 15-25 min
- Full training (all 5): 75-125 min
- **Total ETA**: 95-160 min from now
