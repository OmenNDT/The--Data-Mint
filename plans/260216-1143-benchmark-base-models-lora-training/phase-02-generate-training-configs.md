# Phase 2: Generate Training Configs

## Context Links
- [Plan Overview](plan.md)
- [Phase 1: Download](phase-01-download-and-setup.md)
- [Research: Kohya Multi-Model Training](research/researcher-01-kohya-multi-model-training.md)
- Existing template: `kohya-ss/configs/crack-lora-training-config.toml`

## Overview
- **Priority**: P1 (blocks Phase 4 training)
- **Status**: complete
- **Effort**: 3h
- **Description**: Generate 20 TOML configs (5 defects x 4 base models) from existing configs as templates. Keep identical hyperparams for fair comparison.

## Key Insights
- Current 5 TOML configs differ ONLY in: `train_data_dir`, `reg_data_dir`, `output_dir`, `output_name`, `log_prefix`, `sample_prompts`
- `pretrained_model_name_or_path`, hyperparams (LR, rank, alpha, batch) are identical across all 5
- For fair benchmarking: keep ALL hyperparams identical, only change `pretrained_model_name_or_path` and output naming
- Save intermediate checkpoints at epochs 10, 15, 20 via `save_every_n_epochs = 5` (captures 10, 15, 20)

## Requirements

### Functional
- Read existing 5 TOML configs as templates
- For each of 4 base models, generate 5 TOML configs with modified paths
- Output naming convention: `xray_{defect}_{model_short}_lora_r32`
- Config path pattern: `kohya-ss/configs/benchmark/{model_short}/{defect}-lora-training-config.toml`
- DO NOT modify existing production configs

### Non-functional
- Script is idempotent (safe to re-run)
- Validate generated TOMLs parse correctly
- Print summary of generated configs

## Architecture

### Config Directory Structure
```
kohya-ss/configs/
├── crack-lora-training-config.toml              # existing (unchanged)
├── porosity-lora-training-config.toml            # existing (unchanged)
├── inclusion-lora-training-config.toml           # existing (unchanged)
├── lack_of_fusion-lora-training-config.toml      # existing (unchanged)
├── undercut-lora-training-config.toml            # existing (unchanged)
└── benchmark/
    ├── medxray/
    │   ├── crack-lora-training-config.toml
    │   ├── porosity-lora-training-config.toml
    │   ├── inclusion-lora-training-config.toml
    │   ├── lack_of_fusion-lora-training-config.toml
    │   └── undercut-lora-training-config.toml
    ├── realvis/
    │   ├── crack-lora-training-config.toml
    │   └── ... (5 files)
    ├── absreal/
    │   └── ... (5 files)
    └── cyberreal/
        └── ... (5 files)
```

### Output LoRA Directory Structure
```
kohya-ss/output/benchmark/
├── medxray/
│   ├── crack/
│   │   └── xray_crack_medxray_lora_r32.safetensors
│   ├── porosity/
│   │   └── xray_porosity_medxray_lora_r32.safetensors
│   └── ... (5 defects)
├── realvis/
│   └── ... (5 defects)
├── absreal/
│   └── ... (5 defects)
└── cyberreal/
    └── ... (5 defects)
```

## Related Code Files
- **Read**: `kohya-ss/configs/crack-lora-training-config.toml` (template)
- **Read**: `models/checkpoints/benchmark/model-registry.json` (from Phase 1)
- **Create**: `pipeline/benchmark/generate-training-configs.py`

## Implementation Steps

1. Create script `pipeline/benchmark/generate-training-configs.py`

2. Define constants:
   ```python
   PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
   CONFIGS_DIR = PROJECT_ROOT / "kohya-ss" / "configs"
   BENCHMARK_CONFIGS_DIR = CONFIGS_DIR / "benchmark"
   BENCHMARK_OUTPUT_DIR = PROJECT_ROOT / "kohya-ss" / "output" / "benchmark"

   DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
   MODELS = {
       "medxray": "medical-xray-sd15.safetensors",
       "realvis": "realistic-vision-v51.safetensors",
       "absreal": "absolute-reality-v181.safetensors",
       "cyberreal": "cyberrealistic-v42.safetensors",
   }
   ```

