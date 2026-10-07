# Phase 4: LoRA Training Execution

## Context Links
- [Plan Overview](plan.md)
- [Phase 2: Config Generation](phase-02-generate-training-configs.md)
- [Research: Kohya Multi-Model Training](research/researcher-01-kohya-multi-model-training.md)
- Training script: `kohya-ss/train-all-loras-wsl.sh`
- Example config: `kohya-ss/configs/crack-lora-training-config.toml`

## Overview
- **Priority**: P1 (blocks all evaluation phases)
- **Status**: complete
- **Effort**: 5 days (mostly GPU wall-clock time, ~1h active scripting)
- **Description**: Train 20 LoRA models (5 defects x 4 base models) using generated TOML configs. Deploy trained LoRAs to ComfyUI.

## Key Insights
- Each defect LoRA trains ~4-8h on RTX 3090 (20 epochs, batch 4, grad accum 2)
- 5 defects per model = 20-40h per base model
- 4 base models sequential = 80-160h total (~3.5-7 days)
- **Strategy**: Run 1 model per night; monitor first model (medxray) closely before committing to remaining 3
- Existing `train-all-loras-wsl.sh` loops through defects -- adapt for model iteration
- `save_every_n_epochs = 5` captures checkpoints at epochs 5, 10, 15, 20

## Requirements

### Functional
- Create benchmark training script that iterates models x defects
- Use Phase 2 generated TOML configs
- Save intermediate checkpoints (epochs 10, 15, 20 minimum)
- Copy final LoRAs to ComfyUI `models/loras/` directory
- Log training time, final loss per run

