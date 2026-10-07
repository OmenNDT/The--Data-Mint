# Post-Processing Pipeline

Converts raw synthetic output (image + mask + metadata) into annotated datasets for training.

## Features

- **COCO JSON format**: Instance segmentation with polygon annotations
- **YOLO TXT format**: Object detection with normalized bounding boxes
- **Stratified splitting**: Train/val/test splits maintaining defect distribution
- **Automatic conversion**: Masks → polygons + bboxes

## Usage

### Basic Usage

```bash
# From pipeline root directory
python3 post_processing/post-processing-main.py \
  --synthetic-dir /mnt/e/The\ Data\ Mint/output/synthetic \
  --output-dir /mnt/e/The\ Data\ Mint/output/dataset
```

### Custom Split Ratios

```bash
python3 post_processing/post-processing-main.py \
  --synthetic-dir /path/to/synthetic \
  --output-dir /path/to/output \
  --train-ratio 0.80 \
  --val-ratio 0.15 \
  --test-ratio 0.05
```

### Skip Validation (if pycocotools not installed)

```bash
python3 post_processing/post-processing-main.py \
  --skip-validation
```

## Output Structure

```
output/dataset/
├── annotations/
│   ├── coco_train.json
│   ├── coco_val.json
│   └── coco_test.json
├── yolo/
│   ├── train/
│   │   ├── images/
│   │   └── labels/
│   ├── val/
│   │   ├── images/
│   │   └── labels/
│   ├── test/
│   │   ├── images/
│   │   └── labels/
│   └── data.yaml
└── post-processing-report.txt
```

## Category Mapping

| Defect Type      | COCO ID | YOLO ID |
|------------------|---------|---------|
| crack            | 1       | 0       |
| porosity         | 2       | 1       |
| inclusion        | 3       | 2       |
| lack_of_fusion   | 4       | 3       |
| undercut         | 5       | 4       |

Note: COCO uses 1-indexed category IDs, YOLO uses 0-indexed class IDs.

## Dependencies

- opencv-python (cv2)
- numpy
- pyyaml
- tqdm
- pycocotools (optional, for validation)

## Performance

- ~450 images/second (I/O limited)
- 20K images: ~45 seconds
- 100K images: ~3.7 minutes
