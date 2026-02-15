# Phase 2: Config Preset Manager

## Context Links
- [Batch Config](../../pipeline/config/batch-config.yaml)
- [Code Standards](../../docs/code-standards.md)
- [Research: Training Patterns](research/researcher-02-training-launcher-patterns.md)

## Overview
- **Priority**: P1 (required before UI)
- **Status**: Pending
- **Effort**: 2h
- **Description**: Manage tiered config presets (Pilot/Standard/Full) that map to the existing `batch-config.yaml` structure. Presets encode recommended settings; expert mode allows per-field overrides.

## Key Insights
<!-- Updated: Validation Session 1 - Expanded presets to cover all 9 phases + max parameter tuning -->
- Existing `batch-config.yaml` has 68 lines covering generation tunables
- kohya-ss TOML configs have LoRA training params (rank, alpha, lr, epochs, batch_size)
- User wants **maximum parameter fine-tuning** — expose ALL tunables, not just main knobs
- Presets cover full pipeline: LoRA training + generation + validation params
- Vietnamese descriptions for all parameters
- Presets should show estimated wall-clock time based on known throughput (~1,097 img/hr gen, ~50 epochs/hr training, ~2-3h per LoRA model)

## Requirements

### Functional
- FR1: Three built-in presets: Pilot (500 imgs, ~30min), Standard (5K, ~4h), Full (20K, ~18h)
- FR2: Each preset produces a complete config dict consumable by `PipelineOrchestrator`
- FR3: Expert override of individual params (total_images, epochs, batch_size, model_size, ratios)
- FR4: Load/save custom presets as YAML files
- FR5: Estimate total runtime for any config
- FR6: Validate config before passing to orchestrator

### Non-Functional
- NFR1: Presets stored as YAML in `pipeline/config/presets/`
- NFR2: < 200 lines per file

## Architecture

```
ConfigPresetManager
├── __init__(base_config_path, presets_dir)
├── list_presets() -> List[PresetInfo]
├── load_preset(name) -> dict
├── apply_overrides(preset, overrides) -> dict
├── estimate_runtime(config) -> RuntimeEstimate
├── validate_config(config) -> List[str]  # returns errors
└── save_custom_preset(name, config) -> Path
```

### Preset YAML Format
```yaml
# pipeline/config/presets/pilot.yaml
name: "Pilot"
description: "Quick test run - 500 images, fast validation"
generation:
  total_images: 500
validation:
  epochs: 20
  model_size: "n"
  batch_size: 16
  ratios: [0.0, 0.5, 1.0]
phases_to_run: [6, 7, 8, 9]
```

### Config Resolution Order
1. Load `batch-config.yaml` (base defaults)
2. Overlay preset values (override generation/validation sections)
3. Apply user overrides from UI (highest priority)

## Related Code Files

### Files to Create
- `pipeline/launcher/config-preset-manager.py` (~160 lines) - PresetManager class
- `pipeline/config/presets/pilot.yaml` (~25 lines)
- `pipeline/config/presets/standard.yaml` (~25 lines)
- `pipeline/config/presets/full.yaml` (~25 lines)

### Existing Files Referenced (read-only)
- `pipeline/config/batch-config.yaml` - Base config template

## Implementation Steps

1. Create `pipeline/config/presets/` directory
2. Create three preset YAML files:
   - `pilot.yaml`: 500 images, 20 epochs, nano model, 3 ratios
   - `standard.yaml`: 5,000 images, 50 epochs, small model, 4 ratios
   - `full.yaml`: 20,000 images, 100 epochs, nano model, 6 ratios
3. Create `config-preset-manager.py` with:
   - `PresetInfo` dataclass: `name`, `description`, `estimated_minutes`
   - `RuntimeEstimate` dataclass: `generation_minutes`, `post_processing_minutes`, `qa_minutes`, `validation_minutes`, `total_minutes`
   - `ConfigPresetManager` class
4. Implement `load_preset(name)`:
   - Read base config from `batch-config.yaml`
   - Read preset YAML
   - Deep-merge preset over base (preset values win)
   - Return complete config dict
5. Implement `apply_overrides(config, overrides)`:
   - Accept flat dict of user overrides (e.g., `{"total_images": 1000}`)
   - Map flat keys to nested config paths
   - Return merged config
6. Implement `estimate_runtime(config)`:
   - Generation: `total_images / 1097 * 60` minutes
   - Post-processing: `total_images / 450 / 60` minutes (negligible)
   - QA: ~10 minutes fixed
   - Validation: `len(ratios) * epochs / 50 * 60` minutes
   - Return `RuntimeEstimate` with per-phase and total
7. Implement `validate_config(config)`:
   - Check required keys exist
   - Check `total_images > 0`
   - Check defect distribution sums to 1.0
   - Check `epochs > 0`, `batch_size > 0`
   - Return list of error strings (empty = valid)

## Todo List
- [ ] Create `pipeline/config/presets/` directory
- [ ] Write `pilot.yaml` preset
- [ ] Write `standard.yaml` preset
- [ ] Write `full.yaml` preset
- [ ] Implement `PresetInfo` and `RuntimeEstimate` dataclasses
- [ ] Implement `ConfigPresetManager.__init__`
- [ ] Implement `list_presets()`
- [ ] Implement `load_preset()`
- [ ] Implement `apply_overrides()`
- [ ] Implement `estimate_runtime()`
- [ ] Implement `validate_config()`
- [ ] Implement `save_custom_preset()` (optional, nice-to-have)

## Success Criteria
- `list_presets()` returns 3 presets with name, description, estimated time
- `load_preset("pilot")` returns complete config dict with 500 images
- `apply_overrides()` correctly merges user changes
- `estimate_runtime()` returns reasonable time estimates
- `validate_config()` catches invalid configs (missing keys, bad values)

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Config schema drift between base YAML and presets | Medium | Validate merged config against expected schema |
| Runtime estimates wildly inaccurate | Low | Show "estimated" label; based on RTX 3090 benchmarks |
| User creates invalid override combos | Medium | `validate_config()` catches before run |

## Security Considerations
- Preset YAML files are local-only, no remote loading
- User custom presets saved to local `presets/` dir only
- No secrets in preset files

## Next Steps
- Phase 3 (Gradio UI) displays preset dropdown and override fields
- Phase 1 (Orchestrator) consumes the config dict produced here
