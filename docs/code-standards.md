# Code Standards & Development Guidelines - The Data Mint

**Version**: 1.1
**Effective Date**: 2026-02-14
**Applies To**: All Python, Shell, and configuration files in `pipeline/`, `kohya-ss/`, `dataset/`

---

## File Naming & Organization

### Python Files

**Convention**: kebab-case with descriptive name

✓ **Good Examples**:
```
batch-production-main.py       # Main entry point
comfyui-rest-api-client.py     # REST API wrapper
mask-prefetch-worker-pool.py   # Worker pool for parallel tasks
gpu-thermal-monitor.py         # GPU temperature monitoring
crack-mask-generator.py        # Defect-specific generator
post-processing-main.py        # Post-processing entry point
yolo-dataset-builder.py        # Dataset format builder
```

✗ **Avoid**:
```
BatchProduction.py             # PascalCase not used for files
batch_production.py            # Use kebab-case instead
batchProduction.py             # camelCase not used for files
main.py                        # Too generic, not self-documenting
```

**Rationale**: Kebab-case filenames are easy to read in file listings and clearly indicate purpose without requiring file contents inspection.

### File Size Limit

**Target**: <200 lines per Python file

**Rationale**:
- Improves code readability
- Easier LLM context management
- Single responsibility principle
- Faster import cycles

**When to Split**:
- File approaches 200 lines
- Multiple independent classes
- Distinct functional domains

**Example Refactoring**:
```
Before: comfyui-api.py (350 lines)
  - ComfyUIClient class
  - Workflow management
  - Image upload/download
  - Error handling

After:
  - comfyui-rest-api-client.py (180 lines) — API wrapper
  - comfyui-workflow-manager.py (110 lines) — Workflow logic
  - comfyui-error-handling.py (60 lines) — Error recovery
```

### Directory Structure

```
pipeline/
├── batch_manager/           # Phase 6 orchestration
│   ├── __init__.py         # Module exports
│   ├── batch-production-main.py
│   ├── batch-job-scheduler.py
│   ├── comfyui-rest-api-client.py
│   └── [other <200-line modules]
├── mask_generator/          # Phase 5 mask generation
│   ├── __init__.py
│   ├── base-defect-mask-generator.py
│   ├── crack-mask-generator.py
│   └── [other generators]
├── post_processing/         # Phase 7 annotation export
│   ├── __init__.py
│   ├── post-processing-main.py
│   └── [other <200-line modules]
├── qa/                      # Phase 8 QA validation
├── validation/              # Phase 9 YOLOv8 testing
├── launcher/                # Gradio UI (one-click interface)
├── config/                  # YAML/TOML configs
├── comfyui-workflows/       # JSON workflows + YAML prompts
├── tests/                   # Unit & integration tests
├── logs/                    # Runtime logs
└── checkpoints/             # Progress checkpoints
```

### Launcher Module (pipeline/launcher/)

Gradio UI for one-click pipeline orchestration. Follow same conventions + Gradio-specific:

**Gradio-Specific Conventions**:
```python
import gradio as gr

# Use gr.Interface or gr.Blocks for composition
with gr.Blocks(theme=gr.themes.Soft()) as interface:
    gr.Markdown("# Phase Control")

    # Organize into tabs
    with gr.Tabs():
        with gr.TabItem("Control"):
            btn_start = gr.Button("Start Pipeline")
        with gr.TabItem("Progress"):
            progress_bar = gr.Progress()

    # Event handlers: on_click, on_change
    btn_start.click(fn=start_pipeline, inputs=[...], outputs=[...])
```

**State Management**:
- Store phase state in `PipelineOrchestrator` (not in Gradio state)
- Use `gr.State()` only for UI-specific values
- Prefer function composition over shared mutable state

**UI Patterns**:
- Progress indicators: Use `gr.Progress()` component
- Real-time updates: Polling via `gr.Textbox(interactive=False)` (live logs)
- Charts: Integrate matplotlib or plotly via `gr.Plot()`

---

## Python Code Style

### Class & Function Naming

**Classes**: PascalCase
```python
class BatchJobScheduler:          # ✓
class ComfyUIClient:              # ✓
class MaskPrefetcher:             # ✓
class batch_job_scheduler:        # ✗
```

**Functions/Methods**: snake_case
```python
def load_config(path):            # ✓
def batch_production_loop():      # ✓
def get_next_mask():              # ✓
def LoadConfig():                 # ✗
```

