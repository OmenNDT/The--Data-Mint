#!/bin/bash
# Run Post-Processing Pipeline
# Converts raw synthetic output to COCO + YOLO annotated datasets

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python3"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Virtual environment not found at ${SCRIPT_DIR}/.venv"
    echo "Using system python3"
    VENV_PYTHON="python3"
fi

echo "=================================================="
echo "Post-Processing Pipeline - The Data Mint"
echo "=================================================="
echo ""

# Default paths
SYNTHETIC_DIR="/mnt/e/The Data Mint/output/synthetic"
OUTPUT_DIR="/mnt/e/The Data Mint/output/dataset"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --synthetic-dir)
            SYNTHETIC_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --synthetic-dir PATH   Path to synthetic output (default: /mnt/e/The Data Mint/output/synthetic)"
            echo "  --output-dir PATH      Path to output dataset (default: /mnt/e/The Data Mint/output/dataset)"
            echo "  --help                 Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Synthetic input: $SYNTHETIC_DIR"
echo "Dataset output:  $OUTPUT_DIR"
echo ""

# Run post-processing
cd "$SCRIPT_DIR"

"$VENV_PYTHON" post_processing/post-processing-main.py \
    --synthetic-dir "$SYNTHETIC_DIR" \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "=================================================="
echo "Post-Processing Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Run QA pipeline: cd qa && python3 qa-pipeline-main.py"
echo "  2. Review COCO annotations: $OUTPUT_DIR/annotations/"
echo "  3. Train YOLO: cd validation && python3 validation-main.py"
echo ""
