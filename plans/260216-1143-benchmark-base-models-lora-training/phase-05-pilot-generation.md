# Phase 5: Pilot Generation

## Context Links
- [Plan Overview](plan.md)
- [Phase 3: Pipeline Integration](phase-03-pipeline-integration.md)
- [Phase 4: Training Execution](phase-04-lora-training-execution.md)
- Batch production script: `pipeline/batch_manager/batch-production-main.py`
- Benchmark batch configs: `pipeline/config/benchmark/{model}-batch-config.yaml`

## Overview
- **Priority**: P1 (feeds Phase 6 evaluation)
- **Status**: complete
- **Effort**: 3h (mostly GPU wall-clock; ~30min scripting)
- **Description**: Generate 100 images per defect type per model (500 per model, 2500 total including baseline) using deterministic seeds for fair comparison.

## Key Insights
- Must use IDENTICAL seeds across all 5 models (baseline + 4 challengers) for fair comparison
- Same backgrounds, same masks, same prompts -- only checkpoint + LoRA differ
- Existing `batch-production-main.py` uses `BatchJobScheduler` which randomizes seeds and backgrounds
- Need benchmark runner that fixes seeds and iterates models
- 500 images per model at ~3s/image = ~25 min per model = ~2h total

## Requirements

### Functional
- Generate 100 images per defect x 5 models = 2500 images total
- Deterministic seeds: same 100 seeds per defect across all models
- Same background images per seed across all models
- Output organized: `output/benchmark/{model_short}/{defect_type}/`
- Save generation metadata (seed, model, prompt, timing) per image

### Non-functional
- Script runs all 5 models sequentially (single GPU)
- Resume support: skip already-generated images
- Log progress and errors

## Architecture

### Output Structure
```
output/benchmark/
├── baseline/
│   ├── crack/
│   │   ├── crack_000001.png
│   │   ├── crack_000002.png
│   │   └── ... (100 images)
│   ├── porosity/ (100 images)
│   ├── inclusion/ (100 images)
│   ├── lack_of_fusion/ (100 images)
│   └── undercut/ (100 images)
├── medxray/
│   ├── crack/ (100 images, same seeds as baseline)
│   └── ...
├── realvis/ ...
├── absreal/ ...
├── cyberreal/ ...
└── seeds.json        # deterministic seed manifest
```

### Seed Manifest (`seeds.json`)
```json
{
  "crack": [42, 137, 256, 1024, ...],       // 100 fixed seeds
  "porosity": [43, 138, 257, 1025, ...],     // 100 fixed seeds
  "inclusion": [44, 139, 258, 1026, ...],
  "lack_of_fusion": [45, 140, 259, 1027, ...],
  "undercut": [46, 141, 260, 1028, ...]
}
```

### Approach Options

**Option A (Recommended): Benchmark Runner Script**
- New Python script that directly uses `BatchJobScheduler` with fixed seeds
- Override `_build_job_list()` to use deterministic seeds
- Loop through 5 batch configs (baseline + 4 benchmark)

**Option B: Modify batch configs with fixed seed list**
- Not supported by current `BatchJobScheduler` (uses `random.randint`)

Go with Option A.

## Related Code Files
- **Read**: `pipeline/batch_manager/batch-production-main.py` (understand production entry point)
- **Read**: `pipeline/batch_manager/batch-job-scheduler.py` (job/seed logic)
- **Read**: `pipeline/config/benchmark/{model}-batch-config.yaml` (from Phase 3)
- **Create**: `pipeline/benchmark/run-benchmark-generation.py`
- **Create**: `output/benchmark/seeds.json`

## Implementation Steps

### Step 1: Generate Deterministic Seed Manifest

```python
import json
import random

random.seed(12345)  # fixed master seed for reproducibility

DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
SEEDS_PER_DEFECT = 100

seeds = {}
for defect in DEFECTS:
    seeds[defect] = [random.randint(0, 2**32 - 1) for _ in range(SEEDS_PER_DEFECT)]

with open("output/benchmark/seeds.json", "w") as f:
    json.dump(seeds, f, indent=2)
```

### Step 2: Create `pipeline/benchmark/run-benchmark-generation.py`

Core logic:

```python
"""
Benchmark Image Generation Runner.

Generates images for all 5 models using identical seeds for fair comparison.
Uses existing BatchJobScheduler with overridden seeds.
"""

import json
import yaml
import sys
import time
import logging
from pathlib import Path

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

from batch_manager.batch_job_scheduler import BatchJobScheduler

MODELS = ["baseline", "medxray", "realvis", "absreal", "cyberreal"]

def get_batch_config_path(model: str) -> Path:
    """Return batch config path for given model."""
    if model == "baseline":
        return PROJECT_ROOT / "pipeline" / "config" / "batch-config.yaml"
    return PROJECT_ROOT / "pipeline" / "config" / "benchmark" / f"{model}-batch-config.yaml"
```

