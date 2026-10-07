# Phase 3: Pipeline Integration

## Context Links
- [Plan Overview](plan.md)
- [Phase 2: Config Generation](phase-02-generate-training-configs.md)
- Workflow JSON: `pipeline/comfyui-workflows/sd15-lora-controlnet-inpaint-single-defect-workflow.json`
- Scheduler: `pipeline/batch_manager/batch-job-scheduler.py`
- Prompt templates: `pipeline/comfyui-workflows/defect-type-prompt-templates.yaml`
- Batch config: `pipeline/config/batch-config.yaml`

## Overview
- **Priority**: P1 (blocks Phase 5 generation)
- **Status**: complete
- **Effort**: 4h
- **Description**: Make the image generation pipeline support selectable base model checkpoint and optional external VAE. Create benchmark-specific configs. Do NOT modify production configs.

## Key Insights
- Node "1" (`CheckpointLoaderSimple`) in workflow JSON is hardcoded to `sd-v1-5-pruned-emaonly.safetensors`
- `build_workflow()` in `batch-job-scheduler.py` (line 95-158) sets LoRA, prompts, sampler params but NEVER sets node "1" checkpoint
- Node "8" and "11" both read VAE from node "1" output slot 2 (`["1", 2]`); for external VAE, need a new `VAELoader` node
- `defect-type-prompt-templates.yaml` already has `model_paths.checkpoint` field but `build_workflow()` ignores it
- Strategy: Create benchmark wrapper that modifies workflow AFTER `build_workflow()` returns, avoiding changes to production code path

## Requirements

### Functional
- Support checkpoint selection per batch config
- Support optional external VAE per batch config
- Create 4 benchmark batch configs (one per model)
- Create 4 benchmark prompt template files (one per model) with model-specific LoRA names
- Ensure deterministic seeds across all models for fair comparison

### Non-functional
- Zero changes to existing production config files
- Minimal changes to existing Python code (prefer additive)
- Backward compatible -- existing pipeline works unchanged if no benchmark config

## Architecture

### Approach: Benchmark Wrapper (Minimal Invasion)

Rather than modifying `batch-job-scheduler.py` core logic, create:
1. Benchmark-specific batch configs with checkpoint/VAE fields
2. Benchmark-specific prompt templates with model-specific LoRA names
3. Small patch to `build_workflow()` to read checkpoint from prompt templates (2 lines)
4. Benchmark workflow JSON variant with VAELoader node for external VAE models

### Workflow Modification for External VAE

**Current flow (nodes using checkpoint VAE):**
```
Node 1 (CheckpointLoaderSimple) --[vae]--> Node 8 (InpaintModelConditioning)
Node 1 (CheckpointLoaderSimple) --[vae]--> Node 11 (VAEDecode)
```

**New flow for external VAE (add Node 13):**
```
Node 13 (VAELoader) --[vae]--> Node 8 (InpaintModelConditioning)
Node 13 (VAELoader) --[vae]--> Node 11 (VAEDecode)
Node 1 (CheckpointLoaderSimple) --[model, clip only]--> (downstream nodes unchanged)
```

## Related Code Files

### Modify (minimal)
- `pipeline/batch_manager/batch-job-scheduler.py` -- Add 2-4 lines in `build_workflow()` to set checkpoint name from prompt templates

### Create (benchmark-only)
- `pipeline/config/benchmark/medxray-batch-config.yaml`
- `pipeline/config/benchmark/realvis-batch-config.yaml`
- `pipeline/config/benchmark/absreal-batch-config.yaml`
- `pipeline/config/benchmark/cyberreal-batch-config.yaml`
- `pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-medxray.yaml`
- `pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-realvis.yaml`
- `pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-absreal.yaml`
- `pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-cyberreal.yaml`
- `pipeline/comfyui-workflows/benchmark/sd15-lora-controlnet-inpaint-external-vae-workflow.json`
- `pipeline/benchmark/generate-benchmark-configs.py` (generates all above from templates)

## Implementation Steps

### Step 1: Patch `build_workflow()` (2-4 lines)

In `pipeline/batch_manager/batch-job-scheduler.py`, after line 122 (deep copy), add:

```python
# Set checkpoint model from prompt templates (supports benchmark model selection)
model_paths = self.prompts_config.get("model_paths", {})
if model_paths.get("checkpoint"):
    workflow["1"]["inputs"]["ckpt_name"] = model_paths["checkpoint"]

# Set external VAE if specified
if model_paths.get("vae"):
    # Only works with workflow that has VAELoader node "13"
    if "13" in workflow:
        workflow["13"]["inputs"]["vae_name"] = model_paths["vae"]
```

This is backward compatible: existing prompt templates have `checkpoint: "checkpoints/sd-v1-5-pruned-emaonly.safetensors"` which matches the current hardcoded value.

### Step 2: Create External VAE Workflow JSON

Copy `sd15-lora-controlnet-inpaint-single-defect-workflow.json` to `benchmark/sd15-lora-controlnet-inpaint-external-vae-workflow.json` and add:

```json
{
  "13": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "sd-vae-ft-mse.safetensors"
    }
  }
}
```

And change VAE references in nodes 8 and 11:
- Node "8": `"vae": ["13", 0]` (was `["1", 2]`)
- Node "11": `"vae": ["13", 0]` (was `["1", 2]`)

### Step 3: Create Benchmark Prompt Templates

