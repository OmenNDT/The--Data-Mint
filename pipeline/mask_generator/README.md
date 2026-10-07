# Mask Generator Module

Procedural binary mask generators for weld defect synthesis.

## Overview

Generates binary masks for 10 weld defect types with realistic morphologies:

| # | Defect Class | Morphology | Generator |
|---|---|---|---|
| 1 | **Crack** | Jagged random-walk polylines (1-4px, branching) | `CrackMaskGenerator` |
| 2 | **Porosity** | 1-4 organic gaussian-noise blobs | `PorosityMaskGenerator` |
| 3 | **Clustered Porosity** | 8-25 pores in Rayleigh-scattered cluster | `ClusteredPorosityMaskGenerator` |
| 4 | **Linear Porosity** | 5-15 pores in horizontal chain with jitter | `LinearPorosityMaskGenerator` |
| 5 | **Lack of Fusion** | Flat band OFF-CENTER (5-12px, parallel edges) | `LackOfFusionMaskGenerator` |
| 6 | **Lack of Penetration** | Thin near-continuous line AT CENTERLINE (2-4px) | `LackOfPenetrationMaskGenerator` |
| 7 | **Slag Inclusion** | Single irregular blob (Gaussian noise threshold) | `SlagInclusionMaskGenerator` |
| 8 | **Linear Slag Inclusion** | 3-6 slag blobs in horizontal row | `LinearSlagInclusionMaskGenerator` |
| 9 | **Metallic Inclusion** | Single compact dense blob (sharper edges) | `MetallicInclusionMaskGenerator` |
| 10 | **Elongated Cavity** | Irregular wormhole (quadratic bezier + asymmetric width) | `ElongatedCavityMaskGenerator` |

Each generator produces:
1. **Binary mask** (0 or 255): Sharp edges for ground truth annotation
2. **Feathered mask** (0-255): Gaussian-blurred edges for ControlNet inpainting

## Quick Start

```python
from mask_generator import (
    CrackMaskGenerator,
    ClusteredPorosityMaskGenerator,
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
# Unit tests
python3 tests/test-mask-generator-unit-tests.py

# Visual validation + benchmark
python3 test-mask-generators-visual.py
```

## Architecture

```
mask_generator/
├── base-defect-mask-generator.py           # Abstract base class
├── crack-mask-generator.py                 # Crack morphology
├── porosity-mask-generator.py              # Porosity (isolated)
├── clustered-porosity-mask-generator.py    # Clustered porosity
├── linear-porosity-mask-generator.py       # Linear porosity
├── lack-of-fusion-mask-generator.py        # Lack of fusion
├── lack-of-penetration-mask-generator.py   # Lack of penetration
├── slag-inclusion-mask-generator.py        # Slag inclusion
├── linear-slag-inclusion-mask-generator.py # Linear slag inclusion
├── metallic-inclusion-mask-generator.py    # Metallic inclusion
├── elongated-cavity-mask-generator.py      # Elongated cavity
├── weld-roi-constraint.py                  # ROI utilities
└── feathering-utility.py                   # Edge smoothing
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