Key methods in the script:

1. **Load seed manifest** from `output/benchmark/seeds.json`

2. **For each model**, load its batch config:
   - For baseline: use production `batch-config.yaml` but override `defect_distribution` to equal (0.2 each) and `total_images` to 500
   - For benchmark models: use `pipeline/config/benchmark/{model}-batch-config.yaml`

3. **Override job list seeds**: After `BatchJobScheduler.__init__()`, replace `self.jobs` with fixed-seed jobs:
   ```python
   def create_fixed_seed_jobs(seeds_manifest: dict) -> list:
       jobs = []
       for defect, seed_list in seeds_manifest.items():
           for i, seed in enumerate(seed_list):
               jobs.append({
                   "job_id": len(jobs),
                   "defect_type": defect,
                   "seed": seed,
                   "background_image": None,
                   "status": "pending"
               })
       return jobs
   ```

4. **Assign fixed backgrounds**: Use sorted background list and assign deterministically by index:
   ```python
   bg_images = sorted(scheduler.background_images)
   for job in jobs:
       job["background_image"] = bg_images[job["job_id"] % len(bg_images)]
   ```

5. **Submit to ComfyUI** using existing `batch-production-main.py` logic:
   - Upload background + mask
   - Call `scheduler.build_workflow(job, bg_filename, mask_filename)`
   - Submit workflow via WebSocket
   - Save output image to `output/benchmark/{model}/{defect}/`

6. **Track progress**: Skip images where output file already exists

### Step 3: Handle Baseline Model

For baseline, need to either:
- Use production `batch-config.yaml` with overridden settings
- Or create `pipeline/config/benchmark/baseline-batch-config.yaml` pointing to production checkpoint + production LoRAs

**Recommended**: Create `baseline-batch-config.yaml` that mirrors production but with:
- `total_images: 500`
- Equal defect distribution (0.2 each)
- `output_base_dir: output/benchmark/baseline`

### Step 4: Run Generation

```bash
# Generate for all 5 models sequentially
python3 pipeline/benchmark/run-benchmark-generation.py --all

# Or one model at a time
python3 pipeline/benchmark/run-benchmark-generation.py --model medxray
python3 pipeline/benchmark/run-benchmark-generation.py --model baseline
```

### Step 5: Verify Output Completeness

```bash
# Check image counts per model per defect
for model in baseline medxray realvis absreal cyberreal; do
    echo "=== $model ==="
    for defect in crack porosity inclusion lack_of_fusion undercut; do
        count=$(ls output/benchmark/$model/$defect/*.png 2>/dev/null | wc -l)
        echo "  $defect: $count/100"
    done
done
```

Expected: all 25 cells show 100/100.

### Step 6: Save Generation Metadata

Per model, save `output/benchmark/{model}/generation-metadata.json`:
```json
{
  "model": "medxray",
  "checkpoint": "checkpoints/benchmark/medical-xray-sd15.safetensors",
  "vae": "vae/sd-vae-ft-mse.safetensors",
  "total_images": 500,
  "generation_time_seconds": 1500,
  "avg_time_per_image": 3.0,
  "defects": {
    "crack": {"count": 100, "seeds": [42, 137, ...]},
    "porosity": {"count": 100, "seeds": [43, 138, ...]}
  }
}
```

## Todo List
- [ ] Generate deterministic seed manifest (`seeds.json`)
- [ ] Create `baseline-batch-config.yaml`
- [ ] Implement `run-benchmark-generation.py`
- [ ] Test with single model/defect (medxray/crack, 10 images)
- [ ] Run full generation: baseline (500 images)
- [ ] Run full generation: medxray (500 images)
- [ ] Run full generation: realvis (500 images)
- [ ] Run full generation: absreal (500 images)
- [ ] Run full generation: cyberreal (500 images)
- [ ] Verify 2500 total images (25 x 100)
- [ ] Save generation metadata per model

## Success Criteria
- 2500 images total: 5 models x 5 defects x 100 images
- Same seeds used across all models (verifiable from metadata)
- Same backgrounds assigned per seed across all models
- All images are 512x512 grayscale
- No blank/corrupted images (spot check 5 per model)
- Generation metadata saved per model

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| ComfyUI crashes mid-generation | Medium | Resume support (skip existing); restart and re-run |
| LoRA not found in ComfyUI | High | Verify all 20 LoRAs deployed before starting (Phase 4 step 6) |
| External VAE node missing in ComfyUI | Medium | Pre-test workflow manually in ComfyUI UI |
| Background assignment varies across models | Low | Deterministic sort + modulo assignment ensures consistency |
| Some models produce blank/black images | Medium | Spot-check first 10 per model; abort early if broken |

## Next Steps
- Phase 6: Feed 2500 images into evaluation pipeline (SSIM, FID, sharpness)
- Keep `seeds.json` for reproducibility -- can regenerate exact same images later
