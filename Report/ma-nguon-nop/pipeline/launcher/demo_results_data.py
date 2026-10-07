"""Demo Results Data - Fake QA/validation JSON for demo mode UI testing."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


FAKE_QA_RESULTS = {
    "ssim_mean": 0.941,
    "ssim_std": 0.023,
    "pass_rate": 0.97,
    "total_images_checked": 100,
    "coco_validation_valid": True,
    "yolo_validation_valid": True,
    "defect_distribution": {
        "crack": 0.20,
        "porosity": 0.20,
        "inclusion": 0.20,
        "lack_of_fusion": 0.20,
        "undercut": 0.20,
    },
}


FAKE_VALIDATION_RESULTS = {
    "experiments": [
        {"ratio": 0.0, "map50": 0.312, "map50_95": 0.189},
        {"ratio": 0.5, "map50": 0.523, "map50_95": 0.298},
        {"ratio": 1.0, "map50": 0.612, "map50_95": 0.381},
    ],
    "optimal_ratio": 1.0,
    "model_size": "n",
    "epochs": 20,
}


def write_fake_results(output_dir: str) -> None:
    """Write fake QA and validation results to output directory.

    Args:
        output_dir: Base output directory path
    """
    output_path = Path(output_dir)

    # Write QA results
    qa_dir = output_path / "qa-reports"
    qa_dir.mkdir(parents=True, exist_ok=True)
    qa_file = qa_dir / "qa-results.json"
    qa_file.write_text(json.dumps(FAKE_QA_RESULTS, indent=2))
    logger.info(f"Wrote fake QA results to {qa_file}")

    # Write validation results
    val_dir = output_path / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)
    val_file = val_dir / "validation-results.json"
    val_file.write_text(json.dumps(FAKE_VALIDATION_RESULTS, indent=2))
    logger.info(f"Wrote fake validation results to {val_file}")
