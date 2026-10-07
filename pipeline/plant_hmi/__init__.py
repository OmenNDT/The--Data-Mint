"""Plant HMI: the image-generation pipeline drawn and monitored as a process plant.

Phase 1 is read-only: it polls existing state (processes, image silo, checkpoint,
ComfyUI, GPU, RAM) and never edits or controls the pipeline.
"""
