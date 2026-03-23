"""
Batch Job Scheduler

Manages job queue, defect distribution, workflow building, and output organization.
Creates job list from config, shuffles for mixed generation, tracks progress.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml


class BatchJobScheduler:
    """Manages batch job queue and workflow generation."""

    def __init__(self, config: Dict):
        """
        Initialize job scheduler.

        Args:
            config: Batch configuration dict
        """
        self.config = config
        self.jobs = []
        self.current_index = 0
        self.completed_count = 0
        self.failed_jobs = []

        # Load workflow template
        workflow_path = config["comfyui"]["workflow_path"]
        with open(workflow_path, "r") as f:
            self.workflow_template = json.load(f)

        # Load prompt templates
        prompts_path = config["comfyui"]["prompts_path"]
        with open(prompts_path, "r") as f:
            self.prompts_config = yaml.safe_load(f)

        # Get background images
        bg_dir = Path(config["paths"]["backgrounds_dir"])
        self.background_images = sorted(list(bg_dir.glob("*.png")) + list(bg_dir.glob("*.jpg")))

        if not self.background_images:
            raise RuntimeError(f"No background images found in {bg_dir}")

        # Build job list
        self._build_job_list()

    def _build_job_list(self):
        """Build list of jobs based on defect distribution."""
        total = self.config["generation"]["total_images"]
        distribution = self.config["generation"]["defect_distribution"]

        # Calculate counts per defect type
        for defect_type, ratio in distribution.items():
            count = int(total * ratio)

            for i in range(count):
                job = {
                    "job_id": len(self.jobs),
                    "defect_type": defect_type,
                    "seed": random.randint(0, 2**32 - 1),
                    "background_image": random.choice(self.background_images),
                    "status": "pending"
                }
                self.jobs.append(job)

        # Shuffle for mixed generation (avoid sequential same-type batches)
        random.shuffle(self.jobs)

        print(f"Created {len(self.jobs)} jobs:")
        for defect_type in distribution.keys():
            count = sum(1 for j in self.jobs if j["defect_type"] == defect_type)
            print(f"  {defect_type}: {count} images")

    def get_next_job(self) -> Optional[Dict]:
        """
        Get next pending job.

        Returns:
            Job dict or None if all complete
        """
        if self.current_index >= len(self.jobs):
            return None

        job = self.jobs[self.current_index]

        return job

    def build_workflow(
        self,
        job: Dict,
        background_filename: str,
        mask_filename: str
    ) -> Dict:
        """
        Build ComfyUI workflow from template with job parameters.

        Args:
            job: Job dict from get_next_job()
            background_filename: Uploaded background filename on server
            mask_filename: Uploaded mask filename on server

        Returns:
            Complete workflow dict ready for submission
        """
        defect_type = job["defect_type"]
        seed = job["seed"]

        # Get defect-specific config
        if defect_type not in self.prompts_config["defect_prompts"]:
            raise ValueError(f"Unknown defect type: {defect_type}")

        defect_config = self.prompts_config["defect_prompts"][defect_type]

        # Deep copy workflow template
        workflow = json.loads(json.dumps(self.workflow_template))

        # Set checkpoint model from prompt templates (supports benchmark model selection)
        model_paths = self.prompts_config.get("model_paths", {})
        if model_paths.get("checkpoint"):
            workflow["1"]["inputs"]["ckpt_name"] = model_paths["checkpoint"]
        # Set external VAE if specified (requires VAELoader node "13" in workflow)
        if model_paths.get("vae") and "13" in workflow:
            workflow["13"]["inputs"]["vae_name"] = model_paths["vae"]

        # Update node parameters
        # Node 2: LoRA Loader
        workflow["2"]["inputs"]["lora_name"] = defect_config["lora_name"]
        workflow["2"]["inputs"]["strength_model"] = defect_config.get("lora_strength", 0.7)
        workflow["2"]["inputs"]["strength_clip"] = defect_config.get("lora_strength", 0.7)

        # Node 3: Positive prompt
        workflow["3"]["inputs"]["text"] = defect_config["positive"]

        # Node 4: Negative prompt — must use per-class negative to exclude other defect types
        if "negative" in defect_config:
            workflow["4"]["inputs"]["text"] = defect_config["negative"]

        # Node 5: Load background image
        workflow["5"]["inputs"]["image"] = background_filename

        # Detect workflow type by SaveImage node ID:
        #   img2img workflow:  node 9  = SaveImage (KSampler at node 7)
        #   inpaint workflow:  node 12 = SaveImage (KSampler at node 10, mask at node 6)
        output_prefix = f"{defect_type}_{job['job_id']:06d}"

        is_img2img = workflow.get("9", {}).get("class_type") == "SaveImage"

        if is_img2img:
            # img2img workflow (sd15-img2img-lora-defect-workflow.json)
            sampler_config = self.config["sampler"]
            workflow["7"]["inputs"]["seed"] = seed
            workflow["7"]["inputs"]["steps"] = sampler_config["steps"]
            workflow["7"]["inputs"]["cfg"] = sampler_config.get("cfg", 9.0)
            workflow["7"]["inputs"]["sampler_name"] = sampler_config["name"]
            workflow["7"]["inputs"]["scheduler"] = sampler_config["scheduler"]
            workflow["7"]["inputs"]["denoise"] = defect_config.get("denoise", 0.75)
            workflow["9"]["inputs"]["filename_prefix"] = output_prefix
        else:
            # inpaint workflow (sd15-lora-controlnet-inpaint-batch-api-workflow.json)
            # Node 6: Load mask image
            if "6" in workflow and mask_filename:
                workflow["6"]["inputs"]["image"] = mask_filename
            sampler_config = self.config["sampler"]
            workflow["10"]["inputs"]["seed"] = seed
            workflow["10"]["inputs"]["steps"] = sampler_config["steps"]
            workflow["10"]["inputs"]["cfg"] = sampler_config.get("cfg", 7.0)
            workflow["10"]["inputs"]["sampler_name"] = sampler_config["name"]
            workflow["10"]["inputs"]["scheduler"] = sampler_config["scheduler"]
            workflow["10"]["inputs"]["denoise"] = defect_config.get("denoise", 0.85)
            workflow["12"]["inputs"]["filename_prefix"] = output_prefix

        return workflow

    def mark_complete(self, job: Dict):
        """Mark job as complete and advance index."""
        job["status"] = "complete"
        self.current_index += 1
        self.completed_count += 1

    def mark_failed(self, job: Dict, error: str):
        """Mark job as failed and record error."""
        job["status"] = "failed"
        job["error"] = error
        self.failed_jobs.append(job)
        self.current_index += 1

    def get_output_path(self, job: Dict, is_mask: bool = False) -> Path:
        """
        Get output file path for job.

        Args:
            job: Job dict
            is_mask: True for mask file, False for image file

        Returns:
            Path object for output file
        """
        base_dir = Path(self.config["paths"]["output_base_dir"])

        if self.config["output"]["organize_by_defect"]:
            output_dir = base_dir / job["defect_type"]
        else:
            output_dir = base_dir

        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{job['defect_type']}_{job['job_id']:06d}"
        if is_mask:
            filename += "_mask.png"
        else:
            filename += ".png"

        return output_dir / filename

    def get_progress(self) -> Tuple[int, int, float]:
        """
        Get progress statistics.

        Returns:
            Tuple of (completed, total, percentage)
        """
        total = len(self.jobs)
        completed = self.completed_count
        percentage = (completed / total * 100) if total > 0 else 0
        return completed, total, percentage

    def get_state(self) -> Dict:
        """
        Get scheduler state for checkpointing.

        Returns:
            State dict
        """
        # Convert Path objects to strings for JSON serialization
        jobs_serializable = []
        for job in self.jobs:
            job_copy = job.copy()
            if "background_image" in job_copy and job_copy["background_image"] is not None:
                job_copy["background_image"] = str(job_copy["background_image"])
            jobs_serializable.append(job_copy)

        failed_jobs_serializable = []
        for job in self.failed_jobs:
            job_copy = job.copy()
            if "background_image" in job_copy and job_copy["background_image"] is not None:
                job_copy["background_image"] = str(job_copy["background_image"])
            failed_jobs_serializable.append(job_copy)

        return {
            "current_index": self.current_index,
            "completed_count": self.completed_count,
            "failed_jobs": failed_jobs_serializable,
            "jobs": jobs_serializable
        }

    def restore_state(self, state: Dict):
        """
        Restore scheduler state from checkpoint.

        Args:
            state: State dict from get_state()
        """
        self.current_index = state["current_index"]
        self.completed_count = state["completed_count"]
        self.failed_jobs = state["failed_jobs"]
        self.jobs = state["jobs"]

        # Convert background_image strings back to Path objects
        for job in self.jobs:
            if "background_image" in job and job["background_image"] is not None:
                job["background_image"] = Path(job["background_image"])

        for job in self.failed_jobs:
            if "background_image" in job and job["background_image"] is not None:
                job["background_image"] = Path(job["background_image"])

        print(f"Restored state: {self.completed_count}/{len(self.jobs)} complete")
