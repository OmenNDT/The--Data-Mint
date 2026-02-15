#!/bin/bash
#
# Batch Production Wrapper Script
#
# Runs batch production with correct Python virtual environment
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Please set up the virtual environment first."
    exit 1
fi

# Run batch production with venv Python
exec "$VENV_PYTHON" "$SCRIPT_DIR/batch_manager/batch-production-main.py" "$@"