**Constants**: UPPER_SNAKE_CASE
```python
MAX_RETRIES = 3                   # ✓
DEFAULT_BATCH_SIZE = 16           # ✓
GPU_THERMAL_MAX = 85              # ✓
max_retries = 3                   # ✗
```

**Private Methods**: Leading underscore
```python
def _validate_connection(self):    # ✓ (internal use)
def validate_connection(self):     # ✓ (public API)
```

### Variable Naming

**Clear & Descriptive**: Always choose clarity over brevity

✓ **Good**:
```python
background_image = load_image(path)
defect_distribution = config["generation"]["defect_distribution"]
mask_prefetch_buffer = deque(maxlen=50)
max_thermal_temp_celsius = 85
```

✗ **Avoid**:
```python
img = load_image(path)             # Too short
dist = config["gen"]["def_dist"]   # Abbreviated
buf = deque(maxlen=50)             # Cryptic
max_t = 85                         # Not descriptive
```

### Type Hints

**Requirement**: Add type hints to all function signatures

```python
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import numpy as np

def load_config(config_path: str) -> Dict:
    """Load batch configuration from YAML file."""
    ...

def get_next_mask(timeout: int = 60) -> Optional[np.ndarray]:
    """Get next pre-generated mask, or None if timeout."""
    ...

def create_annotation(
    image_id: int,
    bbox: Tuple[int, int, int, int],
    category_id: int
) -> Dict:
    """Create COCO annotation dict."""
    ...
```

### Docstrings

**Format**: Google-style docstrings for public APIs

```python
def batch_production_loop(config_path: str, pilot_mode: bool = False) -> None:
    """
    Main batch production loop for synthetic image generation.

    Orchestrates parallel mask generation, ComfyUI queue management,
    thermal monitoring, and checkpoint-based fault tolerance.

    Args:
        config_path: Path to batch-config.yaml (required)
        pilot_mode: If True, generate only 5 images (1 per defect type)

    Returns:
        None

    Raises:
        FileNotFoundError: If config_path does not exist
        ConnectionError: If ComfyUI API unreachable
        RuntimeError: On critical failure (logged for manual review)

    Example:
        >>> batch_production_loop("config/batch-config.yaml", pilot_mode=False)
        # Generates 20K images with progress logging
    """
```

### Error Handling

**Pattern**: Try-catch with specific exception types

```python
import logging
import traceback

logger = logging.getLogger(__name__)

try:
    result = comfyui_client.queue_prompt(workflow, prompts)
except ConnectionError as e:
    logger.error(f"ComfyUI connection failed: {str(e)}")
    # Retry or raise
except TimeoutError as e:
    logger.warning(f"Image generation timeout: {str(e)}")
    # Handle gracefully
except Exception as e:
    logger.critical(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
    raise
```

**No Silent Failures**:
```python
# ✗ Bad
try:
    do_something()
except:
    pass  # Silently swallows all errors

# ✓ Good
try:
    do_something()
except SpecificError as e:
    logger.error(f"Error details: {e}")
    raise  # Re-raise to caller
```

### Imports

**Organization**:
1. Standard library
2. Third-party packages
3. Local modules
4. Blank line between groups

```python
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import yaml
from PIL import Image

from batch_manager import BatchJobScheduler, ComfyUIClient
from mask_generator import get_generator
from config import load_config
```

**Avoid Circular Imports**:
- Use `from . import module` instead of `import module`
- Define shared types in a separate `types.py` if needed

---

## Configuration Management

### YAML Files (batch-config.yaml)

**Structure**: Hierarchical with clear sections

```yaml
# Batch Production Configuration

comfyui:
  host: "172.21.192.1"
  port: 8188
  # Comments explain each setting

generation:
  total_images: 20000
  resolution: 512
  defect_distribution:
    crack: 0.25        # 5000 images (25%)
    porosity: 0.25     # 5000 images

lora_models:
  crack: "xray_crack_lora_r32.safetensors"  # Must match actual filename

thermal:
  enabled: true
  max_temp_celsius: 85   # Pause threshold
  resume_temp_celsius: 75  # Resume threshold
```

**Validation**:
```python
def validate_config(config: Dict) -> bool:
    """Validate required keys and value ranges."""
    required_keys = ["comfyui", "generation", "lora_models"]
    for key in required_keys:
        assert key in config, f"Missing required config key: {key}"

    assert config["generation"]["total_images"] > 0
    assert config["thermal"]["max_temp_celsius"] > 60
    assert sum(config["generation"]["defect_distribution"].values()) == 1.0
    return True
```

