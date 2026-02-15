#!/bin/bash
# The Data Mint - One-Click Training Launcher
# Run this script to start the Gradio UI

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if gradio is installed
if ! python -c "import gradio" 2>/dev/null; then
    echo "Installing Gradio..."
    pip install gradio
fi

# Run the launcher
echo "Starting The Data Mint One-Click Launcher..."
echo "Open http://localhost:7860 in your browser"
echo ""

python -m launcher.gradio_launcher_app
