# Kohya-SS Multi-Model LoRA Training Research

**Date:** 2026-02-16
**Focus:** Setting up kohya-ss LoRA training across multiple base model checkpoints

---

## 1. TOML Config Parameterization

### Base Model Configuration
- Set `pretrained_model_name_or_path` in `[model_arguments]` section
- Use absolute paths: `pretrained_model_name_or_path = "/path/to/models/realistic-vision-v5.safetensors"`
- Each training run requires one base model specified

### Multi-Model Approach
- No native support for simultaneous multi-model training
- **Pattern:** Create separate TOML configs per base model, e.g.:
  - `crack-lora-realistic-vision.toml`
  - `crack-lora-cyberrealistic.toml`
  - `crack-lora-vanilla-sd15.toml`
- Keep all other parameters identical across configs for fair comparison

### Key TOML Sections
```toml
[model_arguments]
pretrained_model_name_or_path = "./models/base-checkpoint.safetensors"

[dataset_arguments]
resolution = 512  # SD 1.5 standard
batch_size = 4
```

---

## 2. Output Directory Organization

### Recommended Structure for Benchmarking
```
outputs/
├── defect-type-lora/
│   ├── realistic-vision-v5/
│   │   ├── crack-lora-rv5-ep10.safetensors
│   │   ├── crack-lora-rv5-ep20.safetensors
│   │   └── training_logs/
│   ├── cyberrealistic-v4/
│   │   ├── crack-lora-cr4-ep10.safetensors
│   │   ├── crack-lora-cr4-ep20.safetensors
│   │   └── training_logs/
│   └── vanilla-sd15/
│       ├── crack-lora-vanilla-ep10.safetensors
│       └── training_logs/
```

### Configuration
- Set `output_dir` in TOML per base model
- Use checkpoint naming: `save_model_as = "safetensors"`
- Enable periodic saves: `save_every_n_epochs = 10` to evaluate intermediate checkpoints
- **Naming convention:**
  - Number suffix for different datasets (v1, v2)
  - Letter suffix for same dataset, different hyperparams (a, b, c)

---

## 3. Hyperparameter Adjustments for Different Checkpoints

### Current Config Analysis
- Rank 32 / Alpha 16: **Good baseline**
- AdamW8bit: **Appropriate for all SD 1.5 variants**
- Cosine_with_restarts: **Solid choice**
- Learning rate: **Needs confirmation (assume 1e-4)**

### Adjustments Needed

#### Rank & Alpha Relationship
- **Standard ratio:** Alpha = Rank/2 (your 32/16 is correct)
- **Alternative:** Alpha = 2 × Rank for stronger influence
- **For photorealistic models:** Keep Rank 32, test Alpha at 16, 32, 64
- More complex datasets may need Rank 48-64

#### Learning Rate Tuning
- **SD 1.5 LoRA standard:** 1e-4 (0.0001) baseline
- **Critical:** Photorealistic checkpoints ARE different base models
- **Recommendation:** Test per checkpoint:
  - Realistic Vision: Start 1e-4
  - CyberRealistic: Start 1e-4, may need 8e-5 if overfitting
  - Medical models: May need 5e-5 (more specialized)
- **UNet/Text Encoder split:**
  - UNet LR = Main LR / 2
  - Text Encoder LR = Main LR / 4

#### Batch & Gradient Accumulation
- Current: batch_size 4, gradient_accumulation 2 = effective batch 8
- **Keep identical across all base models** for fair comparison

### Key Insight
> Fine-tuned checkpoints (Realistic Vision, CyberRealistic) have different latent space characteristics than vanilla SD 1.5. Same hyperparams may produce varying convergence speeds and quality.

---

## 4. Known Issues: Photorealistic vs Vanilla SD 1.5

### Photorealistic Checkpoint Considerations
- **Pre-trained biases:** Already tuned for realism; LoRA may conflict with existing tuning
- **Convergence speed:** Often faster than vanilla due to better feature representations
- **Overfitting risk:** Higher on photorealistic models with small datasets (<50 images)
- **Style bleed:** Strong base model style may dominate LoRA concepts

### Mitigation Strategies
- **Lower learning rate** (8e-5 instead of 1e-4) for photorealistic checkpoints
- **More training steps** but monitor for overfitting
- **Dataset quality:** Photorealistic models demand higher-quality, consistent training data
- **Test both vanilla and photorealistic:** Vanilla may generalize better for defect detection

### Medical Model Specifics
- Medical checkpoints likely pre-trained on grayscale/X-ray data
- May need **significantly lower LR** (5e-5 or lower)
- Expect different optimal epoch counts

