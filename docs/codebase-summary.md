# Codebase Summary - The Data Mint

**Generated**: 2026-03-03
**Repomix Tokens**: 1,861,620 (6.55M characters)
**Total Files**: 5,116
**Source Files**: ~800 (Python, Shell, YAML, Config)

---

## Quick Navigation

- **[Pipeline Core](#pipeline-core)** — Main orchestration & API clients
- **[Batch Manager](#batch-manager)** — Image generation & scheduling
- **[Mask Generation](#mask-generation)** — Procedural defect masks
- **[Post-Processing](#post-processing)** — Annotation conversion
- **[Quality Assurance](#quality-assurance)** — QA validation
- **[Validation](#validation)** — YOLOv8 training & testing
- **[Benchmark Pipeline](./benchmark.md)** — Base model comparison
- **[Launcher UI](#launcher-ui)** — One-click Gradio interface
- **[Tests](#tests)** — Unit & integration tests
- **[Configuration](#configuration)** — YAML/TOML configs
- **[External Services](#external-services)** — Dependencies & integrations

---

## Pipeline Core

### Entry Points & Orchestration

**`pipeline/run-batch-production.sh`** (43 lines)
- Main batch production launcher
- Activates venv, runs batch-production-main.py
- Output logging to `pipeline/logs/batch-production-*.log`

**`pipeline/run-post-processing.sh`** (73 lines)
- Post-processing orchestrator
- Runs mask-to-annotation converter, COCO builder, YOLO builder, splitter
- Supports custom parameters: `--synthetic-dir`, `--output-dir`, `--train-ratio`

**`pipeline/comfyui-api-batch-inpaint-client.py`** (376 lines)
- **Class**: `ComfyUIInpaintClient`
- **Key Methods**:
  - `__init__(host, port)` — Initialize connection
  - `upload_image(image_path)` — Upload image to ComfyUI
  - `queue_prompt(workflow_json, prompt_dict)` — Queue generation job
  - `poll_progress(prompt_id, timeout)` — Wait for completion
  - `get_image(output_dir, workflow)` — Retrieve generated image + metadata
  - `reload_models(model_names)` — Load LoRA into memory
  - `validate_connection()` — Health check

**`pipeline/verify-comfyui-setup.py`** (197 lines)
- Pre-flight checks:
  - ComfyUI API connectivity
  - Required models (SD1.5, ControlNet)
  - LoRA safetensors files
  - Workflow JSON validity
  - Output directory permissions

---

## Batch Manager

**Location**: `pipeline/batch_manager/`
**Purpose**: Phase 6 - Orchestrate 20K image generation with reliability
**Total LOC**: ~1,400

### Core Module

**`batch_manager/__init__.py`** (51 lines)
- Exports: `ComfyUIClient`, `BatchJobScheduler`, `MaskPrefetcher`, `GPUThermalMonitor`, `CheckpointManager`
- Module initialization

**`batch-production-main.py`** (321 lines)
- **Entry point for batch generation**
- **Main Loop**:
  1. Load config (YAML)
  2. Check ComfyUI connection
  3. Initialize scheduler, prefetcher, thermal monitor, checkpoint manager
  4. Resume from checkpoint if exists
  5. Pre-fill mask buffer (50 masks)
  6. Loop until `total_images`:
     - Thermal check (pause if >85°C)
     - Get next job from scheduler
     - Prefetch mask
     - Upload background image
     - Queue ComfyUI prompt
     - Poll for result
     - Save image + metadata + mask
     - Checkpoint every 100 images
  7. Generate final report

- **Key Functions**:
  - `load_config(config_path)` — Parse YAML
  - `save_metadata(job, output_path, config)` — JSON metadata per image
  - `run_batch_production(config_path, pilot_mode)` — Main orchestrator

### Scheduling

**`batch-job-scheduler.py`** (263 lines)
- **Class**: `BatchJobScheduler`
- **Purpose**: Fair distribution across 5 defect types
- **Key Methods**:
  - `__init__(total_images, defect_distribution, backgrounds_dir)` — Initialize queue
  - `next_job()` — Get next job (rotates defect types based on distribution)
  - `get_status()` — Progress tracking
  - `reset()` — Clear queue

- **Data Structure**:
  ```python
  Job = {
    "job_id": int,
    "defect_type": str,  # crack, porosity, inclusion, LOF, undercut
    "seed": int,
    "background_image": Path,
    "lora_model": str
  }
  ```

### ComfyUI API Wrapper

**`comfyui-rest-api-client.py`** (183 lines)
- **Class**: `ComfyUIClient`
- **Base URL**: `http://{host}:{port}/api/`
- **Key Methods**:
  - `upload_image(image_path)` → image name for workflow
  - `queue_prompt(workflow_json, prompt_dict)` → prompt_id
  - `get_prompt_status(prompt_id)` → execution_status
  - `poll_completion(prompt_id, timeout=300)` → (success, images)
  - `get_generated_images()` → list of generated files
  - `reload_lora(lora_name)` → load into vRAM
  - `validate()` → health check (GET /status)

- **Error Handling**:
  - Retry on connection errors (up to 3 attempts)
  - Timeout after 300 seconds per image
  - Clear prompt cache on failure

### Mask Prefetching

**`mask-prefetch-worker-pool.py`** (173 lines)
- **Class**: `MaskPrefetcher`
- **Purpose**: Pre-generate masks while GPU processes previous image
- **Key Methods**:
  - `__init__(mask_generators, workers=8, buffer_size=50)` — Initialize thread pool
  - `prefetch_next(defect_type)` — Queue mask generation
  - `get_next_mask(timeout=60)` → PIL.Image (binary mask)
  - `close()` — Clean up worker threads

- **Implementation**:
  - ThreadPoolExecutor with 8 workers
  - Queue-based synchronization
  - Pre-fills buffer with 50 masks before main loop starts

### GPU Thermal Management

**`gpu-thermal-monitor.py`** (143 lines)
- **Class**: `GPUThermalMonitor`
- **Purpose**: Prevent thermal throttling
- **Key Methods**:
  - `__init__(max_temp=85, resume_temp=75, check_interval=30)` — Initialize thresholds
  - `check_temperature()` → float (celsius)
  - `should_pause()` → bool (temp > max_temp)
  - `can_resume()` → bool (temp < resume_temp)
  - `wait_for_safe()` → block until temp safe

- **Implementation**:
  - Reads `nvidia-smi` output
  - Parses GPU temp from query string
  - Logs pause/resume events
  - Configurable thresholds in batch-config.yaml

### State & Checkpointing

**`checkpoint-state-manager.py`** (109 lines)
- **Class**: `CheckpointManager`
- **Purpose**: Resume on failure
- **Key Methods**:
  - `__init__(checkpoint_dir)` — Set checkpoint directory
  - `save_checkpoint(job_id, defect_counts, timestamp)` → None
  - `load_checkpoint()` → (job_id, defect_counts) or (None, {})
  - `clear_checkpoint()` → Delete checkpoint file

- **Checkpoint Format** (JSON):
  ```json
  {
    "job_id": 1234,
    "timestamp": "2026-01-31 14:25:30",
    "defect_counts": {
      "crack": 2500,
      "porosity": 2500,
      "inclusion": 2000,
      "lack_of_fusion": 1500,
      "undercut": 1500
    }
  }
  ```

- **Recovery**: Checkpoint every 100 images, auto-resume on restart

---

## Mask Generation

**Location**: `pipeline/mask_generator/`
**Purpose**: Phase 5 - Generate procedural defect masks for inpainting
**Total LOC**: ~600

### Base Class

**`base-defect-mask-generator.py`** (58 lines)
- **Class**: `BaseDefectMaskGenerator`
- **Abstract Methods**:
  - `generate(background_shape, roi_mask, seed) → np.ndarray` (binary mask)
  - `get_defect_name() → str`

- **Utilities**:
  - `apply_roi_constraint(mask, roi_mask)` — Keep defects within weld area
  - `feather_edges(mask, feather_width)` — Smooth boundaries
  - `validate_mask(mask)` → bool

### Defect Generators

**`crack-mask-generator.py`** (127 lines)
- **Class**: `CrackMaskGenerator(BaseDefectMaskGenerator)`
- **Algorithm**: Simulates crack propagation via erosion + dilation
  - Random walk on grid
  - Morphological operations for realistic crack geometry
  - Branching for complex cracks
- **Parameters**:
  - Crack width: 2-8 pixels
  - Crack length: 50-200 pixels
  - Branching probability: 0.1-0.3

**`porosity-mask-generator.py`** (94 lines)
- **Class**: `PorosityMaskGenerator(BaseDefectMaskGenerator)`
- **Algorithm**: Circular void clusters
  - Random Gaussian distribution of void centers
  - Overlapping circles with varying radii
  - Merging of adjacent voids
- **Parameters**:
  - Void radius: 3-15 pixels
  - Void count: 10-50 per defect region

**`slag-inclusion-mask-generator.py`** (121 lines)
- **Class**: `SlagInclusionMaskGenerator(BaseDefectMaskGenerator)`
- **Algorithm**: Irregular angular inclusions
  - Convex hull of random points
  - Multiple overlapping polygons
  - Angular/jagged boundaries
- **Parameters**:
  - Inclusion size: 20-60 pixels
  - Inclusion count: 3-10
  - Angularity: 0.5-1.0

**`lack-of-fusion-mask-generator.py`** (91 lines)
- **Class**: `LackOfFusionMaskGenerator(BaseDefectMaskGenerator)`
- **Algorithm**: Linear seams/gaps
  - Horizontal or angled lines
  - Variable thickness (2-6 pixels)
  - Ragged edges via dilation
- **Parameters**:
  - Seam length: 100-300 pixels
  - Seam thickness: 2-6 pixels
  - Angle: 0-45 degrees

**`undercut-mask-generator.py`** (96 lines)
- **Class**: `UndercutMaskGenerator(BaseDefectMaskGenerator)`
- **Algorithm**: Surface grooves along weld edge
  - Linear features at weld boundary
  - Thin, elongated regions
  - Follow ROI perimeter
- **Parameters**:
  - Groove width: 1-4 pixels
  - Groove length: 80-200 pixels

### Utilities

**`feathering-utility.py`** (29 lines)
- **Function**: `apply_feathering(mask, width=5) → np.ndarray`
- Gaussian blur + thresholding for smooth inpainting boundaries

**`weld-roi-constraint.py`** (40 lines)
- **Function**: `generate_roi_mask(image_shape, roi_type='center') → np.ndarray`
- Constrains defects to weld region (center 80% of image)

### Initialization

**`mask_generator/__init__.py`** (51 lines)
- Exports all 5 generators
- Factory method: `get_generator(defect_type) → BaseDefectMaskGenerator`

---

## Post-Processing

**Location**: `pipeline/post_processing/`
**Purpose**: Phase 7 - Convert masks to COCO/YOLO annotations
**Total LOC**: ~880

### Entry Point

**`post-processing-main.py`** (203 lines)
- **Main Loop**:
  1. Parse command-line arguments
  2. Scan `synthetic_dir` for defect subdirectories
  3. For each defect type:
     - Load image + mask pairs
     - Convert masks to annotations
     - Group by split (train/val/test)
  4. Build COCO dataset (annotations + images)
  5. Build YOLO dataset (images + label TXT files)
  6. Generate report

- **Key Functions**:
  - `process_defect_type(defect_type, images_dir, masks_dir, output_dir)` → None
  - `generate_report(stats) → str` (markdown summary)

### Annotation Conversion

**`mask-to-annotation-converter.py`** (154 lines)
- **Class**: `MaskToAnnotationConverter`
- **Key Methods**:
  - `mask_to_bbox(mask) → (x, y, w, h)` — Extract bounding box
  - `mask_to_polygon(mask, simplify=True) → [(x1,y1), (x2,y2), ...]` — Polygon segmentation
  - `create_coco_annotation(image_id, bbox, polygon, category_id) → dict`

- **Features**:
  - Connected component analysis for multi-region defects
  - Douglas-Peucker polygon simplification (epsilon=1.0)
  - Area filtering (min 50 pixels²)

### COCO Format

**`coco-dataset-builder.py`** (160 lines)
- **Class**: `COCODatasetBuilder`
- **Structure**:
  ```python
  {
    "info": {...},
    "licenses": [...],
    "images": [
      {"id": 1, "file_name": "crack_000000.png", "height": 512, "width": 512}
    ],
    "annotations": [
      {
        "id": 1,
        "image_id": 1,
        "category_id": 1,
        "bbox": [x, y, w, h],
        "area": w*h,
        "segmentation": [[x1,y1,x2,y2,...]],
        "iscrowd": 0
      }
    ],
    "categories": [
      {"id": 1, "name": "crack"},
      ...
    ]
  }
  ```
- **Validation**: pycocotools compatibility check

### YOLO Format

**`yolo-dataset-builder.py`** (182 lines)
- **Class**: `YOLODatasetBuilder`
- **Output Structure**:
  ```
  yolo/
  ├── train/images/ ├── labels/
  ├── val/images/ ├── labels/
  ├── test/images/ ├── labels/
  └── data.yaml
  ```
- **Label Format** (one line per defect):
  ```
  <class_id> <x_center> <y_center> <width> <height>
  ```
  (all normalized to [0, 1])
- **data.yaml**:
  ```yaml
  path: /absolute/path
  train: train/images
  val: val/images
  test: test/images
  nc: 5
  names: [crack, porosity, inclusion, lack_of_fusion, undercut]
  ```

### Dataset Splitting

**`dataset-splitter.py`** (185 lines)
- **Class**: `DatasetSplitter`
- **Key Methods**:
  - `stratified_split(image_list, train_ratio, val_ratio) → (train, val, test)`
  - `split_by_defect_type(images, defect_classes, ratios) → splits`

- **Features**:
  - Stratified splitting (maintain defect distribution across splits)
  - Reproducible via seed
  - Per-defect-type balancing

---

## Quality Assurance

**Location**: `pipeline/qa/`
**Purpose**: Phase 8 - Validate synthetic images and annotations
**Total LOC**: ~1,000

### Entry Point

**`qa-pipeline-main.py`** (347 lines)
- **Execution Steps**:
  1. Check SSIM background consistency (500 sample)
  2. Validate COCO/YOLO annotation formats
  3. Check distribution across defect types
  4. Generate visual spot-check gallery
  5. Compile QA report (markdown)
  6. Save results (JSON)

- **Output**:
  - `qa-report.md` — Summary + pass/fail
  - `qa-results.json` — Detailed metrics
  - `spot-check-gallery.html` — Visual inspection HTML

**`annotation-validator.py`** (273 lines)
- **Class**: `AnnotationValidator`
- **Checks**:
  - COCO JSON loadable with pycocotools
  - YOLO data.yaml loadable with Ultralytics
  - Bboxes within image bounds [0, W] × [0, H]
  - Polygon coordinates valid and non-self-intersecting
  - Image counts match annotation counts
  - Category IDs match expected defect types
  - No duplicate annotations

- **Key Methods**:
  - `validate_coco_format(coco_dict) → (valid, errors)`
  - `validate_yolo_format(yolo_dir) → (valid, errors)`
  - `check_bbox_bounds(bbox, img_w, img_h) → bool`

**`ssim-background-checker.py`** (166 lines)
- **Class**: `SSIMBackgroundChecker`
- **Purpose**: Verify inpainting didn't distort background
- **Algorithm**:
  - Compare synthetic image background to original background
  - Mask out defect region (use mask)
  - Compute Structural Similarity Index (SSIM)
  - Thresholds: mean ≥0.90, pass rate ≥85%

- **Key Methods**:
  - `compute_ssim_for_image(synth_img, background_img, defect_mask) → float`
  - `batch_check(synth_dir, sample_size=500) → (mean, std, pass_rate)`

**`visual-spot-check-grid.py`** (244 lines)
- **Class**: `VisualSpotCheckGallery`
- **Purpose**: HTML gallery for manual QA
- **Features**:
  - Random 1-2% sample of dataset
  - Grid layout (5 cols × N rows)
  - Per-image: synthetic + mask + metadata
  - Collapsible defect type sections
  - SSIM score overlay
  - Pass/fail indicators

- **Output**: Single self-contained HTML file (~2-5MB)

---

## Validation

**Location**: `pipeline/validation/`
**Purpose**: Phase 9 - YOLOv8 downstream validation
**Total LOC**: ~790

### Entry Point

**`validation-main.py`** (388 lines)
- **Experiment Design**:
  1. Load real test set (held-out GDXray images in YOLO format)
  2. Generate experiment configs for different synthetic ratios
  3. For each ratio: train YOLOv8, evaluate on real test set
  4. Compare mAP across ratios
  5. Generate validation report (markdown + JSON)

- **Experiments**:
  - Real-only baseline (0% synthetic)
  - 20% synthetic + 80% real
  - 50% synthetic + 50% real
  - 100% synthetic only

- **Output**:
  - `validation-report.md` — Summary + per-class metrics
  - `validation-results.json` — Raw metrics
  - `results/{experiment_name}/weights/best.pt` — Trained models

**`yolo-trainer.py`** (190 lines)
- **Class**: `YOLOv8Trainer`
- **Key Methods**:
  - `__init__(model_size='n', epochs=100, batch_size=16, device='cuda:0')`
  - `train(data_yaml_path, experiment_name) → results`
  - `evaluate(weights_path, test_data_yaml) → metrics`

- **Parameters**:
  - Model size: n (nano), s (small), m (medium) — default 'n'
  - Epochs: typically 100
  - Batch size: 16 (adjust for VRAM)
  - Augmentation: mosaic, mixup, HSV
  - Patience: 50 (early stopping)

**`evaluation-metrics.py`** (208 lines)
- **Class**: `EvaluationMetrics`
- **Key Methods**:
  - `extract_metrics(results_dir) → dict` (mAP, precision, recall)
  - `compare_experiments(results_list) → comparison_df`
  - `get_optimal_ratio(results) → str` (recommended ratio)

- **Metrics Computed**:
  - mAP@0.5 (primary metric)
  - mAP@0.5:0.95 (strict metric)
  - Per-class precision/recall
  - Inference time

---

## Plant HMI

**Location**: `pipeline/plant_hmi/` (phase 1, chỉ đọc) · trang `/plant-hmi/` trên port 7860
- `plant_host_readers.py`: quét /proc tìm tiến trình batch, RAM, tốc độ swap, load
- `plant_production_readers.py`: config YAML, đếm ảnh silo (cache 4 s), checkpoint
- `plant_slow_probes.py`: probe nền single-flight cho nvidia-smi và ComfyUI
- `plant_alarm_rules.py`: `derive_alarms` thuần + `AlarmOnDelay`
- `plant_snapshot_builder.py`, `plant_hmi_routes.py`: snapshot JSON + route FastAPI
- `static/`: HTML + SVG P&ID + JS thuần (Dark Neumorphism, ISA-101)
- `plant_telemetry_emitter.py`: chạy trong tiến trình batch, ghi JSONL enter/exit/job (phase 2)
- `plant_telemetry_collector.py`, `plant_flow_metrics.py`: tail telemetry, tính lưu lượng/KI (thuần)
- `plant_comfyui_readers.py`: tiến trình ComfyUI cục bộ, kiểm tra host trong config có phải máy này
- `static/plant-hmi-particle-layer.js`: hạt theo job; `plant-hmi-event-stream.js`, `plant-hmi-visible-polling.js`
- `plant_historian_store.py`, `plant_historian_sampler.py`, `plant_history_routes.py`: historian SQLite, lấy mẫu 10 s, API history (phase 3)
- `static/plant-hmi-replay-*.js`, `plant-hmi-trend-panel.js`, `plant-hmi-alarm-journal.js`, `plant-hmi-render-panels.js`: phát lại, xu hướng, nhật ký
- `plant_comfyui_progress_{observer,state,routes}.py` + `static/plant-hmi-comfyui-progress-panel.js`: hộp đen ComfyUI (phase 4)
- `plant_setpoints.py`, `plant_setpoint_routes.py` + `static/plant-hmi-setpoint-faceplate.js`: setpoint SP-601 (phase 5)
- `plant_batch_control*.py`, `plant_batch_{config_whitelist,process_ops,audit}.py` + `static/plant-hmi-batch-control*.js`: start/stop (phase 6A)
- `plant_alarm_state.py`, `plant_alarm_state_routes.py` + `static/plant-hmi-alarm-{list,api}.js`: ack/shelve (phase 6B)
- `plant_request_guards.py`: chặn CSRF dùng chung cho mọi route ghi
- Test: `pipeline/tests/test-plant-hmi-{alarm-rules,telemetry,historian,comfyui-progress,setpoints,batch-control,alarm-state}.py`

---

## Launcher UI

**Location**: `pipeline/launcher/`
**Purpose**: One-click Gradio web interface for pipeline orchestration (Phase 6+)
**Total LOC**: ~1,200

### Core Application

**`gradio_launcher_app.py`** (342 lines)
- Main Gradio application entry point
- Tabs: Pipeline Control, Progress, Results, Dataset, Settings
- Real-time progress updates via log polling
- Error categorization and user guidance

**`pipeline_orchestrator.py`** (268 lines)
- **Class**: `PipelineOrchestrator`
- Phase management state machine
- Validates phase dependencies before execution
- Supports: pilot mode, dry-run, resume from checkpoint

**`phase_runner.py`** (194 lines)
- **Class**: `PhaseRunner`
- Subprocess management for phase scripts
- Captures stdout/stderr for real-time logging
- Timeout handling (configurable per phase)

**`progress_tracker.py`** (187 lines)
- **Class**: `ProgressTracker`
- Parses log files for progress metrics
- Extracts: job count, throughput, GPU temp, errors
- Updates UI in real-time (every 2 seconds)

### UI Components

**`ui_progress_panel.py`** (156 lines)
- Progress bar, current phase, throughput graph
- Temperature gauge (85°C threshold marked)
- Checkpoint status display

**`ui_results_panel.py`** (142 lines)
- Post-execution results summary
- QA metrics display (SSIM, annotation count)
- Validation mAP comparison chart

**`ui_dataset_panel.py`** (128 lines)
- Dataset statistics (image count, class distribution)
- Download buttons for COCO/YOLO files
- Gallery preview (random 10 samples)

### Utilities

**`error_handler.py`** (109 lines)
- **Class**: `ErrorHandler`
- Categorizes errors: API, storage, memory, thermal
- Suggests mitigations and recovery steps
- Logs with traceback for debugging

**`launcher_utils.py`** (94 lines)
- GPU availability check (nvidia-smi)
- ComfyUI API connectivity ping
- Disk space validation

**`config_preset_manager.py`** (87 lines)
- **Class**: `PresetManager`
- Presets: pilot (500 img), standard (20K img), full (100K img)
- Loads/saves custom configs to YAML

**`demo_pipeline_runner.py`** (73 lines)
- Demo mode for testing without GPU
- Simulates phase execution with mock data
- Useful for UI/UX validation

### Features

- **One-click operation**: Select preset, click "Start", monitor progress
- **Real-time dashboards**: Progress, temperature, throughput graphs
- **Error recovery**: Auto-suggest mitigations, resume option
- **Preset configs**: pilot (500), standard (20K), full (100K)
- **Demo mode**: Test UI without GPU
- **Export**: Download COCO/YOLO datasets after Phase 7

---

## Tests

**Location**: `pipeline/tests/`
**Framework**: pytest
**Total LOC**: ~850

### Unit Tests

**`test-mask-generator-unit-tests.py`** (234 lines)
- Tests for all 5 defect generators
- Validates: mask shape, defect coverage, ROI constraints
- Coverage: >80%

**`test-comfyui-workflow-validation.py`** (156 lines)
- Validates workflow JSON structure
- Checks prompt injection
- Tests API connection mocking

**`test-config-preset-manager.py`** (128 lines)
- Config loading, validation
- Preset switching
- Custom parameter merging

**`test-progress-tracker.py`** (104 lines)
- Log parsing accuracy
- Progress extraction metrics
- Error detection in logs

**`test-error-handler.py`** (95 lines)
- Error categorization
- Mitigation suggestion accuracy
- Recovery step validation

### Integration Tests (planned)

- `test-batch-production-pilot.py` — Full 5-image run
- `test-post-processing-pipeline.py` — Mask→COCO/YOLO conversion
- `test-qa-pipeline.py` — QA validation chain
- `test-validation-pipeline.py` — YOLOv8 training

### Test Execution

```bash
cd pipeline
pytest tests/ -v --cov=batch_manager,mask_generator,launcher --cov-report=html
```

---

## Configuration

**`pipeline/config/batch-config.yaml`** (68 lines)

| Key | Default | Description |
|-----|---------|-------------|
| `comfyui.host` | 172.21.192.1 | ComfyUI API host |
| `comfyui.port` | 8188 | ComfyUI API port |
| `generation.total_images` | 20000 | Images to generate |
| `generation.resolution` | 512 | Output resolution (px) |
| `generation.defect_distribution` | crack: 0.25, ... | Per-defect percentages |
| `generation.background_filter` | mean ≥ 140 | Brightness threshold for clean images |
| `lora_models.*` | xray_*_lora_r32.safetensors | LoRA filenames |
| `sampler.steps` | 20 | Diffusion steps |
| `sampler.cfg` | 7.0 | Classifier-free guidance |
| `sampler.denoise_crack` | 1.0 | Full latent freedom for cracks |
| `sampler.denoise_other` | 0.7 | Preserve background for other defects |
| `thermal.max_temp_celsius` | 85 | Pause threshold |
| `thermal.resume_temp_celsius` | 75 | Resume threshold |
| `reliability.checkpoint_interval` | 100 | Checkpoints per N images |
| `performance.mask_prefetch_workers` | 8 | CPU worker threads |

**`pipeline/config/mask-config.yaml`** (optional)
- Per-defect generator parameters
- Not yet implemented (using hardcoded defaults in generators)

**`kohya-ss/configs/*.toml`** (5 files, ~60 lines each)
- LoRA training hyperparameters
- Files:
  - `crack-lora-training-config.toml`
  - `porosity-lora-training-config.toml`
  - `inclusion-lora-training-config.toml`
  - `lack-of-fusion-lora-training-config.toml`
  - `undercut-lora-training-config.toml`

**`pipeline/comfyui-workflows/`**
- `sd15-lora-controlnet-inpaint-single-defect-workflow.json` — Workflow JSON
- `defect-type-prompt-templates.yaml` — Prompts per defect type

---

## External Services

### ComfyUI API Integration

**Endpoint**: `http://172.21.192.1:8188/api/`

**Key Routes**:
- `GET /status` — Health check
- `POST /upload/image` — Upload background image
- `POST /prompt` — Queue generation job
- `GET /history/{prompt_id}` — Job status & output

**Workflow JSON**:
- Nodes: Load Model, Load LoRA, Load ControlNet, KSampler, VAE Decode, Save Image
- Prompts: Injected per defect type (loaded from YAML)
- Outputs: Generated PNG + metadata

### LoRA Models

**Storage**: `/mnt/e/The Data Mint/kohya-ss/output/{defect_type}/`

| Model | Filename | Size | Status |
|-------|----------|------|--------|
| Crack | xray_crack_lora_r32.safetensors | ~37 MB | ✓ Trained |
| Porosity | xray_porosity_lora_r32.safetensors | ~37 MB | ✓ Trained |
| Inclusion | xray_inclusion_lora_r32.safetensors | ~37 MB | ✓ Trained |
| LOF | xray_lof_lora_r32.safetensors | ~37 MB | ✓ Trained |
| Undercut | xray_undercut_lora_r32.safetensors | ~37 MB | ✓ Trained |

---

## Key Metrics & Performance

| Component | Throughput | Bottleneck |
|-----------|-----------|-----------|
| Mask Generation | ~100 masks/s | CPU (not limiting) |
| ComfyUI Generation | ~1,097 img/hr | GPU (RTX 3090) |
| Post-Processing | ~450 img/s | I/O |
| QA (SSIM) | ~1 img/s | CPU (scikit-image) |
| YOLOv8 Training | ~50 epochs/hr | GPU (batch_size=16) |

---

## File Organization Strategy

**Conventions**:
- Kebab-case filenames: `batch-production-main.py`, `comfyui-rest-api-client.py`
- Module size: <200 lines per file (single responsibility)
- Tests: `pipeline/tests/` (currently 3 test files)
- Logs: `pipeline/logs/batch-production-*.log`

**Imports**:
- Relative imports within modules: `from batch_manager import ComfyUIClient`
- Absolute imports for dependencies: `import yaml`, `import numpy`
- No circular dependencies

---

## Dependencies & Versions

**Python**: 3.8+

**Core**:
- opencv-python 4.8.1
- numpy 1.24
- pillow 10.1
- pyyaml 6.0
- tqdm 4.66

**QA**:
- scikit-image 0.21 (SSIM)

**Validation**:
- ultralytics 8.0+ (YOLOv8)
- torch 2.0+ (GPU inference)
- torchvision 0.15+ (image ops)

**Optional**:
- pycocotools 2.0.6 (COCO validation)
- nvidia-ml-py 11.0+ (GPU temp)

---

**Benchmark Pipeline Section Added**: 2026-03-03
- 6 models: baseline SD 1.5 + 5 challengers (medxray, realvis, absreal, cyberreal, medxray-direct)
- 500 deterministic test images per model (100 per defect type)
- FID/SSIM/Sharpness metrics + HTML report
- Rev01-Rev06 revisions completed (LoadImage MASK alpha bug fix, crack color consistency, background filtering)
- Composite ranking: FID (40%) + SSIM (40%) + Sharpness (20%)

**Last Updated**: 2026-03-03
**Version**: 1.2
**Total Lines of Code**: ~10,200 (pipeline directory including launcher, tests, & benchmark)
