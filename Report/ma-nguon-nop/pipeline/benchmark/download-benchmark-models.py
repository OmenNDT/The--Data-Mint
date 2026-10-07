"""
Download benchmark SD 1.5 checkpoints and VAE for LoRA training comparison.

Usage:
    python3 pipeline/benchmark/download-benchmark-models.py [--dry-run]
"""

import json
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
MODELS_DIR = PROJECT_ROOT / "models"
CHECKPOINT_DIR = MODELS_DIR / "checkpoints" / "benchmark"
VAE_DIR = MODELS_DIR / "vae"
REGISTRY_PATH = CHECKPOINT_DIR / "model-registry.json"

# HuggingFace models with direct single-file downloads
HF_MODELS = {
    "realvis": {
        "repo_id": "SG161222/Realistic_Vision_V5.1_noVAE",
        "filename": "Realistic_Vision_V5.1_fp16-no-ema.safetensors",
        "local_name": "realistic-vision-v51.safetensors",
    },
    "cyberreal": {
        "repo_id": "sam749/CyberRealistic-v4-2",
        "filename": "cyberrealistic_v42.safetensors",
        "local_name": "cyberrealistic-v42.safetensors",
    },
    "absreal": {
        "repo_id": "digiplay/AbsoluteReality_v1.8.1",
        "filename": "absolutereality_v181.safetensors",
        "local_name": "absolute-reality-v181.safetensors",
    },
}

# Osama03 - check for single safetensors first (per validation decision)
MEDXRAY_MODEL = {
    "repo_id": "Osama03/Medical-X-ray-image-generation-stable-diffusion",
    "local_name": "medical-xray-sd15.safetensors",
}

# CivitAI model
CIVITAI_MODEL = {
    "model_id": 81458,
    "local_name": "absolute-reality-v181.safetensors",
}

VAE_MODEL = {
    "repo_id": "stabilityai/sd-vae-ft-mse-original",
    "filename": "vae-ft-mse-840000-ema-pruned.safetensors",
    "local_name": "sd-vae-ft-mse.safetensors",
}


def download_hf_model(repo_id: str, filename: str, local_path: Path) -> bool:
    """Download a single file from HuggingFace hub."""
    if local_path.exists():
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"SKIP {local_path.name} (exists, {size_mb:.0f}MB)")
        return True

    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"Downloading {repo_id}/{filename}...")
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_path.parent,
            local_dir_use_symlinks=False,
        )
        # Rename to standard local name if different
        dl_path = Path(downloaded)
        if dl_path.name != local_path.name:
            dl_path.rename(local_path)
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"OK {local_path.name} ({size_mb:.0f}MB)")
        return True
    except Exception as e:
        logger.error(f"FAILED {repo_id}: {e}")
        return False


def check_osama03_repo() -> str | None:
    """Check Osama03 repo for single safetensors file (validation decision)."""
    try:
        from huggingface_hub import list_repo_files
        files = list_repo_files(MEDXRAY_MODEL["repo_id"])
        safetensors = [f for f in files if f.endswith(".safetensors")]
        ckpt = [f for f in files if f.endswith(".ckpt")]

        if safetensors:
            logger.info(f"Osama03: found safetensors: {safetensors}")
            return safetensors[0]
        if ckpt:
            logger.info(f"Osama03: found ckpt: {ckpt}")
            return ckpt[0]

        logger.warning(f"Osama03: no single file found. Files: {files[:10]}")
        # Check if diffusers format
        if "model_index.json" in files:
            logger.warning("Osama03: diffusers format detected — needs conversion")
        return None
    except Exception as e:
        logger.error(f"Osama03 repo check failed: {e}")
        return None


def download_medxray(local_path: Path) -> bool:
    """Download Osama03 Medical X-Ray model."""
    if local_path.exists():
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"SKIP {local_path.name} (exists, {size_mb:.0f}MB)")
        return True

    remote_file = check_osama03_repo()
    if remote_file is None:
        logger.error("Osama03: Cannot find downloadable file. Manual intervention needed.")
        return False

    return download_hf_model(
        MEDXRAY_MODEL["repo_id"], remote_file, local_path
    )


def download_civitai(model_id: int, local_path: Path) -> bool:
    """Download model from CivitAI API."""
    if local_path.exists():
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"SKIP {local_path.name} (exists, {size_mb:.0f}MB)")
        return True

    try:
        import requests
        url = f"https://civitai.com/api/download/models/{model_id}"
        logger.info(f"Downloading CivitAI model {model_id}...")
        response = requests.get(url, stream=True, allow_redirects=True, timeout=600)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0 and downloaded % (50 * 1024 * 1024) < 8192:
                    logger.info(f"  {downloaded / (1024*1024):.0f}/{total / (1024*1024):.0f} MB")
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"OK {local_path.name} ({size_mb:.0f}MB)")
        return True
    except Exception as e:
        logger.error(f"FAILED CivitAI {model_id}: {e}")
        if local_path.exists():
            local_path.unlink()
        return False


def verify_checkpoint(path: Path) -> bool:
    """Verify checkpoint loads without error."""
    try:
        from safetensors import safe_open
        with safe_open(str(path), framework="pt") as f:
            keys = f.keys()
            logger.info(f"  Verified: {len(keys)} tensors")
            return True
    except Exception as e:
        logger.error(f"  Verification FAILED: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download benchmark models")
    parser.add_argument("--dry-run", action="store_true", help="Check without downloading")
    args = parser.parse_args()

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    VAE_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    if args.dry_run:
        logger.info("=== DRY RUN — checking repo availability ===")
        check_osama03_repo()
        return

    # Download HuggingFace models (realvis, cyberreal, absreal)
    for model_key, info in HF_MODELS.items():
        local_path = CHECKPOINT_DIR / info["local_name"]
        ok = download_hf_model(info["repo_id"], info["filename"], local_path)
        results[model_key] = ok

    # Download Osama03
    local_path = CHECKPOINT_DIR / MEDXRAY_MODEL["local_name"]
    results["medxray"] = download_medxray(local_path)

    # Download VAE
    vae_path = VAE_DIR / VAE_MODEL["local_name"]
    results["vae"] = download_hf_model(VAE_MODEL["repo_id"], VAE_MODEL["filename"], vae_path)

    # Verify all files
    logger.info("\n=== Verification ===")
    for name, path in [
        ("medxray", CHECKPOINT_DIR / "medical-xray-sd15.safetensors"),
        ("realvis", CHECKPOINT_DIR / "realistic-vision-v51.safetensors"),
        ("absreal", CHECKPOINT_DIR / "absolute-reality-v181.safetensors"),
        ("cyberreal", CHECKPOINT_DIR / "cyberrealistic-v42.safetensors"),
        ("vae", VAE_DIR / "sd-vae-ft-mse.safetensors"),
    ]:
        if path.exists():
            logger.info(f"{name}: {path.stat().st_size / (1024*1024):.0f}MB")
            verify_checkpoint(path)
        else:
            logger.warning(f"{name}: NOT FOUND at {path}")

    # Summary
    logger.info("\n=== Summary ===")
    for k, v in results.items():
        logger.info(f"  {k}: {'OK' if v else 'FAILED'}")

    if all(results.values()):
        logger.info("All downloads successful!")
    else:
        failed = [k for k, v in results.items() if not v]
        logger.error(f"Failed: {failed}")


if __name__ == "__main__":
    main()
