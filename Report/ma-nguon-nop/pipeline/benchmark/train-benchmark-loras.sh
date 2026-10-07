#!/bin/bash
# Benchmark LoRA Training Script
# Trains 5 defect LoRAs for each of 4 benchmark base models
# Usage: ./pipeline/benchmark/train-benchmark-loras.sh [all|pilot|medxray|realvis|absreal|cyberreal]

set -e
set -o pipefail

PROJECT_ROOT="/home/sontn/Projects/The Data Mint"
KOHYA_DIR="$PROJECT_ROOT/kohya-ss"
COMFYUI_LORAS="$PROJECT_ROOT/models/loras"
BENCHMARK_CONFIGS="$KOHYA_DIR/configs/benchmark"
LOG_DIR="$KOHYA_DIR/logs/benchmark"
LOG_FILE="$LOG_DIR/benchmark-training-$(date +%Y%m%d-%H%M%S).log"

MODELS=("realvis" "absreal" "cyberreal")
DEFECTS=("crack")
# TODO: restore full list when training data is ready
# DEFECTS=("crack" "porosity" "inclusion" "lack_of_fusion" "undercut")

mkdir -p "$LOG_DIR"
mkdir -p "$COMFYUI_LORAS"

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

echo "Starting benchmark training: ${#MODELS[@]} models x ${#DEFECTS[@]} defects = $TOTAL_RUNS runs" | tee -a "$LOG_FILE"

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

        if [ ! -f "$CONFIG_FILE" ]; then
            echo "[$CURRENT_RUN/$TOTAL_RUNS] ERROR: config not found: $CONFIG_FILE" | tee -a "$LOG_FILE"
            exit 1
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

        # Copy final LoRA to ComfyUI loras directory
        LATEST=$(ls -t "$OUTPUT_DIR"/*.safetensors 2>/dev/null | head -1)
        if [ -f "$LATEST" ]; then
            cp "$LATEST" "$COMFYUI_LORAS/"
            echo "Deployed: $(basename "$LATEST")" | tee -a "$LOG_FILE"
        else
            echo "ERROR: No output for $model/$defect" | tee -a "$LOG_FILE"
            exit 1
        fi

        # GPU cooldown between runs
        echo "Cooling down 60s..." | tee -a "$LOG_FILE"
        sleep 60
    done
done

echo "" | tee -a "$LOG_FILE"
echo "All benchmark training complete!" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"

# Count deployed LoRAs
DEPLOYED=$(ls "$COMFYUI_LORAS"/xray_*_*_lora_r32.safetensors 2>/dev/null | wc -l)
echo "Deployed LoRAs: $DEPLOYED" | tee -a "$LOG_FILE"