3. For each model + defect combination:
   - Load existing `{defect}-lora-training-config.toml` with `toml` library (or `tomli`/`tomllib`)
   - Modify these fields ONLY:
     ```python
     config["model_arguments"]["pretrained_model_name_or_path"] = str(
         PROJECT_ROOT / "models" / "checkpoints" / "benchmark" / model_filename
     )
     config["training_arguments"]["output_dir"] = str(
         BENCHMARK_OUTPUT_DIR / model_short / defect
     )
     config["training_arguments"]["output_name"] = f"xray_{defect}_{model_short}_lora_r32"
     config["training_arguments"]["log_prefix"] = f"{defect}_{model_short}"
     config["training_arguments"]["save_every_n_epochs"] = 5  # capture epochs 10, 15, 20
     ```
   - Keep ALL other fields identical (LR, rank, alpha, batch size, dataset paths, etc.)

4. Write each config to `kohya-ss/configs/benchmark/{model_short}/{defect}-lora-training-config.toml`
   - Use `tomli_w` or manual TOML writing (preserve section ordering)

5. Update sample_prompts path if it references defect-specific prompt file:
   ```python
   # Keep original sample_prompts path -- it's defect-specific, not model-specific
   # No change needed here
   ```

6. Validate all 20 configs:
   - Parse each with TOML loader
   - Check `pretrained_model_name_or_path` file exists (warn if not yet downloaded)
   - Check `train_data_dir` exists
   - Check `output_dir` can be created

7. Print summary table:
   ```
   Generated 20 benchmark configs:
   Model      | Defect         | Config Path                     | Output Name
   medxray    | crack          | benchmark/medxray/crack-...toml | xray_crack_medxray_lora_r32
   ...
   ```

### TOML Writing Note
Python's `tomllib` (3.11+) is read-only. For writing:
- Use `tomli_w` package: `pip install tomli-w`
- Or use string template approach: read original as text, regex-replace the 4 fields
- String template is simpler and preserves comments/formatting

### Recommended: String Template Approach
```python
import re

def generate_config(template_text: str, model_short: str, model_filename: str, defect: str) -> str:
    """Replace model path, output dir, output name, log prefix in TOML text."""
    text = template_text

    # Replace pretrained_model_name_or_path
    checkpoint_path = str(PROJECT_ROOT / "models" / "checkpoints" / "benchmark" / model_filename)
    text = re.sub(
        r'pretrained_model_name_or_path\s*=\s*"[^"]*"',
        f'pretrained_model_name_or_path = "{checkpoint_path}"',
        text
    )

    # Replace output_dir
    output_dir = str(BENCHMARK_OUTPUT_DIR / model_short / defect)
    text = re.sub(
        r'output_dir\s*=\s*"[^"]*"',
        f'output_dir = "{output_dir}"',
        text
    )

    # Replace output_name
    output_name = f"xray_{defect}_{model_short}_lora_r32"
    text = re.sub(
        r'output_name\s*=\s*"[^"]*"',
        f'output_name = "{output_name}"',
        text
    )

    # Replace log_prefix
    text = re.sub(
        r'log_prefix\s*=\s*"[^"]*"',
        f'log_prefix = "{defect}_{model_short}"',
        text
    )

    # Update save_every_n_epochs to 5 (capture checkpoints at 10, 15, 20)
    text = re.sub(
        r'save_every_n_epochs\s*=\s*\d+',
        'save_every_n_epochs = 5',
        text
    )

    return text
```

## Todo List
- [ ] Create `pipeline/benchmark/` directory and `__init__.py`
- [ ] Implement `generate-training-configs.py`
- [ ] Test with dry-run mode (print configs without writing)
- [ ] Generate all 20 configs
- [ ] Validate all 20 configs parse correctly
- [ ] Verify checkpoint paths reference correct model files

## Success Criteria
- 20 TOML files generated in `kohya-ss/configs/benchmark/{model}/{defect}-lora-training-config.toml`
- Each config differs from original ONLY in: `pretrained_model_name_or_path`, `output_dir`, `output_name`, `log_prefix`, `save_every_n_epochs`
- All configs parse without error
- No existing production configs modified

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| TOML formatting broken by regex | Low | Validate parsed output matches expected values |
| `tomli_w` not available in env | Low | Use string template approach (no extra dependency) |
| Config field names change between kohya versions | Low | Configs are static files we control |
| Dataset paths incorrect for some defects | Low | Read from existing config, don't hardcode |

## Next Steps
- Phase 3: Pipeline Integration (make `build_workflow()` use checkpoint from config)
- Phase 4: Use generated configs for training execution
