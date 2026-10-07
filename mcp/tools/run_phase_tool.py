"""Run phase tool — trigger specific pipeline phase execution."""

import subprocess
from pathlib import Path


# Phase scripts mapping
PHASE_SCRIPTS = {
    5: {"name": "Mask Generation", "script": "mask_generator/", "type": "module"},
    6: {"name": "Batch Production", "script": "batch_manager/batch-production-main.py", "type": "python"},
    7: {"name": "Post-Processing", "script": "post_processing/post-processing-main.py", "type": "python"},
    8: {"name": "Quality Assurance", "script": "qa/qa-pipeline-main.py", "type": "python"},
    9: {"name": "Downstream Validation", "script": "validation/validation-main.py", "type": "python"},
}


def register(mcp, project_root: Path):
    @mcp.tool()
    def run_phase(phase: int, dry_run: bool = True) -> dict:
        """Trigger a specific pipeline phase.

        Args:
            phase: Phase number (5-9). Phases 1-4 are manual setup steps.
            dry_run: If True (default), show what would run without executing.
        """
        if phase not in PHASE_SCRIPTS:
            return {
                "error": f"Phase {phase} not executable. Available: {list(PHASE_SCRIPTS.keys())}",
                "note": "Phases 1-4 are manual setup (environment, preprocessing, LoRA training, workflow design).",
            }

        phase_info = PHASE_SCRIPTS[phase]
        script_path = project_root / "pipeline" / phase_info["script"]

        config = {
            "phase": phase,
            "name": phase_info["name"],
            "script": str(script_path),
            "exists": script_path.exists(),
        }

        if dry_run:
            return {"dry_run": True, "config": config, "message": "Set dry_run=False to execute."}

        if not script_path.exists():
            return {"error": f"Script not found: {script_path}"}

        try:
            cmd = ["python3", str(script_path)]
            if phase == 6:
                # Batch production uses config
                cmd.extend(["--config", str(project_root / "pipeline" / "config" / "batch-config.yaml")])

            proc = subprocess.Popen(
                cmd,
                cwd=str(project_root / "pipeline"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            return {
                "dry_run": False,
                "status": "started",
                "pid": proc.pid,
                "config": config,
                "message": f"Phase {phase} ({phase_info['name']}) started (PID: {proc.pid}).",
            }
        except Exception as e:
            return {"error": f"Failed to start phase {phase}: {e}"}
