# Phase 4: Progress Tracking

## Context Links
- [System Architecture](../../docs/system-architecture.md) - Logging patterns
- [Codebase Summary](../../docs/codebase-summary.md) - Checkpoint format
- [Phase 1: Orchestrator](phase-01-pipeline-orchestrator.md) - Subprocess stdout source

## Overview
- **Priority**: P2 (enhances UX but not blocking)
- **Status**: Pending
- **Effort**: 3h
- **Description**: Parse real-time stdout from pipeline subprocesses to extract structured progress data (phase %, image count, ETA, GPU temp). Feed parsed data to UI progress components.

## Key Insights
<!-- Updated: Validation Session 1 - Add kohya-ss log parsing + GPU temp display -->
- Phase 3 LoRA training: kohya-ss logs `epoch {N}/{total}`, loss values, lr schedule
- Phase 6 logs `[CHECKPOINT] Generated {N} images` every 100 images
- Phase 6 thermal monitor logs pause/resume events
- Phase 7 post-processing is fast (~2 min for 20K); coarse progress sufficient
- Phase 8 QA logs SSIM check progress
- Phase 9 YOLO training: Ultralytics prints epoch progress like `Epoch 15/100`
- Existing logging uses Python `logging` module with `INFO`/`WARNING`/`ERROR` levels
- **GPU temp display** — poll nvidia-smi for real-time temperature/VRAM in progress panel

## Requirements

### Functional
- FR1: Parse Phase 6 checkpoint lines to extract image count / total
- FR2: Parse Phase 9 epoch lines to extract epoch / total
- FR3: Calculate overall pipeline progress (weighted by estimated phase duration)
- FR4: Compute ETA based on throughput rate
- FR5: Detect error/warning lines and flag them in UI
- FR6: Extract GPU temperature from thermal monitor logs

### Non-Functional
- NFR1: < 200 lines per file
- NFR2: Regex patterns must not break on unexpected log formats (fail gracefully)

## Architecture

```
ProgressTracker
├── __init__(total_phases, config)
├── parse_line(line: str) -> ProgressUpdate
├── get_overall_progress() -> float  # 0.0 - 1.0
├── get_eta_seconds() -> Optional[int]
├── get_current_phase_info() -> PhaseProgress
└── reset()

ProgressUpdate (dataclass)
├── phase_id: int
├── phase_progress: float  # 0.0 - 1.0
├── overall_progress: float
├── message: str
├── level: str  # info, warning, error
├── eta_seconds: Optional[int]
├── gpu_temp: Optional[float]
├── images_generated: Optional[int]
├── epoch_current: Optional[int]
```

### Progress Weight Distribution
Pipeline total = 100%
- Phase 6 (Generation): 70% weight (~18h for 20K)
- Phase 7 (Post-processing): 2% weight (~2min)
- Phase 8 (QA): 3% weight (~10min)
- Phase 9 (Validation): 25% weight (~5h for 4 experiments)

Weights adjust dynamically if phases are skipped.

## Related Code Files

### Files to Create
- `pipeline/launcher/progress-tracker.py` (~180 lines) - Parser + state tracker

### Existing Files Referenced (read-only, for log format analysis)
- `pipeline/batch_manager/batch-production-main.py` - Checkpoint log format
- `pipeline/batch_manager/gpu-thermal-monitor.py` - Thermal log format
- `pipeline/qa/qa-pipeline-main.py` - QA progress format
- `pipeline/validation/validation-main.py` - Validation progress format

## Implementation Steps

1. Analyze existing log output patterns:
   - Phase 6: `[CHECKPOINT] Generated {N} images, elapsed: {T}s`
   - Phase 6: `[THERMAL] GPU temp: {T}°C, pausing...`
   - Phase 7: `Processing {defect_type}... ({N}/{total})`
   - Phase 8: `SSIM check: {N}/{sample_size} images`
   - Phase 9: Ultralytics format `Epoch {N}/{total}`, `mAP@0.5: {val}`
2. Create `ProgressUpdate` and `PhaseProgress` dataclasses
3. Implement regex patterns for each phase:
   ```python
   PATTERNS = {
       "checkpoint": r"\[CHECKPOINT\] Generated (\d+) images",
       "thermal": r"GPU temp: ([\d.]+)",
       "epoch": r"Epoch\s+(\d+)/(\d+)",
       "ssim": r"SSIM check: (\d+)/(\d+)",
       "error": r"\[(ERROR|CRITICAL)\]",
       "warning": r"\[WARNING\]",
   }
   ```
4. Implement `ProgressTracker.__init__()`:
   - Accept `total_phases` and config (for total_images, epochs)
   - Initialize phase weights based on config
   - Set up internal state (current_phase, start_time, counters)
5. Implement `parse_line(line)`:
   - Match against regex patterns
   - Update internal state (image_count, epoch_count, etc.)
   - Calculate phase progress and overall progress
   - Compute ETA: `remaining_work / throughput_rate`
   - Return `ProgressUpdate`
6. Implement `get_overall_progress()`:
   - Sum completed phase weights + current phase partial weight
   - Return float 0.0-1.0
7. Implement `get_eta_seconds()`:
   - Track throughput (images/sec or epochs/sec)
   - Extrapolate remaining time
   - Add remaining phase estimates
8. Integration with Phase 1 (Orchestrator):
   - `PhaseRunner` passes each stdout line to `ProgressTracker.parse_line()`
   - `ProgressUpdate` forwarded to Gradio UI via callback/queue

## Todo List
- [ ] Analyze actual log output from each phase (run pilot to capture samples)
- [ ] Define `ProgressUpdate` and `PhaseProgress` dataclasses
- [ ] Implement regex patterns for phases 6, 7, 8, 9
- [ ] Implement `ProgressTracker` class with state management
- [ ] Implement `parse_line()` with pattern matching
- [ ] Implement ETA calculation based on throughput
- [ ] Implement phase weight distribution
- [ ] Handle edge cases (unexpected log format, empty lines)
- [ ] Unit test with sample log lines

## Success Criteria
- Correctly parses Phase 6 checkpoint lines and reports image count
- Correctly parses Phase 9 epoch progress
- Overall progress bar moves proportionally across phases
- ETA within 20% accuracy after first few data points
- Unknown log lines passed through as raw text (no crash)

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Log format changes break regex | Medium | Graceful fallback: unparsed lines shown as-is |
| ETA wildly inaccurate early on | Low | Show "calculating..." until 5+ data points |
| Ultralytics output format varies by version | Medium | Test with installed version; use loose regex |
| GPU temp not available (no nvidia-smi) | Low | Show "N/A" for GPU temp; don't crash |

## Security Considerations
- Log lines are read-only; no user input injected into regex
- No external data sources

## Next Steps
- Phase 3 (Gradio UI) consumes `ProgressUpdate` to refresh progress bar and log display
- Phase 5 (Results Dashboard) uses final metrics extracted from Phase 9 output
