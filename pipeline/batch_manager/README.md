# Batch Production System - Quick Start Guide

## Overview
Automated synthetic X-ray defect image generation pipeline using ComfyUI API.

## Prerequisites
- ComfyUI running at `172.21.192.1:8188` (Windows host accessible from WSL)
- Python venv at `/mnt/e/The Data Mint/pipeline/.venv`
- 5 trained LoRA models deployed to ComfyUI
- Background images in `/mnt/e/The Data Mint/kohya-ss/training_data/reg/1_xray_clean/`

## Quick Start

### Pilot Run (5 images, 1 per defect type)
```bash
cd /mnt/e/The Data Mint/pipeline
.venv/bin/python3 batch_manager/batch-production-main.py --pilot
```

### Production Run (20K images, default config)
```bash
cd /mnt/e/The Data Mint/pipeline
.venv/bin/python3 batch_manager/batch-production-main.py
```

### Custom Configuration
```bash
.venv/bin/python3 batch_manager/batch-production-main.py --config /path/to/custom-config.yaml
```

## Configuration

Edit `/mnt/e/The Data Mint/pipeline/config/batch-config.yaml`:

```yaml
generation:
  total_images: 20000  # Change target count
  defect_distribution:
    crack: 0.25
    porosity: 0.25
    inclusion: 0.20
    lack_of_fusion: 0.15
    undercut: 0.15

thermal:
  enabled: true
  max_temp_celsius: 85    # Pause if GPU exceeds this
  resume_temp_celsius: 75 # Resume when GPU cools below this

reliability:
  max_retries: 3
  checkpoint_interval: 100  # Save progress every N images
```

## Output Structure

```
/mnt/e/The Data Mint/output/synthetic/
├── crack/
│   ├── crack_000000.png       # Generated image
│   ├── crack_000000_mask.png  # Binary mask
│   └── crack_000000.json      # Metadata
├── porosity/
├── inclusion/
├── lack_of_fusion/
└── undercut/
```

## Resume from Checkpoint

If interrupted, the system auto-saves progress every 100 images.

On restart, it will prompt:
```
Found checkpoint from 2026-01-31 13:04:23
  Progress: 5000 images complete
Resume from checkpoint? (y/n):
```

Type `y` to resume, `n` to start fresh (backs up checkpoint).

## Monitoring

### Progress Output
```
[5000/20000] (25.0%) Job 5000 | crack | ETA: 13.5h
  ✓ Saved to: /mnt/e/The Data Mint/output/synthetic/crack/crack_005000.png
```

### Thermal Throttling
```
⚠ GPU temperature 86°C >= 85°C
  Pausing generation until temp drops below 75°C...
  Current temp: 82°C (target: <=75°C)
✓ GPU temperature 74°C <= 75°C
  Resuming generation...
```

### Completion Report
```
Results:
  Total images: 20000/20000
  Success rate: 99.8%
  Failed jobs: 42
  Elapsed time: 18.24 hours
  Throughput: 1096 images/hour
```

## Troubleshooting

### "ComfyUI server not reachable"
- Check ComfyUI is running on Windows host
- Verify network: `curl http://172.21.192.1:8188/system_stats`

### "numpy.core.multiarray failed to import"
- Must use venv Python: `.venv/bin/python3`
- Do not use system Python: `python3`

### "No background images found"
- Check path in config: `paths.backgrounds_dir`
- Verify images exist: `ls /mnt/e/The Data Mint/kohya-ss/training_data/reg/1_xray_clean/`

### High GPU temperature
- Reduce thermal threshold in config: `thermal.max_temp_celsius: 80`
- Improve cooling or reduce GPU power limit
- Run during cooler hours (overnight)

### Slow throughput
- Check ComfyUI queue: not backed up with other jobs
- Verify mask prefetcher workers: increase `performance.mask_prefetch_workers`
- Monitor CPU usage during mask generation

## Performance

### Expected Throughput
- 900-1800 images/hour (512x512, 20 steps, RTX 3090)
- ~2-4 seconds per image

### Estimated Times
- 20K images: 11-22 hours
- 100K images: 2.3-4.6 days

### Resource Usage
- GPU: RTX 3090 24GB (Windows host)
- CPU: 8 workers for mask generation (44 cores available)
- RAM: <1GB for batch manager
- Disk: ~150KB per image (PNG + mask + JSON)

## Architecture

### Components
- `comfyui-rest-api-client.py`: Upload, queue, poll, download
- `batch-job-scheduler.py`: Job distribution, workflow building
- `mask-prefetch-worker-pool.py`: CPU parallel mask generation
- `gpu-thermal-monitor.py`: Temperature monitoring with nvidia-smi
- `checkpoint-state-manager.py`: Atomic checkpoint saves
- `batch-production-main.py`: Main orchestration loop

### Workflow
1. Load config and initialize components
2. Build job list (20K jobs, shuffled)
3. Pre-fill mask buffer (50 masks ahead)
4. Main loop:
   - Check GPU temperature (thermal gate)
   - Get pre-generated mask from buffer
   - Upload background and mask to ComfyUI
   - Build workflow with job parameters
   - Queue prompt and poll completion
   - Download result and save with metadata
   - Checkpoint every 100 images
5. Generate final report

## Advanced Usage

### Test Workflow Building
```bash
.venv/bin/python3 batch_manager/test-workflow-build.py
```

### Check GPU Temperature
```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader
```

### Monitor Disk Space
```bash
df -h /mnt/e/The\ Data\ Mint/output/
```

### Clean Failed Jobs
Failed jobs are logged in checkpoint. To retry only failed:
1. Note failed job IDs from final report
2. Create custom job list in scheduler
3. Re-run with subset

## Next Steps

After batch production:
- **Phase 7**: Post-processing (annotation format conversion)
- **Phase 8**: Quality assurance (automated validation)
- **Phase 9**: Dataset packaging and distribution
