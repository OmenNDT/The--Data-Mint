"""
Checkpoint State Manager

Saves and restores batch production progress to JSON file.
Enables resume capability after interruption or crash.
Uses atomic write (temp file + rename) to prevent corruption.
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional


class CheckpointManager:
    """Manages checkpoint persistence for batch production state."""

    def __init__(self, config: Dict):
        """
        Initialize checkpoint manager.

        Args:
            config: Batch configuration dict
        """
        checkpoint_dir = Path(config["paths"]["checkpoint_dir"])
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint file path
        self.checkpoint_path = checkpoint_dir / "batch_state.json"
        self.checkpoint_interval = config["reliability"]["checkpoint_interval"]

        # Track last save
        self.last_checkpoint_count = 0

    def should_checkpoint(self, completed_count: int) -> bool:
        """
        Check if checkpoint should be saved based on interval.

        Args:
            completed_count: Number of completed jobs

        Returns:
            True if checkpoint should be saved
        """
        return completed_count - self.last_checkpoint_count >= self.checkpoint_interval

    def save_checkpoint(self, state: Dict):
        """
        Save checkpoint state to disk atomically.

        Args:
            state: State dict to save
        """
        # Add timestamp
        state["checkpoint_time"] = time.time()
        state["checkpoint_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Write to temp file first
        temp_path = self.checkpoint_path.with_suffix(".tmp")

        with open(temp_path, "w") as f:
            json.dump(state, f, indent=2)

        # Atomic rename
        temp_path.replace(self.checkpoint_path)

        self.last_checkpoint_count = state["completed_count"]

        print(f"  Checkpoint saved: {state['completed_count']} images complete")

    def load_checkpoint(self) -> Optional[Dict]:
        """
        Load checkpoint state from disk.

        Returns:
            State dict or None if no checkpoint exists
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            with open(self.checkpoint_path, "r") as f:
                state = json.load(f)

            print(f"\nFound checkpoint from {state.get('checkpoint_timestamp', 'unknown')}")
            print(f"  Progress: {state['completed_count']} images complete")

            return state

        except Exception as e:
            print(f"Warning: Failed to load checkpoint: {e}")
            return None

    def delete_checkpoint(self):
        """Delete checkpoint file (called after successful completion)."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            print("Checkpoint deleted (batch complete)")

    def backup_checkpoint(self):
        """Create backup of current checkpoint."""
        if not self.checkpoint_path.exists():
            return

        backup_path = self.checkpoint_path.with_suffix(
            f".backup.{int(time.time())}.json"
        )
        self.checkpoint_path.rename(backup_path)
        print(f"Checkpoint backed up to: {backup_path}")
