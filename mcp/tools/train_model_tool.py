"""Train model tool — trigger LoRA fine-tuning or YOLOv8 detection training."""

import subprocess
from pathlib import Path


def register(mcp, project_root: Path):
    @mcp.tool()
    def train_model(model_type: str, dry_run: bool = True) -> dict:
        """Train AI model with synthetic data.

        Args:
            model_type: 'yolo' for YOLOv8 detection, 'lora' for LoRA fine-tuning
            dry_run: If True (default), only show config without executing. Set False to run.
        """
        if model_type == "yolo":
            return _yolo_training(project_root, dry_run)
        elif model_type == "lora":
            return _lora_training(project_root, dry_run)
        else:
            return {"error": f"Unknown model_type: {model_type}. Use 'yolo' or 'lora'."}


def _yolo_training(project_root: Path, dry_run: bool) -> dict:
    """YOLOv8 detection training on synthetic dataset."""
    yolo_dir = project_root / "output" / "dataset" / "yolo"
    validation_script = project_root / "pipeline" / "validation" / "validation-main.py"

    # Check dataset exists
    if not yolo_dir.exists():
        return {"error": "YOLO dataset not found. Run Phase 7 (post-processing) first."}

    # Count available training data
    train_images = list((yolo_dir / "train" / "images").glob("*.png")) if (yolo_dir / "train" / "images").exists() else []
    val_images = list((yolo_dir / "val" / "images").glob("*.png")) if (yolo_dir / "val" / "images").exists() else []

    config = {
        "model_type": "yolo",
        "base_model": "yolov8n.pt",
        "dataset_path": str(yolo_dir),
        "train_images": len(train_images),
        "val_images": len(val_images),
        "epochs": 100,
        "imgsz": 512,
        "batch_size": 16,
        "script": str(validation_script),
    }

    if dry_run:
        return {"dry_run": True, "config": config, "message": "Set dry_run=False to start training."}

    # Execute training
    if not validation_script.exists():
        return {"error": f"Training script not found: {validation_script}"}

    try:
        proc = subprocess.Popen(
            ["python3", str(validation_script)],
            cwd=str(project_root / "pipeline"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return {
            "dry_run": False,
            "status": "started",
            "pid": proc.pid,
            "config": config,
            "message": f"YOLOv8 training started (PID: {proc.pid}). Monitor via pipeline_status().",
        }
    except Exception as e:
        return {"error": f"Failed to start training: {e}"}


def _lora_training(project_root: Path, dry_run: bool) -> dict:
    """LoRA fine-tuning via kohya-ss."""
    kohya_dir = project_root / "kohya-ss"
    train_script = kohya_dir / "train-all-loras-wsl.sh"

    # Check training configs
    config_dir = kohya_dir / "configs"
    configs = list(config_dir.glob("*.toml")) if config_dir.exists() else []

    config = {
        "model_type": "lora",
        "kohya_dir": str(kohya_dir),
        "train_script": str(train_script),
        "configs_found": [c.name for c in configs],
        "config_count": len(configs),
        "rank": 32,
        "alpha": 16,
        "epochs": 10,
    }

    if dry_run:
        return {"dry_run": True, "config": config, "message": "Set dry_run=False to start LoRA training."}

    if not train_script.exists():
        return {"error": f"Training script not found: {train_script}"}

    try:
        proc = subprocess.Popen(
            ["bash", str(train_script)],
            cwd=str(kohya_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return {
            "dry_run": False,
            "status": "started",
            "pid": proc.pid,
            "config": config,
            "message": f"LoRA training started (PID: {proc.pid}). Check progress via pipeline_status().",
        }
    except Exception as e:
        return {"error": f"Failed to start training: {e}"}
