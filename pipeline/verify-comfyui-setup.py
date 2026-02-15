"""Verify ComfyUI is running and can generate SD 1.5 test image via API.

Usage:
    1. Start ComfyUI first: python main.py --listen 0.0.0.0 --port 8188
    2. Run this script: python verify-comfyui-setup.py

Checks:
    - ComfyUI API reachable at localhost:8188
    - SD 1.5 checkpoint available
    - ControlNet inpaint model available
    - Generate 512x512 test image
"""

import json
import sys
import time
import requests

COMFYUI_URL = "http://127.0.0.1:8188"


def check_api_reachable():
    """Check if ComfyUI API is running."""
    try:
        resp = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        resp.raise_for_status()
        stats = resp.json()
        print(f"[OK] ComfyUI API reachable")
        vram = stats.get("devices", [{}])[0]
        if vram:
            total = vram.get("vram_total", 0) / (1024**3)
            free = vram.get("vram_free", 0) / (1024**3)
            print(f"     GPU: {vram.get('name', 'unknown')} | VRAM: {free:.1f}GB free / {total:.1f}GB total")
        return True
    except requests.ConnectionError:
        print(f"[FAIL] Cannot connect to {COMFYUI_URL}")
        print("       Start ComfyUI first: python main.py --listen 0.0.0.0 --port 8188")
        return False
    except Exception as e:
        print(f"[FAIL] API error: {e}")
        return False


def check_models():
    """Check if required models are loaded."""
    try:
        resp = requests.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple", timeout=5)
        data = resp.json()
        checkpoints = data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        sd15_found = any("sd-v1-5" in c.lower() or "v1-5" in c.lower() for c in checkpoints)
        print(f"[{'OK' if sd15_found else 'FAIL'}] SD 1.5 checkpoint: {'found' if sd15_found else 'NOT FOUND'}")
        print(f"     Available checkpoints: {checkpoints}")

        resp2 = requests.get(f"{COMFYUI_URL}/object_info/ControlNetLoader", timeout=5)
        data2 = resp2.json()
        controlnets = data2["ControlNetLoader"]["input"]["required"]["control_net_name"][0]
        inpaint_found = any("inpaint" in c.lower() for c in controlnets)
        canny_found = any("canny" in c.lower() for c in controlnets)
        print(f"[{'OK' if inpaint_found else 'FAIL'}] ControlNet inpaint: {'found' if inpaint_found else 'NOT FOUND'}")
        print(f"[{'OK' if canny_found else 'FAIL'}] ControlNet canny: {'found' if canny_found else 'NOT FOUND'}")
        print(f"     Available ControlNets: {controlnets}")

        return sd15_found and inpaint_found
    except Exception as e:
        print(f"[FAIL] Model check error: {e}")
        return False


def generate_test_image():
    """Queue a simple SD 1.5 txt2img workflow and wait for result."""
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 10,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd-v1-5-pruned-emaonly.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "X-ray radiograph of a metal weld joint, grayscale, high contrast",
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "color, photograph, blurry", "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "verify_test", "images": ["8", 0]},
        },
    }

    try:
        print("[...] Queuing test image generation (512x512, 10 steps)...")
        resp = requests.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow},
            timeout=10,
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        print(f"     Prompt ID: {prompt_id}")

        # Poll for completion
        for i in range(60):
            time.sleep(2)
            hist = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5).json()
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if "9" in outputs and outputs["9"].get("images"):
                    img = outputs["9"]["images"][0]
                    print(f"[OK] Test image generated: {img['filename']}")
                    return True
                status = hist[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    print(f"[FAIL] Generation error: {status.get('messages', 'unknown')}")
                    return False

        print("[FAIL] Generation timed out after 120s")
        return False
    except Exception as e:
        print(f"[FAIL] Generation error: {e}")
        return False


def main():
    print("=" * 50)
    print("ComfyUI Phase 1 Verification")
    print("=" * 50)

    if not check_api_reachable():
        sys.exit(1)

    if not check_models():
        print("\n[!] Missing models. Verify files in comfyui/models/")
        sys.exit(1)

    if not generate_test_image():
        print("\n[!] Test generation failed")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("ALL CHECKS PASSED - Phase 1 Environment Ready")
    print("=" * 50)


if __name__ == "__main__":
    main()
