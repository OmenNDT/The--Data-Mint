"""Config Preset Manager - Tiered presets + full parameter overrides."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml

from .pipeline_orchestrator import PipelineConfig
from .launcher_utils import resolve_pipeline_path

logger = logging.getLogger(__name__)


@dataclass
class PresetInfo:
    """Information about a preset."""
    name: str
    description: str
    estimated_minutes: int
    file_path: Path


@dataclass
class RuntimeEstimate:
    """Estimated runtime breakdown."""
    generation_minutes: float
    post_processing_minutes: float
    qa_minutes: float
    validation_minutes: float
    total_minutes: float


class ConfigPresetManager:
    """Manages tiered config presets and user overrides."""

    # Throughput estimates (based on RTX 3090 benchmarks)
    GENERATION_THROUGHPUT = 1097  # images per hour
    POST_PROCESSING_THROUGHPUT = 450  # images per hour
    VALIDATION_EPOCHS_PER_HOUR = 50  # epochs per hour per experiment

    def __init__(
        self,
        base_config_path: Optional[str] = None,
        presets_dir: Optional[str] = None
    ):
        """Initialize ConfigPresetManager.

        Args:
            base_config_path: Path to base config YAML (default: config/batch-config.yaml)
            presets_dir: Path to presets directory (default: config/presets)
        """
        self.pipeline_dir = resolve_pipeline_path(".")

        self.base_config_path = (
            Path(base_config_path)
            if base_config_path
            else self.pipeline_dir / "config" / "batch-config.yaml"
        )

        self.presets_dir = (
            Path(presets_dir)
            if presets_dir
            else self.pipeline_dir / "config" / "presets"
        )

        logger.info(f"ConfigPresetManager initialized")
        logger.info(f"  Base config: {self.base_config_path}")
        logger.info(f"  Presets dir: {self.presets_dir}")

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        """Save YAML file."""
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def write_effective_config(self, config: Dict[str, Any]) -> str:
        """Write a fully-merged config (base + preset + UI overrides) to a temp
        YAML file and return its path.

        Phase 6 (batch-production-main.py) only reads `--config <file>`, so any
        UI choice such as the dataset/backgrounds folder must be baked into an
        actual YAML file. Without this the pipeline silently falls back to the
        default batch-config.yaml and ignores everything picked in the UI.
        """
        out_dir = self.base_config_path.parent / "_generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "effective-run-config.yaml"
        self._save_yaml(out_path, config)
        logger.info(f"Wrote effective run config: {out_path}")
        return str(out_path)

    def list_presets(self) -> List[PresetInfo]:
        """List all available presets.

        Returns:
            List of PresetInfo objects
        """
        presets = []

        if not self.presets_dir.exists():
            logger.warning(f"Presets directory not found: {self.presets_dir}")
            return presets

        for yaml_file in self.presets_dir.glob("*.yaml"):
            try:
                data = self._load_yaml(yaml_file)
                presets.append(PresetInfo(
                    name=data.get("name", yaml_file.stem),
                    description=data.get("description", ""),
                    estimated_minutes=data.get("estimated_minutes", 0),
                    file_path=yaml_file
                ))
            except Exception as e:
                logger.warning(f"Failed to load preset {yaml_file}: {e}")

        # Sort by estimated time
        presets.sort(key=lambda p: p.estimated_minutes)

        return presets

    def load_preset(self, name: str) -> Dict[str, Any]:
        """Load a preset and merge with base config.

        Args:
            name: Preset name (without .yaml extension)

        Returns:
            Complete config dict
        """
        # Load base config
        base_config = {}
        if self.base_config_path.exists():
            base_config = self._load_yaml(self.base_config_path)
            logger.info(f"Loaded base config: {self.base_config_path}")
        else:
            logger.warning(f"Base config not found: {self.base_config_path}")

        # Load preset
        preset_path = self.presets_dir / f"{name}.yaml"
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset not found: {preset_path}")

        preset_config = self._load_yaml(preset_path)
        logger.info(f"Loaded preset: {preset_path}")

        # Merge preset over base (preset values win)
        merged = self._deep_merge(base_config, preset_config)

        return merged

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dicts, override wins."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def apply_overrides(
        self,
        config: Dict[str, Any],
        overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply user overrides to config.

        Args:
            config: Base config dict
            overrides: Flat dict of overrides (e.g., {"total_images": 1000})

        Returns:
            Merged config with overrides applied
        """
        # Map flat keys to nested paths
        key_mapping = {
            "total_images": ("generation", "total_images"),
            "epochs": ("validation", "epochs"),
            "model_size": ("validation", "model_size"),
            "batch_size": ("validation", "batch_size"),
            "ratios": ("validation", "ratios"),
            "train_ratio": ("post_processing", "train_ratio"),
            "val_ratio": ("post_processing", "val_ratio"),
            "test_ratio": ("post_processing", "test_ratio"),
        }

        result = config.copy()

        for flat_key, value in overrides.items():
            if flat_key in key_mapping:
                section, key = key_mapping[flat_key]
                if section not in result:
                    result[section] = {}
                result[section][key] = value
            else:
                # Direct key
                result[flat_key] = value

        return result

    def estimate_runtime(self, config: Dict[str, Any]) -> RuntimeEstimate:
        """Estimate runtime for a config.

        Args:
            config: Configuration dict

        Returns:
            RuntimeEstimate with breakdown
        """
        # Extract params
        total_images = config.get("generation", {}).get("total_images", 500)
        epochs = config.get("validation", {}).get("epochs", 20)
        batch_size = config.get("validation", {}).get("batch_size", 16)
        ratios = config.get("validation", {}).get("ratios", [0.0, 0.5, 1.0])
        phases = config.get("phases_to_run", [6, 7, 8])

        # Calculate generation time
        gen_minutes = (total_images / self.GENERATION_THROUGHPUT) * 60 if 6 in phases else 0

        # Calculate post-processing time
        pp_minutes = (total_images / self.POST_PROCESSING_THROUGHPUT) * 60 if 7 in phases else 0

        # Calculate QA time (fixed ~10 min)
        qa_minutes = 10 if 8 in phases else 0

        # Calculate validation time
        num_experiments = len(ratios)
        val_minutes = (
            num_experiments * epochs / self.VALIDATION_EPOCHS_PER_HOUR * 60
            if 9 in phases else 0
        )

        total = gen_minutes + pp_minutes + qa_minutes + val_minutes

        return RuntimeEstimate(
            generation_minutes=gen_minutes,
            post_processing_minutes=pp_minutes,
            qa_minutes=qa_minutes,
            validation_minutes=val_minutes,
            total_minutes=total
        )

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate config before passing to orchestrator.

        Args:
            config: Configuration dict to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required sections
        if "generation" not in config:
            errors.append("Missing 'generation' section in config")

        if "validation" not in config:
            errors.append("Missing 'validation' section in config")

        # Validate generation
        gen = config.get("generation", {})
        total_images = gen.get("total_images", 0)
        if total_images <= 0:
            errors.append("total_images must be > 0")

        # Validate defect distribution
        defect_dist = gen.get("defect_distribution", {})
        if defect_dist:
            total = sum(defect_dist.values())
            if abs(total - 1.0) > 0.01:
                errors.append(f"defect_distribution must sum to 1.0, got {total}")

        # Validate validation params
        val = config.get("validation", {})
        epochs = val.get("epochs", 0)
        if epochs <= 0:
            errors.append("epochs must be > 0")

        batch_size = val.get("batch_size", 0)
        if batch_size <= 0:
            errors.append("batch_size must be > 0")

        ratios = val.get("ratios", [])
        if not ratios:
            errors.append("ratios cannot be empty")

        # Validate split ratios (only if post_processing section exists)
        pp = config.get("post_processing", {})
        if pp:
            train_ratio = pp.get("train_ratio", 0.7)
            val_ratio = pp.get("val_ratio", 0.2)
            test_ratio = pp.get("test_ratio", 0.1)
            if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 0.01:
                errors.append("train_ratio + val_ratio + test_ratio must equal 1.0")

        return errors

    def config_to_pipeline_config(self, config: Dict[str, Any]) -> PipelineConfig:
        """Convert config dict to PipelineConfig dataclass.

        Args:
            config: Configuration dict

        Returns:
            PipelineConfig instance
        """
        gen = config.get("generation", {})
        val = config.get("validation", {})
        pp = config.get("post_processing", {})
        paths = config.get("paths", {})

        return PipelineConfig(
            dataset_path=config.get("dataset_path", ""),
            total_images=gen.get("total_images", 500),
            pilot_mode=gen.get("pilot_mode", False),
            train_ratio=pp.get("train_ratio", 0.70),
            val_ratio=pp.get("val_ratio", 0.20),
            test_ratio=pp.get("test_ratio", 0.10),
            ssim_sample_size=config.get("qa", {}).get("ssim_sample_size", 100),
            real_yolo_dir=config.get("real_yolo_dir", ""),
            synth_yolo_dir=config.get("synth_yolo_dir", ""),
            model_size=val.get("model_size", "n"),
            epochs=val.get("epochs", 100),
            batch_size=val.get("batch_size", 16),
            ratios=val.get("ratios", [0.0, 0.5, 1.0]),
            output_dir=paths.get("output_base_dir", "output"),
            config_path=config.get("config_path", "config/batch-config.yaml"),
        )

    def save_custom_preset(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> Path:
        """Save a custom preset.

        Args:
            name: Preset name (without .yaml)
            config: Configuration to save

        Returns:
            Path to saved preset file
        """
        preset_path = self.presets_dir / f"{name}.yaml"

        # Extract relevant parts for preset
        preset_data = {
            "name": name,
            "description": config.get("description", "Custom preset"),
            "generation": config.get("generation", {}),
            "validation": config.get("validation", {}),
            "phases_to_run": config.get("phases_to_run", [6, 7, 8]),
        }

        self._save_yaml(preset_path, preset_data)
        logger.info(f"Saved custom preset: {preset_path}")

        return preset_path