### TOML Files (kohya-ss/configs/*.toml)

**Convention**: One config per LoRA type

```toml
# Crack LoRA Training Configuration

[model_arguments]
pretrained_model_name_or_path = "runwayml/stable-diffusion-v1-5"
v2 = false
v_parameterization = false

[train_arguments]
output_dir = "./output/crack"
training_steps = 1000
learning_rate = 1e-4
batch_size = 4
enable_bucket = true

[network_arguments]
network_module = "networks.lora"
network_dim = 32
network_alpha = 16
```

---

## Logging

### Pattern: Use Python logging module

```python
import logging

logger = logging.getLogger(__name__)

def process_image(image_path: str) -> np.ndarray:
    logger.debug(f"Loading image: {image_path}")
    img = cv2.imread(image_path)

    if img is None:
        logger.warning(f"Failed to load image: {image_path}")
        return None

    logger.info(f"Image loaded successfully: {img.shape}")
    return img
```

### Log Levels

| Level | When to Use | Example |
|-------|------------|---------|
| DEBUG | Development info | "Loading config from..." |
| INFO | Normal progress | "Generated 1000 images..." |
| WARNING | Recoverable issue | "SSIM score low (0.82)" |
| ERROR | Non-critical failure | "Failed to load mask, retrying..." |
| CRITICAL | Fatal error | "ComfyUI API unreachable, aborting" |

### Checkpoint & Status Logging

```python
if job_id % 100 == 0:
    logger.info(f"[CHECKPOINT] Generated {job_id} images, elapsed: {elapsed:.1f}s")
    checkpoint_manager.save_checkpoint(job_id, defect_counts, timestamp)
```

---

## Testing

### Unit Tests

**Location**: `pipeline/tests/test_*.py`
**Framework**: pytest

```python
import pytest
from batch_manager import BatchJobScheduler

def test_scheduler_initialization():
    """Test scheduler creates correct defect distribution."""
    scheduler = BatchJobScheduler(
        total_images=1000,
        defect_distribution={"crack": 0.5, "porosity": 0.5},
        backgrounds_dir="/tmp"
    )
    assert scheduler.total_images == 1000

def test_scheduler_respects_distribution():
    """Test scheduler maintains defect distribution."""
    scheduler = BatchJobScheduler(total_images=100, ...)

    counts = {"crack": 0, "porosity": 0}
    for _ in range(100):
        job = scheduler.next_job()
        counts[job["defect_type"]] += 1

    assert counts["crack"] == 50  # Within tolerance
    assert counts["porosity"] == 50
```

**Run Tests**:
```bash
cd pipeline
python -m pytest tests/ -v
```

### Integration Tests

**Location**: `pipeline/tests/test_integration_*.py`

```python
def test_batch_production_pilot(tmp_path):
    """Test 5-image pilot run end-to-end."""
    config = load_config("config/batch-config.yaml")
    config["generation"]["total_images"] = 5

    run_batch_production(config_path, pilot_mode=True)

    # Verify output
    assert (tmp_path / "output/synthetic/crack").exists()
    images = list((tmp_path / "output/synthetic/crack").glob("*.png"))
    assert len(images) == 1
```

### Coverage Target

**Minimum**: 80% line coverage for critical modules
- batch-production-main.py: 85%+
- batch-job-scheduler.py: 80%+
- mask generators: 75%+

**Exclusions**: (ok to skip)
- Error recovery paths
- Logging-only code
- External API mocking

---

## Comments & Documentation

### Inline Comments

**Use Sparingly**: Only for "why", not "what"

```python
# ✓ Good - explains intent
for i, job in enumerate(scheduler.jobs):
    # Rotate through defect types to maintain even distribution
    job["defect_type"] = defect_types[i % len(defect_types)]

# ✗ Bad - just restates code
job_id += 1  # Increment job_id
mask = generate_mask()  # Generate mask
```

### Complex Algorithm Comments

```python
def apply_feathering(mask: np.ndarray, width: int = 5) -> np.ndarray:
    """
    Apply Gaussian blur to defect edges for smooth inpainting.

    The feathering creates a soft transition between the defect region
    and background, preventing hard edges from appearing in inpainted areas.
    Uses normalized Gaussian kernel with sigma = width/2.
    """
    sigma = width / 2.0
    return cv2.GaussianBlur(mask, (width, width), sigma)
```

---

## Performance & Optimization

### Profiling

**When to Profile**: Before optimization claims