### Non-functional
- GPU cooldown between runs (60s sleep)
- Resumable: skip already-completed training runs
- Exit on error (don't silently continue with broken LoRA)
- Log everything to timestamped log file

## Architecture

### Training Schedule (Recommended)

| Night | Model | Defects | Est. Duration |
|-------|-------|---------|---------------|
| 1 | medxray | crack (pilot first) | 4-8h |
| 1-2 | medxray | remaining 4 | 16-32h |
| 3 | realvis | all 5 | 20-40h |
| 4 | absreal | all 5 | 20-40h |
| 5 | cyberreal | all 5 | 20-40h |

**Pilot strategy**: Train medxray/crack first, inspect output, confirm no errors before bulk run.

### Output File Locations
```
kohya-ss/output/benchmark/
├── medxray/
│   ├── crack/
│   │   ├── xray_crack_medxray_lora_r32.safetensors          # epoch 20 (final)
│   │   ├── xray_crack_medxray_lora_r32-000010.safetensors   # epoch 10
│   │   └── xray_crack_medxray_lora_r32-000015.safetensors   # epoch 15
│   ├── porosity/
│   │   └── ...
│   └── ... (5 defects)
├── realvis/ ...
├── absreal/ ...
└── cyberreal/ ...
```

### Deployed LoRAs (ComfyUI)
```
models/loras/
├── xray_crack_medxray_lora_r32.safetensors
├── xray_porosity_medxray_lora_r32.safetensors
├── xray_inclusion_medxray_lora_r32.safetensors
├── xray_lof_medxray_lora_r32.safetensors
├── xray_undercut_medxray_lora_r32.safetensors
├── xray_crack_realvis_lora_r32.safetensors
└── ... (20 total)
```

## Related Code Files
- **Read**: `kohya-ss/train-all-loras-wsl.sh` (existing, use as reference)
- **Read**: `kohya-ss/configs/benchmark/{model}/{defect}-lora-training-config.toml` (from Phase 2)
- **Create**: `pipeline/benchmark/train-benchmark-loras.sh`

## Implementation Steps

### Step 1: Create `pipeline/benchmark/train-benchmark-loras.sh`

```bash
#!/bin/bash
# Benchmark LoRA Training Script
# Trains 5 defect LoRAs for each of 4 benchmark base models
# Usage: ./train-benchmark-loras.sh [model_short|all|pilot]

set -e
set -o pipefail

PROJECT_ROOT="/home/sontn/Projects/The Data Mint"
KOHYA_DIR="$PROJECT_ROOT/kohya-ss"
COMFYUI_LORAS="$PROJECT_ROOT/models/loras"
BENCHMARK_CONFIGS="$KOHYA_DIR/configs/benchmark"
LOG_DIR="$PROJECT_ROOT/kohya-ss/logs/benchmark"
LOG_FILE="$LOG_DIR/benchmark-training-$(date +%Y%m%d-%H%M%S).log"

MODELS=("medxray" "realvis" "absreal" "cyberreal")
DEFECTS=("crack" "porosity" "inclusion" "lack_of_fusion" "undercut")

mkdir -p "$LOG_DIR"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

MODE=${1:-"all"}

case "$MODE" in
    pilot)
        MODELS=("medxray")
        DEFECTS=("crack")
        ;;
    all)
        ;;
    *)
        if [[ " ${MODELS[*]} " =~ " ${MODE} " ]]; then
            MODELS=("$MODE")
        else
            echo "Usage: $0 [all|pilot|medxray|realvis|absreal|cyberreal]"
            exit 1
        fi
        ;;
esac

cd "$KOHYA_DIR"
source .venv/bin/activate

TOTAL_RUNS=$(( ${#MODELS[@]} * ${#DEFECTS[@]} ))
CURRENT_RUN=0

for model in "${MODELS[@]}"; do
    for defect in "${DEFECTS[@]}"; do
        CURRENT_RUN=$((CURRENT_RUN + 1))
        CONFIG_FILE="$BENCHMARK_CONFIGS/$model/${defect}-lora-training-config.toml"
        OUTPUT_DIR="$KOHYA_DIR/output/benchmark/$model/$defect"

        # Skip if final LoRA already exists
        EXPECTED_OUTPUT="$OUTPUT_DIR/xray_${defect}_${model}_lora_r32.safetensors"
        if [ -f "$EXPECTED_OUTPUT" ]; then
            echo "[$CURRENT_RUN/$TOTAL_RUNS] SKIP $model/$defect (already exists)" | tee -a "$LOG_FILE"
            continue
        fi

        echo "[$CURRENT_RUN/$TOTAL_RUNS] Training $model/$defect..." | tee -a "$LOG_FILE"
        echo "Config: $CONFIG_FILE" | tee -a "$LOG_FILE"
        echo "Started: $(date)" | tee -a "$LOG_FILE"

        mkdir -p "$OUTPUT_DIR"
        python3 -c "import torch; torch.cuda.empty_cache()" 2>/dev/null || true

        START_TIME=$(date +%s)

        accelerate launch --mixed_precision fp16 \
            train_network.py \
            --config_file "$CONFIG_FILE" \
            2>&1 | tee -a "$LOG_FILE"

        END_TIME=$(date +%s)
        DURATION=$(( (END_TIME - START_TIME) / 60 ))
        echo "Duration: ${DURATION} minutes" | tee -a "$LOG_FILE"

        # Copy final LoRA to ComfyUI
        LATEST=$(ls -t "$OUTPUT_DIR"/*.safetensors 2>/dev/null | head -1)
        if [ -f "$LATEST" ]; then
            cp "$LATEST" "$COMFYUI_LORAS/"
            echo "Deployed: $(basename "$LATEST")" | tee -a "$LOG_FILE"
        else
            echo "ERROR: No output for $model/$defect" | tee -a "$LOG_FILE"
            exit 1
        fi

        # GPU cooldown
        sleep 60
    done
done

echo "All benchmark training complete!" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"
```

### Step 2: Make Script Executable
```bash
chmod +x pipeline/benchmark/train-benchmark-loras.sh
```

### Step 3: Pilot Run (medxray/crack only)
```bash
./pipeline/benchmark/train-benchmark-loras.sh pilot
```

Verify:
- Training completes without OOM or CUDA errors
- Output LoRA exists in `kohya-ss/output/benchmark/medxray/crack/`
- File size is reasonable (~37-75MB for rank 32)
- Intermediate checkpoints saved at epoch 5, 10, 15

### Step 4: Inspect Pilot LoRA Quality
Before committing to 19 more runs:
- Quick visual test in ComfyUI UI: load medxray checkpoint + medxray crack LoRA
- Generate 5-10 test images manually
- Check for: catastrophic forgetting, mode collapse, color artifacts, blank outputs
- If quality poor, investigate LR adjustment (see Risk section)

### Step 5: Full Training Run
```bash
# Run remaining medxray defects
./pipeline/benchmark/train-benchmark-loras.sh medxray

# Run each subsequent model (one per night)
./pipeline/benchmark/train-benchmark-loras.sh realvis
./pipeline/benchmark/train-benchmark-loras.sh absreal
./pipeline/benchmark/train-benchmark-loras.sh cyberreal
```

### Step 6: Verify All 20 LoRAs Deployed
```bash
ls -lh models/loras/xray_*_*_lora_r32.safetensors | wc -l
# Expected: 20

ls -lh models/loras/xray_*_*_lora_r32.safetensors
# Should show all 20 files with sizes ~37-75MB each
```

### Step 7: Create Training Summary
After all runs complete, create `kohya-ss/output/benchmark/training-summary.json`:
```json
{
  "medxray": {
    "crack": {"duration_min": 240, "final_loss": 0.042, "file_size_mb": 37.5},
    "porosity": {"duration_min": 280, "final_loss": 0.038, "file_size_mb": 37.5}
  }
}
```
Parse from log file or collect manually.

## Todo List
- [ ] Create `pipeline/benchmark/train-benchmark-loras.sh`
- [ ] Run pilot: medxray/crack
- [ ] Inspect pilot LoRA quality in ComfyUI
- [ ] If pilot OK: run remaining medxray defects (4 runs)
- [ ] Run realvis (5 runs, overnight)
- [ ] Run absreal (5 runs, overnight)
- [ ] Run cyberreal (5 runs, overnight)
- [ ] Verify all 20 LoRAs deployed to `models/loras/`
- [ ] Create training summary JSON

## Success Criteria
- 20 `.safetensors` files in `kohya-ss/output/benchmark/{model}/{defect}/`
- 20 LoRAs copied to `models/loras/`
- Each LoRA file ~37-75MB (rank 32 expected range)
- No training failures in log
- Intermediate checkpoints at epochs 10, 15, 20

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| OOM on RTX 3090 with new checkpoint | Medium | Same batch size works with vanilla SD 1.5; all models are same architecture |
| Photorealistic models overfit faster | Medium | Checkpoints at epoch 10/15/20 allow picking best epoch in Phase 6 |
| Osama03 model produces poor LoRA | Medium | Pilot run first; can skip if unusable |
| Training interrupted (power, crash) | Low | Script resumes (skips existing outputs); `save_every_n_epochs` preserves progress |
| Different models need different LR | Medium | Keep 5e-5 for all initially; if loss diverges, create model-specific config with 8e-5 or 3e-5 |

### LR Fallback Strategy
If a model's training loss does not decrease or diverges:
1. Check epoch 5 checkpoint quality visually
2. If overfitting: reduce LR to 3e-5, reduce epochs to 15
3. If underfitting: increase LR to 1e-4
4. Re-run only affected model/defect combinations

## Next Steps
- Phase 5: Use trained LoRAs for pilot image generation (500 per model)
- Training logs useful for Phase 6 evaluation (loss curves comparison)
