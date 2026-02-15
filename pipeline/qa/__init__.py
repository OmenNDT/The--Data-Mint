"""
Quality Assurance Module

Automated quality validation pipeline for synthetic X-ray defect images:
- SSIM background preservation check
- Annotation validation (COCO/YOLO format consistency)
- Defect distribution verification
- Visual spot-check sampling
"""

from importlib import import_module

# Import from kebab-case filenames
ssim_module = import_module('.ssim-background-checker', package=__name__)
annotation_module = import_module('.annotation-validator', package=__name__)
spot_check_module = import_module('.visual-spot-check-grid', package=__name__)
main_module = import_module('.qa-pipeline-main', package=__name__)

check_ssim_background = ssim_module.check_ssim_background
validate_annotations = annotation_module.validate_annotations
create_spot_check_grid = spot_check_module.create_spot_check_grid
run_qa_pipeline = main_module.run_qa_pipeline

__all__ = [
    'check_ssim_background',
    'validate_annotations',
    'create_spot_check_grid',
    'run_qa_pipeline',
]