```python
import cProfile
import pstats

def profile_batch_generation():
    profiler = cProfile.Profile()
    profiler.enable()

    # Run code to profile
    batch_production_loop(config_path)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions by time
```

### Optimization Guidelines

**Priority Order**:
1. **Correctness** — Always works, produces valid outputs
2. **Readability** — Clear code that others can maintain
3. **Performance** — Speed improvements only if needed

**Avoid Premature Optimization**:
```python
# ✗ Over-optimized, unclear
masks = np.array([m.ravel()[i] for m, i in zip(ms, idx)])

# ✓ Clear and fast enough
masks = [generate_mask(d, seed) for d, seed in jobs]
```

---

## Dependencies & Versioning

### requirements.txt

**Location**: `pipeline/requirements.txt`

```
# Core
opencv-python==4.8.1.78
numpy==1.24.3
pillow==10.0.0
pyyaml==6.0
tqdm==4.66.1

# QA
scikit-image==0.21.0

# Validation
ultralytics==8.0.192
torch==2.0.1
torchvision==0.15.2

# Optional
pycocotools==2.0.6
nvidia-ml-py==11.525.112
```

**Update Policy**:
- Pin major.minor versions (e.g., `==4.8.*`)
- Test before upgrading dependencies
- Document breaking changes in upgrade notes

---

## Git Commit Messages

### Format: Conventional Commits

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Purpose |
|------|---------|
| feat | New feature |
| fix | Bug fix |
| refactor | Code reorganization (no feature change) |
| perf | Performance improvement |
| test | Add/update tests |
| docs | Documentation changes |
| chore | Tooling, deps, cleanup |

### Examples

```
feat(batch-manager): add GPU thermal monitoring

- Monitor GPU temperature every 30 seconds
- Pause generation if temp exceeds 85°C
- Resume when temp drops to 75°C
- Configurable thresholds in batch-config.yaml

Fixes #42
```

```
fix(mask-generator): handle edge case for small images

Previously crashed when image dimension < 50px.
Now skips generation and logs warning.
```

```
docs: update README with 1,097 img/hr throughput data

Based on 500-image pilot run average.
```

---

## Security & Secrets

### API Keys & Credentials

**Never commit**:
- `.env` files (use `.env.example`)
- API keys, tokens, passwords
- Database credentials
- Private config files

**Secure Pattern**:
```python
import os
from dotenv import load_dotenv

load_dotenv(".env.local")  # Local only, not in git

COMFYUI_API_KEY = os.getenv("COMFYUI_API_KEY")
assert COMFYUI_API_KEY, "Missing COMFYUI_API_KEY in .env"
```

### File Permissions

**Secure Files**:
```bash
# Don't commit private configs
echo ".env*" >> .gitignore
echo "*.pem" >> .gitignore
echo "checkpoint-state.json" >> .gitignore
```

---

## Code Review Checklist

Before submitting PR:

- [ ] No syntax errors (run `python -m py_compile`)
- [ ] All type hints present
- [ ] Docstrings for public functions
- [ ] Tests added/updated
- [ ] Test coverage ≥80%
- [ ] No hardcoded paths (use config)
- [ ] Logging at appropriate levels
- [ ] No print() statements (use logger)
- [ ] No trailing whitespace
- [ ] Imports organized & sorted
- [ ] File <200 lines (or justified)

---

## Development Workflow

### Local Setup

```bash
cd /mnt/e/The\ Data\ Mint/pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run linting (if configured)
python -m flake8 --max-line-length=100 batch_manager/ mask_generator/
```

### Before Commit

```bash
# Format code
python -m black batch_manager/ mask_generator/  # Optional

# Run tests
pytest tests/ -v --cov=batch_manager --cov-fail-under=80

# Verify no imports are broken
python -c "from batch_manager import *; from mask_generator import *"
```

---

## Q&A

**Q: Why kebab-case for files?**
A: Consistent, readable in `ls` output, easy for LLM tools to parse intent.

**Q: <200 lines feels restrictive. What if logic is coherent?**
A: Single responsibility is better long-term. If it feels coherent, it can split coherently.

**Q: What if I need to import from parent directory?**
A: Use `sys.path.insert(0, str(Path(__file__).parent.parent))` in entry points only.

**Q: Can I skip tests for small changes?**
A: No. All code changes need test coverage or explicit skip with documentation.

**Q: External library doesn't follow these standards. Do I?**
A: Yes, only for code you write. Adapt external code as needed.

---

**Last Updated**: 2026-02-14
**Version**: 1.1
**Maintainer**: Development Team
