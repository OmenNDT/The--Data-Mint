#!/bin/bash
# Example: Single image inpainting using ComfyUI API client
#
# Prerequisites:
# 1. ComfyUI server running on http://127.0.0.1:8188
# 2. Models installed in ComfyUI:
#    - checkpoints/sd-v1-5-pruned-emaonly.safetensors
#    - controlnet/control_v11p_sd15_inpaint.pth
#    - loras/xray_crack_lora_r32.safetensors (or other defect LoRAs)
# 3. Input images prepared:
#    - Clean X-ray background (512x512 PNG)
#    - Binary mask (512x512 PNG, white=defect region, black=preserve)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
CLIENT="${SCRIPT_DIR}/comfyui-api-batch-inpaint-client.py"

# Input paths (CHANGE THESE to your actual image paths)
BACKGROUND="${SCRIPT_DIR}/test_data/clean_background_512x512.png"
MASK="${SCRIPT_DIR}/test_data/binary_mask_512x512.png"

# Output path
OUTPUT_DIR="${SCRIPT_DIR}/test_output/comfyui_inpaint"
mkdir -p "$OUTPUT_DIR"

# ComfyUI server
COMFYUI_URL="http://127.0.0.1:8188"

echo "==================================================================="
echo "ComfyUI Inpainting Example - Single Image"
echo "==================================================================="
echo ""
echo "Configuration:"
echo "  Background: $BACKGROUND"
echo "  Mask:       $MASK"
echo "  Server:     $COMFYUI_URL"
echo ""

# Test 1: Crack defect
echo "[1/5] Generating crack defect..."
$PYTHON "$CLIENT" \
    --background "$BACKGROUND" \
    --mask "$MASK" \
    --defect-type crack \
    --output "$OUTPUT_DIR/crack_defect_001.png" \
    --seed 42 \
    --server-url "$COMFYUI_URL"

# Test 2: Porosity defect
echo ""
echo "[2/5] Generating porosity defect..."
$PYTHON "$CLIENT" \
    --background "$BACKGROUND" \
    --mask "$MASK" \
    --defect-type porosity \
    --output "$OUTPUT_DIR/porosity_defect_001.png" \
    --seed 42 \
    --server-url "$COMFYUI_URL"

# Test 3: Inclusion defect
echo ""
echo "[3/5] Generating inclusion defect..."
$PYTHON "$CLIENT" \
    --background "$BACKGROUND" \
    --mask "$MASK" \
    --defect-type inclusion \
    --output "$OUTPUT_DIR/inclusion_defect_001.png" \
    --seed 42 \
    --server-url "$COMFYUI_URL"

# Test 4: Lack of fusion defect
echo ""
echo "[4/5] Generating lack_of_fusion defect..."
$PYTHON "$CLIENT" \
    --background "$BACKGROUND" \
    --mask "$MASK" \
    --defect-type lack_of_fusion \
    --output "$OUTPUT_DIR/lof_defect_001.png" \
    --seed 42 \
    --server-url "$COMFYUI_URL"

# Test 5: Undercut defect
echo ""
echo "[5/5] Generating undercut defect..."
$PYTHON "$CLIENT" \
    --background "$BACKGROUND" \
    --mask "$MASK" \
    --defect-type undercut \
    --output "$OUTPUT_DIR/undercut_defect_001.png" \
    --seed 42 \
    --server-url "$COMFYUI_URL"

echo ""
echo "==================================================================="
echo "✓ All 5 defect types generated successfully!"
echo "==================================================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Generated files:"
ls -lh "$OUTPUT_DIR"/*.png
