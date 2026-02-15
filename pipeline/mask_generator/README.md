# Mask Generator Module

Procedural binary mask generators for weld defect synthesis.

## Overview

Generates binary masks for 5 weld defect types with realistic morphologies:
- **Crack**: Jagged linear patterns (random walk polylines)
- **Porosity**: Clustered gas pores (Rayleigh-distributed circles)
- **Lack of Fusion**: Linear indications along fusion boundaries
- **Slag Inclusion**: Irregular organic blobs
- **Undercut**: Edge-aligned linear grooves

Each generator produces:
1. **Binary mask** (0 or 255): Sharp edges for ground truth annotation
2. **Feathered mask** (0-255): Gaussian-blurred edges for ControlNet inpainting

## Quick Start

```python
from mask_generator import (
    CrackMaskGenerator,
    create_weld_roi_mask,
    apply_weld_roi
)

# Create generator
generator = CrackMaskGenerator(seed=42)

# Generate masks
binary_mask, feathered_mask = generator.generate()

# Apply weld ROI constraint
roi_mask = create_weld_roi_mask(512, 512, zone_height_pct=0.4)
constrained = apply_weld_roi(binary_mask, roi_mask)
```

## Configuration

See `../config/mask-config.yaml` for all parameters:
- Defect size ranges
- Position constraints
- Orientation variations
- Weld ROI dimensions

## Performance

- Average: **1573 masks/sec** on CPU (Dual Xeon E5-2696v4)
- All generators: >700 masks/sec minimum
- Reproducible with fixed seed

## Testing

```bash
# Unit tests (34 tests)
python3 tests/test-mask-generator-unit-tests.py

# Visual validation + benchmark
python3 test-mask-generators-visual.py
```

## Architecture

```
mask_generator/
├── base-defect-mask-generator.py    # Abstract base class
├── crack-mask-generator.py          # Crack morphology
├── porosity-mask-generator.py       # Porosity morphology
├── lack-of-fusion-mask-generator.py # LoF morphology
├── slag-inclusion-mask-generator.py # Slag/inclusion morphology
├── undercut-mask-generator.py       # Undercut morphology
├── weld-roi-constraint.py           # ROI utilities
└── feathering-utility.py            # Edge smoothing
```

## Usage in Pipeline

```python
# 1. Generate mask
mask_gen = PorosityMaskGenerator(seed=iteration_idx, **config['porosity'])
binary, feathered = mask_gen.generate()

# 2. Apply ROI
roi = create_weld_roi_mask(**config['weld_roi'])
final_binary = apply_weld_roi(binary, roi)
final_feathered = apply_weld_roi(feathered, roi)

# 3. Use in ComfyUI workflow
# final_feathered -> ControlNet inpainting mask input
# final_binary -> Save as ground truth annotation
```

## Dependencies

- numpy >= 1.23
- opencv-python-headless >= 4.8
- scipy >= 1.15
- pyyaml >= 6.0