For each model, create a prompt template YAML. Only differences from production:
- `model_paths.checkpoint` -- points to benchmark model
- `model_paths.vae` -- set for models needing external VAE (null for cyberreal)
- `defect_prompts.{defect}.lora_name` -- model-specific LoRA name

Example: `defect-type-prompt-templates-medxray.yaml`
```yaml
defect_prompts:
  crack:
    lora_name: "xray_crack_medxray_lora_r32.safetensors"
    positive: "xray_crack, weld crack defect, radiographic image, high contrast, sharp edges, linear discontinuity, prominent dark line, visible crack pattern"
    negative: "color, photograph, blurry, text, watermark, low quality, rgb, scattered defects, round shapes, clean weld, no defect"
    lora_strength: 0.85
    controlnet_strength: 0.45
    denoise: 0.92
  porosity:
    lora_name: "xray_porosity_medxray_lora_r32.safetensors"
    # ... (same prompts, strengths as production)
  # ... (all 5 defects)

sampler_config:
  sampler_name: "euler"
  scheduler: "normal"
  steps: 20
  cfg: 8.5

model_paths:
  checkpoint: "checkpoints/benchmark/medical-xray-sd15.safetensors"
  vae: "vae/sd-vae-ft-mse.safetensors"
  controlnet: "controlnet/control_v11p_sd15_inpaint.pth"
  lora_dir: "loras/"
```

### Step 4: Create Benchmark Batch Configs

For each model, create batch config. Only differences from production:
- `comfyui.prompts_path` -- points to model-specific prompt template
- `comfyui.workflow_path` -- points to external-VAE workflow (for models 1-3) or standard workflow (model 4)
- `lora_models` -- model-specific LoRA names
- `paths.output_base_dir` -- `output/benchmark/{model_short}`
- `generation.defect_distribution` -- equal distribution (0.2 each) for benchmarking

Example: `medxray-batch-config.yaml`
```yaml
comfyui:
  host: 192.168.2.9
  port: 8188
  prompts_path: /home/sontn/Projects/The Data Mint/pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-medxray.yaml
  workflow_path: /home/sontn/Projects/The Data Mint/pipeline/comfyui-workflows/benchmark/sd15-lora-controlnet-inpaint-external-vae-workflow.json
generation:
  defect_distribution:
    crack: 0.2
    inclusion: 0.2
    lack_of_fusion: 0.2
    porosity: 0.2
    undercut: 0.2
  resolution: 512
  total_images: 500
lora_models:
  crack: xray_crack_medxray_lora_r32.safetensors
  inclusion: xray_inclusion_medxray_lora_r32.safetensors
  lack_of_fusion: xray_lof_medxray_lora_r32.safetensors
  porosity: xray_porosity_medxray_lora_r32.safetensors
  undercut: xray_undercut_medxray_lora_r32.safetensors
paths:
  backgrounds_dir: /home/sontn/Projects/The Data Mint/kohya-ss/training_data/reg/1_xray_clean
  output_base_dir: /home/sontn/Projects/The Data Mint/output/benchmark/medxray
  logs_dir: /home/sontn/Projects/The Data Mint/pipeline/logs
# ... (same performance, reliability, sampler, thermal settings as production)
```

### Step 5: Create Config Generator Script

`pipeline/benchmark/generate-benchmark-configs.py`:
- Read production `defect-type-prompt-templates.yaml` as template
- Read production `batch-config.yaml` as template
- Read `model-registry.json` for model paths
- For each model: generate prompt template YAML + batch config YAML
- Copy and modify workflow JSON for external VAE variant
- For CyberRealistic (built-in VAE): use standard workflow, set `vae: null`

### Step 6: Deploy Trained LoRAs to ComfyUI

After Phase 4 training completes, LoRAs need to be in ComfyUI's loras directory:
```
models/loras/
├── xray_crack_lora_r32.safetensors        # existing production
├── xray_crack_medxray_lora_r32.safetensors # benchmark
├── xray_crack_realvis_lora_r32.safetensors
├── xray_crack_absreal_lora_r32.safetensors
├── xray_crack_cyberreal_lora_r32.safetensors
└── ... (20 benchmark LoRAs total)
```

## Todo List
- [ ] Patch `build_workflow()` with checkpoint/VAE selection (4 lines)
- [ ] Create external VAE workflow JSON variant
- [ ] Implement `generate-benchmark-configs.py`
- [ ] Generate 4 benchmark prompt template YAMLs
- [ ] Generate 4 benchmark batch config YAMLs
- [ ] Test production pipeline still works unchanged (regression check)
- [ ] Verify benchmark workflow loads in ComfyUI (manual check)

## Success Criteria
- Production pipeline unaffected (run existing batch config, verify same output)
- `build_workflow()` correctly sets checkpoint name from prompt templates
- External VAE workflow routes VAE through node "13" instead of node "1"
- All 4 benchmark batch configs point to correct model-specific prompt templates and workflows
- LoRA naming convention matches Phase 2 output names

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Changing `build_workflow()` breaks production | High | Only add lines; existing `model_paths.checkpoint` already has production value |
| External VAE node ID conflicts | Low | Use node "13" (unused in current workflow) |
| ComfyUI rejects modified workflow | Medium | Test workflow in ComfyUI UI before automation |
| LoRA names don't match between config and filesystem | Medium | Use `model-registry.json` as single source of truth |

## Security Considerations
- No secrets exposed in config files (all local paths)
- ComfyUI host/port same as production (internal network)

## Next Steps
- After pipeline integration verified -> Phase 4 (training) can begin
- Phase 5 (generation) uses benchmark batch configs directly
