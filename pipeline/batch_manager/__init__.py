"""
Batch Manager Module

Orchestrates automated batch production of synthetic X-ray defect images
using ComfyUI API, mask generators, and thermal monitoring.
"""

from importlib import import_module

# Import from kebab-case filenames
comfyui_client_module = import_module('.comfyui-rest-api-client', package=__name__)
job_scheduler_module = import_module('.batch-job-scheduler', package=__name__)
mask_prefetcher_module = import_module('.mask_prefetch_worker_pool', package=__name__)
thermal_monitor_module = import_module('.gpu-thermal-monitor', package=__name__)
checkpoint_manager_module = import_module('.checkpoint-state-manager', package=__name__)

ComfyUIClient = comfyui_client_module.ComfyUIClient
BatchJobScheduler = job_scheduler_module.BatchJobScheduler
MaskPrefetcher = mask_prefetcher_module.MaskPrefetcher
GPUThermalMonitor = thermal_monitor_module.GPUThermalMonitor
CheckpointManager = checkpoint_manager_module.CheckpointManager

__all__ = [
    'ComfyUIClient',
    'BatchJobScheduler',
    'MaskPrefetcher',
    'GPUThermalMonitor',
    'CheckpointManager',
]
