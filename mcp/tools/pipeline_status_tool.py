"""Pipeline status tool — reads checkpoints, logs, and config to report current state."""

import json
from pathlib import Path


def register(mcp, project_root: Path):
    @mcp.tool()
    def pipeline_status() -> dict:
        """Get current pipeline status: latest checkpoint, generation progress, errors."""
        checkpoint_dir = project_root / "pipeline" / "checkpoints"
        logs_dir = project_root / "pipeline" / "logs"
        output_dir = project_root / "output" / "synthetic"

        result = {
            "checkpoint": _get_latest_checkpoint(checkpoint_dir),
            "output_counts": _count_outputs(output_dir),
            "recent_errors": _get_recent_errors(logs_dir),
        }
        return result


def _get_latest_checkpoint(checkpoint_dir: Path) -> dict:
    """Read the most recent checkpoint file."""
    if not checkpoint_dir.exists():
        return {"status": "no_checkpoints_dir"}

    checkpoints = sorted(checkpoint_dir.glob("batch_state*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not checkpoints:
        return {"status": "no_checkpoints"}

    latest = checkpoints[0]
    try:
        data = json.loads(latest.read_text())
        return {
            "file": latest.name,
            "modified": latest.stat().st_mtime,
            "data": data,
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "error", "error": str(e)}


def _count_outputs(output_dir: Path) -> dict:
    """Count generated images per defect type."""
    if not output_dir.exists():
        return {"status": "no_output_dir"}

    counts = {}
    total = 0
    for defect_dir in sorted(output_dir.iterdir()):
        if defect_dir.is_dir():
            count = len(list(defect_dir.glob("*.png")))
            counts[defect_dir.name] = count
            total += count
    counts["_total"] = total
    return counts


def _get_recent_errors(logs_dir: Path) -> list:
    """Extract recent error lines from logs."""
    if not logs_dir.exists():
        return []

    log_files = sorted(logs_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not log_files:
        return []

    errors = []
    # Check latest log file only
    latest_log = log_files[0]
    try:
        lines = latest_log.read_text().splitlines()
        for line in lines[-100:]:  # Last 100 lines
            if "ERROR" in line or "FAIL" in line:
                errors.append(line.strip())
    except OSError:
        pass
    return errors[-10:]  # Return max 10 recent errors
