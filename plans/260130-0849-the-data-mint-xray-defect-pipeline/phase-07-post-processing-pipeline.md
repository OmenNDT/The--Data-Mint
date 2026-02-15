# Phase 07: Post-Processing Pipeline

## Context Links
- [Plan Overview](plan.md)
- [Research: COCO/YOLO Conversion](research/researcher-02-masks-annotations-qa.md#2-coco--yolo-annotation-format-conversion)
- [Brainstorm: Auto-Annotation](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: pending
- **Effort**: 4h
- **Description**: Convert inpainting masks to COCO polygon + YOLO bbox annotations. Multi-resolution resize. Organize output directory structure. Generate metadata CSV.

## Key Insights
- Inpainting mask IS the ground truth - no separate annotation step needed
- mask -> COCO: `cv2.findContours` -> flatten -> polygon + bbox + area
- mask -> YOLO: bbox normalized (x_center, y_center, w, h)
- pycocotools validates COCO format; Ultralytics `convert_coco()` for COCO->YOLO
- Multi-defect images need one annotation instance per defect
- CPU-parallelizable: 44 cores for batch conversion

## Requirements

### Functional
- Convert binary mask -> COCO JSON (polygon segmentation + bbox + area)
- Convert binary mask -> YOLO TXT (normalized bbox per image)
- Multi-resolution output: 512x512 primary (768x768 optional)
- Organized directory structure with train/val/test splits
- metadata.csv: image_id, defect_type, source_background, mask_path, generation_params

### Non-Functional
- Process 20K+ images in <30min on 44-core CPU
- Valid COCO JSON (loadable by pycocotools.coco.COCO)
- Valid YOLO format (loadable by Ultralytics)

## Architecture

```
output/
├── dataset/
│   ├── images/
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   ├── masks/
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   ├── annotations/
│   │   ├── coco_train.json
│   │   ├── coco_val.json
│   │   └── coco_test.json
│   ├── yolo/
│   │   ├── train/
│   │   │   ├── images/
│   │   │   └── labels/
│   │   ├── val/
│   │   │   ├── images/
│   │   │   └── labels/
│   │   ├── test/
│   │   │   ├── images/
│   │   │   └── labels/
│   │   └── data.yaml
│   └── metadata.csv
│
pipeline/
├── post_processor/
│   ├── __init__.py
│   ├── mask_to_coco.py        # Mask -> COCO polygon conversion
│   ├── mask_to_yolo.py        # Mask -> YOLO bbox conversion
│   ├── dataset_splitter.py    # Train/val/test split
│   ├── resizer.py             # Multi-resolution output
│   ├── metadata_writer.py     # CSV metadata generation
│   └── main.py                # Orchestration entry point
```

## Related Code Files
- Create: all files in `pipeline/post_processor/` (6 files)
- Depends on: `pipeline/mask_generator/` (Phase 5) for mask format
- Depends on: `pipeline/batch_manager/` (Phase 6) for raw output location

## Implementation Steps

1. **Implement Mask-to-COCO Converter**
   ```python
   # mask_to_coco.py
   CATEGORY_MAP = {
       "crack": 1,
       "porosity": 2,
       "lack_of_fusion": 3,
       "lack_of_penetration": 4,
       "slag_inclusion": 5
   }

   def build_coco_dataset(image_mask_pairs, split_name):
       coco = {
           "images": [],
           "annotations": [],
           "categories": [
               {"id": v, "name": k} for k, v in CATEGORY_MAP.items()
           ]
       }
       ann_id = 1
       for img_id, (img_path, mask_path, defect_type) in enumerate(image_mask_pairs, 1):
           mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
           h, w = mask.shape

           coco["images"].append({
               "id": img_id, "file_name": os.path.basename(img_path),
               "height": h, "width": w
           })

           contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
           for contour in contours:
               if contour.size >= 6:
                   seg = contour.flatten().tolist()
                   pos = np.where(mask > 0)
                   bbox = [int(np.min(pos[1])), int(np.min(pos[0])),
                           int(np.max(pos[1]) - np.min(pos[1])),
                           int(np.max(pos[0]) - np.min(pos[0]))]
                   coco["annotations"].append({
                       "id": ann_id, "image_id": img_id,
                       "category_id": CATEGORY_MAP[defect_type],
                       "segmentation": [seg], "bbox": bbox,
                       "area": int(np.sum(mask > 0)), "iscrowd": 0
                   })
                   ann_id += 1
       return coco
   ```

2. **Implement Mask-to-YOLO Converter**
   ```python
   # mask_to_yolo.py
   def mask_to_yolo_label(mask_path, defect_type, img_w, img_h):
       mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
       pos = np.where(mask > 0)
       if len(pos[0]) == 0:
           return ""
       xmin, ymin = np.min(pos[1]), np.min(pos[0])
       xmax, ymax = np.max(pos[1]), np.max(pos[0])

       x_center = ((xmin + xmax) / 2) / img_w
       y_center = ((ymin + ymax) / 2) / img_h
       width = (xmax - xmin) / img_w
       height = (ymax - ymin) / img_h

       class_id = CATEGORY_MAP[defect_type] - 1  # YOLO uses 0-indexed
       return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
   ```

3. **Implement Dataset Splitter**
   - Split ratio: train 70%, val 20%, test 10%
   - Stratified by defect type (maintain distribution in each split)
   - Deterministic with seed for reproducibility
   - Move/symlink images + masks to split directories

4. **Implement Multi-Resolution Resizer**
   - Primary: 512x512 (native)
   - Optional: 768x768 (for SDXL-compatible downstream)
   - Use `cv2.INTER_LANCZOS4` for downscaling, `cv2.INTER_CUBIC` for upscaling
   - Resize both image and mask identically

5. **Implement Metadata CSV Writer**
   ```csv
   image_id,filename,defect_type,category_id,split,resolution,source_background,mask_filename,seed,lora_strength,controlnet_strength
   1,defect_00001.png,crack,1,train,512,clean_042.png,mask_00001.png,12345,0.7,0.8
   ```

6. **Create YOLO data.yaml**
   ```yaml
   # data.yaml (auto-generated)
   path: C:/DataMint/output/dataset/yolo
   train: train/images
   val: val/images
   test: test/images

   nc: 5
   names: ['crack', 'porosity', 'lack_of_fusion', 'lack_of_penetration', 'slag_inclusion']
   ```

7. **Validate Output**
   - Load COCO JSON with `pycocotools.coco.COCO()` - must not error
   - Spot-check: visualize 10 images with overlaid COCO polygons
   - Load YOLO data.yaml with Ultralytics - must parse correctly
   - Verify image count matches annotation count per split

## Todo List
- [ ] Implement mask-to-COCO polygon converter
- [ ] Implement mask-to-YOLO bbox converter
- [ ] Implement stratified train/val/test splitter
- [ ] Implement multi-resolution resizer
- [ ] Implement metadata CSV writer
- [ ] Auto-generate YOLO data.yaml
- [ ] Validate COCO JSON with pycocotools
- [ ] Validate YOLO format with Ultralytics
- [ ] Visualize 10 annotated samples for spot-check
- [ ] Benchmark: process 20K images in <30min

## Success Criteria
- COCO JSON loads with `pycocotools.coco.COCO()` without errors
- YOLO data.yaml loads with Ultralytics without errors
- Split ratios match 70/20/10 within 1%
- Defect distribution consistent across splits
- Metadata CSV complete for all images
- Processing 20K images in <30min on 44-core CPU

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| Malformed COCO polygons | Medium | Validate contour.size >= 6, filter small artifacts |
| YOLO class ID mismatch | Medium | YOLO is 0-indexed, COCO is 1-indexed - verify mapping |
| Split leakage (same background in train+test) | Low | Split by source background image, not by generated image |
| Large COCO JSON (100K images) | Low | Stream-write JSON, test memory with full dataset |

## Security Considerations
- Output paths validated (no directory traversal)
- Generated dataset does not contain sensitive information

## Next Steps
- Phase 8: QA pipeline validates annotation quality + image realism
- Phase 9: Feed annotated dataset into YOLOv8 training
