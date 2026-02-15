"""Auto-labeler module: YOLO detection + SAM segmentation for X-ray defects.

Provides automatic defect labeling on any folder of X-ray images,
producing COCO/YOLO annotations and binary mask PNGs.
"""

__version__ = "0.1.0"

from importlib import import_module

# Re-export public API via importlib (hyphenated filenames)
_dataclass_mod = import_module(
    ".detection-result-dataclass", package=__name__
)
DetectionResult = _dataclass_mod.DetectionResult
SegmentedDetection = _dataclass_mod.SegmentedDetection
ImageAutoLabelResult = _dataclass_mod.ImageAutoLabelResult
AutoLabelResult = _dataclass_mod.AutoLabelResult
AutoLabelConfig = _dataclass_mod.AutoLabelConfig

_pipeline_mod = import_module(
    ".auto-label-pipeline-main", package=__name__
)
run_auto_labeling = _pipeline_mod.run_auto_labeling
load_config_from_yaml = _pipeline_mod.load_config_from_yaml

__all__ = [
    "DetectionResult",
    "SegmentedDetection",
    "ImageAutoLabelResult",
    "AutoLabelResult",
    "AutoLabelConfig",
    "run_auto_labeling",
    "load_config_from_yaml",
]
