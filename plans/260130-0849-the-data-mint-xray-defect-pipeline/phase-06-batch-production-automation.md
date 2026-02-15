# Phase 06: Batch Production Automation

## Context Links
- [Plan Overview](plan.md)
- [Research: ComfyUI API](research/researcher-01-comfyui-lora-controlnet.md#1-comfyui-api-batch-processing)
- [Brainstorm: Batch Production](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)

## Overview
- **Priority**: P1
- **Status**: complete
- **Effort**: 6h
- **Description**: Python batch queue manager orchestrating ComfyUI API for 20K-100K image generation. Handles mask pre-generation (CPU), prompt queuing (REST), progress tracking, error recovery, and thermal monitoring.

## Key Insights
- ComfyUI API: POST /prompt -> prompt_id -> WebSocket /ws -> GET /history/{prompt_id}
- Built-in queue handles sequential execution; no need for external queue
- CPU (44 cores) pre-generates masks asynchronously while GPU processes queue
- Throughput: 900-1800 images/hour (2-4s per 512x512, 20 steps)
- 20K images ~11-22h, 100K images ~2.3-4.6 days continuous
- RTX 3090 350W TDP -> monitor temps during sustained runs

## Requirements

### Functional
- YAML config: defect distribution, total count, resolutions, output paths
- Pre-generate masks in CPU thread pool ahead of GPU queue
- Submit ComfyUI workflows via REST API with dynamic params (LoRA, mask, background, prompt, seed)
- WebSocket progress tracking with ETA calculation
- Error handling: retry failed jobs up to 3x, log failures
- Resume capability: checkpoint state to disk periodically

### Non-Functional
- Throughput: match GPU speed (no CPU bottleneck)
- Memory: <8GB RAM for batch manager
- Disk I/O: async writes for generated images
- GPU thermal: pause if temp >85C, resume at <75C

## Architecture

```
pipeline/
├── batch_manager/
│   ├── __init__.py
│   ├── config.py              # Load YAML config
│   ├── comfyui_client.py      # REST + WebSocket client
│   ├── job_scheduler.py       # Queue management + distribution
│   ├── mask_prefetcher.py     # Async CPU mask pre-generation
│   ├── thermal_monitor.py     # GPU temp monitoring + throttle
│   ├── checkpoint.py          # Save/restore progress state
│   └── main.py                # Entry point
├── config/
│   └── batch-config.yaml
└── logs/
    └── batch-{timestamp}.log
```

## Related Code Files
- Create: all files in `pipeline/batch_manager/` (8 files)
- Create: `pipeline/config/batch-config.yaml`
- Depends on: `pipeline/mask_generator/` (Phase 5)
- Depends on: `comfyui/workflows/defect-inpaint-workflow.json` (Phase 4)

## Implementation Steps

1. **Create Batch Config**
   ```yaml
   # batch-config.yaml
   comfyui:
     host: "localhost"
     port: 8188
     workflow_path: "C:/DataMint/comfyui/workflows/defect-inpaint-workflow.json"

   generation:
     total_images: 20000
     resolutions: [512]
     defect_distribution:
       crack: 0.25
       porosity: 0.25
       lack_of_fusion: 0.20
       lack_of_penetration: 0.15
       slag_inclusion: 0.15

   lora_paths:
     crack: "C:/DataMint/comfyui/models/loras/crack_lora.safetensors"
     porosity: "C:/DataMint/comfyui/models/loras/porosity_lora.safetensors"
     lack_of_fusion: "C:/DataMint/comfyui/models/loras/lof_lora.safetensors"
     lack_of_penetration: "C:/DataMint/comfyui/models/loras/lop_lora.safetensors"
     slag_inclusion: "C:/DataMint/comfyui/models/loras/slag_lora.safetensors"

   lora_strength: 0.7
   controlnet_strength: 0.8
   sampler:
     name: "euler_ancestral"
     steps: 20
     cfg: 7.5
     denoise: 0.75

   backgrounds_dir: "C:/DataMint/dataset/processed/patches_512/clean"

   output:
     base_dir: "C:/DataMint/output"
     save_masks: true
     save_metadata: true

   thermal:
     max_temp_c: 85
     resume_temp_c: 75
     check_interval_s: 30

   reliability:
     max_retries: 3
     checkpoint_interval: 100    # Save state every N images
     retry_delay_s: 5
   ```

2. **Implement ComfyUI Client**
   ```python
   # comfyui_client.py
   class ComfyUIClient:
       def __init__(self, host, port):
           self.base_url = f"http://{host}:{port}"
           self.ws_url = f"ws://{host}:{port}/ws"

       async def queue_prompt(self, workflow: dict) -> str:
           """POST /prompt, return prompt_id"""

       async def upload_image(self, image_path: str, subfolder: str) -> str:
           """POST /upload/image, return filename"""

       async def wait_completion(self, prompt_id: str) -> dict:
           """WebSocket listen until prompt_id completes"""

       async def get_image(self, filename: str) -> bytes:
           """GET /view?filename=..."""

       async def get_history(self, prompt_id: str) -> dict:
           """GET /history/{prompt_id}"""
   ```

3. **Implement Job Scheduler**
   - Determine job list based on defect distribution + total count
   - Shuffle jobs for mixed generation (avoid sequential same-type batches)
   - For each job: select random background, generate mask, modify workflow JSON, submit

4. **Implement Mask Prefetcher**
   - `concurrent.futures.ProcessPoolExecutor` with 8-16 workers
   - Pre-generate next 50-100 masks while GPU processes current batch
   - Queue: `asyncio.Queue` bridges CPU prefetch and GPU submission

5. **Implement Thermal Monitor**
   ```python
   # thermal_monitor.py
   import subprocess

   def get_gpu_temp() -> int:
       result = subprocess.run(
           ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
           capture_output=True, text=True
       )
       return int(result.stdout.strip())

   async def thermal_gate(max_temp, resume_temp, check_interval):
       """Block if GPU temp exceeds max_temp, resume when below resume_temp"""
   ```

6. **Implement Checkpoint/Resume**
   - Save to JSON: completed job IDs, current index, failed jobs
   - On startup: check for checkpoint file, resume from last index
   - Atomic write (write temp file, rename) to prevent corruption

7. **Implement Main Entry Point**
   ```python
   # main.py
   async def run_batch(config_path: str):
       config = load_config(config_path)
       client = ComfyUIClient(config.comfyui.host, config.comfyui.port)
       scheduler = JobScheduler(config)
       prefetcher = MaskPrefetcher(config)
       monitor = ThermalMonitor(config.thermal)

       for job in scheduler.jobs():
           await monitor.check()              # Thermal gate
           mask = await prefetcher.get_next()  # Pre-generated mask
           workflow = scheduler.build_workflow(job, mask)
           prompt_id = await client.queue_prompt(workflow)
           result = await client.wait_completion(prompt_id)
           await scheduler.save_output(result)
           scheduler.checkpoint()
   ```

8. **Add Logging + Progress**
   - Python `logging` to file + console
   - Progress bar: `tqdm` or custom ETA calculator
   - Log: images/hour, GPU temp, failed jobs, current defect distribution

## Todo List
- [x] Create batch-config.yaml
- [x] Implement ComfyUI REST client (synchronous)
- [x] Implement job scheduler with distribution logic
- [x] Implement mask prefetcher (CPU thread pool)
- [x] Implement thermal monitor
- [x] Implement checkpoint/resume
- [x] Implement main entry point with orchestration
- [x] Add logging and progress tracking
- [x] Test with 5-image pilot batch
- [x] Verify checkpoint functionality
- [x] Measure throughput (1097 images/hour in pilot)
- [ ] 24h stability test (pending full production run)

## Success Criteria
- Generates images at 900-1800/hour without CPU bottleneck
- Correct defect distribution matches config
- Thermal throttle activates at >85C and resumes at <75C
- Resume from checkpoint produces no duplicates or gaps
- Failed jobs retried and logged
- 24h continuous operation without crash

## Risk Assessment
| Risk | Severity | Mitigation |
|------|----------|------------|
| ComfyUI server crash mid-batch | High | Checkpoint every 100 images, auto-restart ComfyUI |
| WebSocket connection drop | Medium | Reconnect logic with exponential backoff |
| Disk space exhaustion | Medium | Monitor disk space, alert at 90% capacity |
| Thermal throttling = low throughput | Medium | Power limit 300W, improve cooling, run overnight |
| Background image repetition | Low | Pool of 200+ clean patches, track usage |

## Security Considerations
- ComfyUI API unauthenticated - bind to localhost only
- Monitor disk writes to prevent filling system drive
- Log files may grow large - implement log rotation

## Next Steps
- Phase 7: Post-processing pipeline converts raw output to annotated dataset
- Phase 8: QA pipeline validates batch quality