---

## 5. Batch Training Automation

### Script Approach: Bash/PowerShell Wrapper

**Pattern:** Loop through base model configs and call kohya training script

```bash
#!/bin/bash
# train-all-loras.sh

BASE_MODELS=(
  "realistic-vision-v5"
  "cyberrealistic-v4"
  "vanilla-sd15"
)

DEFECT_TYPES=(
  "crack"
  "porosity"
  "inclusion"
  "lack-of-fusion"
  "undercut"
)

for model in "${BASE_MODELS[@]}"; do
  for defect in "${DEFECT_TYPES[@]}"; do
    echo "Training $defect LoRA on $model..."
    accelerate launch --num_cpu_threads_per_process=2 \
      train_network.py \
      --config_file="./configs/${defect}-lora-${model}.toml"

    # Optional: Wait between trainings for GPU cooldown
    sleep 60
  done
done
```

### PowerShell Variant (Windows)
```powershell
# train-all-loras.ps1
$baseModels = @("realistic-vision-v5", "cyberrealistic-v4", "vanilla-sd15")
$defectTypes = @("crack", "porosity", "inclusion", "lack-of-fusion", "undercut")

foreach ($model in $baseModels) {
  foreach ($defect in $defectTypes) {
    Write-Host "Training $defect LoRA on $model..."
    accelerate launch --num_cpu_threads_per_process=2 `
      train_network.py `
      --config_file="./configs/$defect-lora-$model.toml"

    Start-Sleep -Seconds 60
  }
}
```

### TOML Config Management
- **Templating:** Use single template TOML, replace `{{BASE_MODEL}}` and `{{OUTPUT_DIR}}` via script
- **Python script alternative:**
  ```python
  import toml
  import subprocess

  template = toml.load("template.toml")
  for model in base_models:
      config = template.copy()
      config['model_arguments']['pretrained_model_name_or_path'] = model_path
      config['output_dir'] = f"outputs/{defect_type}/{model_name}/"

      with open(f"temp_config_{model_name}.toml", "w") as f:
          toml.dump(config, f)

      subprocess.run(["accelerate", "launch", "train_network.py",
                      "--config_file", f"temp_config_{model_name}.toml"])
  ```

---

## Practical Recommendations

### Immediate Actions
1. **Create config template** with placeholders for `pretrained_model_name_or_path` and `output_dir`
2. **Test single defect type** (crack) across all 3 base models first
3. **Use identical hyperparams** initially: Rank 32, Alpha 16, LR 1e-4
4. **Monitor training loss curves** to identify if photorealistic models need LR adjustment

### Benchmarking Protocol
1. Train all models to 20 epochs (save checkpoints at 10, 15, 20)
2. Evaluate each checkpoint on validation set
3. Compare:
   - Training time
   - Final loss
   - Visual quality on test prompts
   - Generalization to unseen defect variations

### Risk Mitigation
- **Start conservative:** Don't lower LR prematurely; observe overfitting first
- **Dataset size:** If <30 images, reduce epochs to 15 or enable regularization
- **Version control:** Tag each training run with commit hash + config hash

---

## Sources

- [TOML config for sdxl lora training](https://github.com/kohya-ss/sd-scripts/issues/2094)
- [kohya_ss GitHub](https://github.com/bmaltais/kohya_ss)
- [LoRA training parameters Wiki](https://github.com/bmaltais/kohya_ss/wiki/LoRA-training-parameters)
- [Stable Diffusion LoRA Training Settings - Aituts](https://aituts.com/lora-training-settings/)
- [Generate Studio Quality Realistic Photos Training Tutorial](https://github.com/FurkanGozukara/Stable-Diffusion/blob/main/Tutorials/Generate-Studio-Quality-Realistic-Photos-By-Kohya-LoRA-Stable-Diffusion-Training-Full-Tutorial.md)
- [sd-scripts config README](https://github.com/kohya-ss/sd-scripts/blob/main/docs/config_README-en.md)
- [Execute Kohya SS without WebUI](https://github.com/kohya-ss/sd-scripts/discussions/747)
- [LoRA Hyperparameters Guide - Unsloth](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide)
- [Understanding LoRA Training - Medium](https://medium.com/@dreamsarereal/understanding-lora-training-part-1-learning-rate-schedulers-network-dimension-and-alpha-c88a8658beb7)
- [THE OTHER LoRA TRAINING RENTRY](https://rentry.co/59xed3)
- [MimicPC Kohya-SS Training Guide](https://www.mimicpc.com/learn/sd-lora-training-guide-kohya-ss)
