"""
Downstream Validation Module

Validates synthetic dataset quality by training YOLOv8 detector:
- Trains on real-only, real+synthetic, and synthetic-only datasets
- Evaluates on held-out real test set
- Compares performance across different synthetic ratios
- Generates validation report with recommendations
"""

from importlib import import_module

# Import from kebab-case filenames
trainer_module = import_module('.yolo-trainer', package=__name__)
metrics_module = import_module('.evaluation-metrics', package=__name__)
main_module = import_module('.validation-main', package=__name__)

train_yolo = trainer_module.train_yolo
evaluate_model = metrics_module.evaluate_model
run_validation = main_module.run_validation

__all__ = [
    'train_yolo',
    'evaluate_model',
    'run_validation',
]
