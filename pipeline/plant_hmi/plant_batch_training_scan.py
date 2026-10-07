"""Detects a live kohya-ss LoRA training process (`train_network.py`): same GPU as
the batch pipeline, so a training run blocks a new batch start (`NO_TRAINING`
permissive, phase 6A). Split out of `plant_batch_process_ops.py` purely to keep
each file under the 200-line guideline; both are read-only /proc scans.
"""

import os
from pathlib import Path
from typing import List

TRAINING_SCRIPT_MARKER = "train_network"


def find_training_processes() -> List[int]:
    """Live pids running `train_network.py` (kohya-ss LoRA training)."""
    found: List[int] = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            argv = [a.decode(errors="replace") for a in argv if a]
        except OSError:
            continue
        # only a python/accelerate process running the script counts (a shell whose command
        # line merely mentions "train_network", e.g. `pgrep -af train_network`, does not)
        prog = os.path.basename(argv[0]) if argv else ""
        if ("python" in prog or "accelerate" in prog) and any(
                a.endswith(TRAINING_SCRIPT_MARKER + ".py") for a in argv[1:]):
            found.append(pid)
    return found
