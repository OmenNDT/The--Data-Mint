#!/usr/bin/env python3
"""
YOLO Trainer

Wrapper for training YOLOv8 models on different dataset configurations.
Supports training experiments with varying synthetic data ratios.
"""

import shutil
import yaml
from pathlib import Path
from typing import Dict, Optional


def train_yolo(
    data_yaml_path: Path,
    experiment_name: str,
    output_dir: Path,
    model_size: str = "n",
    epochs: int = 300,
    batch_size: int = 16,
    imgsz: int = 640,
    device: int = 0,
    patience: int = 50,
    resume: bool = False
) -> Dict:
    """
    Train YOLOv8 model.

    Args:
        data_yaml_path: Path to YOLO data.yaml configuration
        experiment_name: Name for this training run
        output_dir: Directory to save results
        model_size: YOLOv8 model size (n, s, m, l, x)
        epochs: Number of training epochs
        batch_size: Batch size
        imgsz: Input image size
        device: GPU device ID (0 for first GPU)
        patience: Early stopping patience
        resume: Resume from last checkpoint

    Returns:
        Training results dict
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics package not installed. "
            "Install with: pip install ultralytics"
        )

    # Load pretrained model
    model_name = f"yolov8{model_size}.pt"
    model = YOLO(model_name)

    print(f"Training YOLOv8{model_size} - {experiment_name}")
    print(f"  Data: {data_yaml_path}")
    print(f"  Epochs: {epochs}, Batch: {batch_size}, Image size: {imgsz}")

    # Train
    results = model.train(
        data=str(data_yaml_path),
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        device=device,
        project=str(output_dir),
        name=experiment_name,
        patience=patience,
        save=True,
        plots=True,
        resume=resume,
        verbose=True
    )

    print(f"✓ Training completed: {experiment_name}")

    # Return results path
    results_dir = output_dir / experiment_name

    return {
        "experiment_name": experiment_name,
        "results_dir": str(results_dir),
        "weights_path": str(results_dir / "weights" / "best.pt"),
        "completed": True
    }


def create_mixed_dataset_yaml(
    real_yolo_dir: Path,
    synth_yolo_dir: Path,
    synth_ratio: float,
    output_dir: Path,
    experiment_name: str,
    seed: int = 42
) -> Path:
    """
    Create mixed dataset with specified synthetic ratio.

    Args:
        real_yolo_dir: Path to real YOLO dataset
        synth_yolo_dir: Path to synthetic YOLO dataset
        synth_ratio: Fraction of synthetic data (0.0 to 1.0)
        output_dir: Output directory for mixed dataset
        experiment_name: Experiment name
        seed: Random seed for reproducibility

    Returns:
        Path to generated data.yaml
    """
    import random
    import os

    random.seed(seed)

    experiment_dir = output_dir / experiment_name
    experiment_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    for split in ["train", "val"]:
        (experiment_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (experiment_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    # Mix datasets for each split
    for split in ["train", "val"]:
        # Get real images
        real_images_dir = real_yolo_dir / split / "images"
        real_labels_dir = real_yolo_dir / split / "labels"

        real_images = list(real_images_dir.glob("*.png")) + list(real_images_dir.glob("*.jpg"))

        # Get synthetic images
        synth_images_dir = synth_yolo_dir / split / "images"
        synth_labels_dir = synth_yolo_dir / split / "labels"

        synth_images = list(synth_images_dir.glob("*.png")) + list(synth_images_dir.glob("*.jpg"))

        # Calculate how many of each to include
        if synth_ratio == 0.0:
            # Real-only
            n_real = len(real_images)
            n_synth = 0
        elif synth_ratio == 1.0:
            # Synth-only
            n_real = 0
            n_synth = len(synth_images)
        else:
            # Mixed: keep total size constant based on real dataset size
            total_target = len(real_images)
            n_synth = int(total_target * synth_ratio)
            n_real = total_target - n_synth

        # Sample images
        selected_real = random.sample(real_images, min(n_real, len(real_images)))
        selected_synth = random.sample(synth_images, min(n_synth, len(synth_images)))

        # Copy to experiment directory
        dest_images_dir = experiment_dir / split / "images"
        dest_labels_dir = experiment_dir / split / "labels"

        for img_path in selected_real:
            shutil.copy2(img_path, dest_images_dir / img_path.name)
            label_path = real_labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                shutil.copy2(label_path, dest_labels_dir / label_path.name)

        for img_path in selected_synth:
            shutil.copy2(img_path, dest_images_dir / img_path.name)
            label_path = synth_labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                shutil.copy2(label_path, dest_labels_dir / label_path.name)

        print(f"  {split}: {len(selected_real)} real + {len(selected_synth)} synthetic")

    # Create data.yaml
    yaml_content = {
        "path": str(experiment_dir.resolve()),
        "train": "train/images",
        "val": "val/images",
        "nc": 5,
        "names": ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
    }

    yaml_path = experiment_dir / "data.yaml"
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, default_flow_style=False)

    print(f"✓ Created mixed dataset: {yaml_path}")
    return yaml_path
