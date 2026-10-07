"""
Post-Processing Module

Converts raw synthetic output (image + mask + metadata) into annotated dataset formats:
- COCO JSON format (for instance segmentation training)
- YOLO TXT format (for object detection training)
- Derives bounding boxes from masks automatically
- Organizes into train/val splits (80/20)
"""

from importlib import import_module

# Import from kebab-case filenames
mask_to_annotation_module = import_module('.mask-to-annotation-converter', package=__name__)
coco_builder_module = import_module('.coco-dataset-builder', package=__name__)
yolo_builder_module = import_module('.yolo-dataset-builder', package=__name__)
splitter_module = import_module('.dataset-splitter', package=__name__)
main_module = import_module('.post-processing-main', package=__name__)

mask_to_annotation = mask_to_annotation_module.mask_to_annotation
build_coco_dataset = coco_builder_module.build_coco_dataset
build_yolo_dataset = yolo_builder_module.build_yolo_dataset
split_dataset = splitter_module.split_dataset
run_post_processing = main_module.run_post_processing

__all__ = [
    'mask_to_annotation',
    'build_coco_dataset',
    'build_yolo_dataset',
    'split_dataset',
    'run_post_processing',
]
