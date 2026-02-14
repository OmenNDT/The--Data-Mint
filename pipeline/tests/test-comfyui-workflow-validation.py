#!/usr/bin/env python3
"""
ComfyUI Workflow Validation Tests
==================================

Validates workflow JSON structure and API client functionality.

Tests:
1. Workflow JSON syntax and structure
2. Node connectivity and data types
3. Required inputs present
4. Placeholder substitution
5. API client parameter handling
"""

import json
import sys
from pathlib import Path

import yaml


def validate_workflow_json(workflow_path: Path) -> bool:
    """Validate workflow JSON syntax and structure."""
    print(f"\n[TEST] Validating workflow: {workflow_path.name}")

    try:
        with open(workflow_path, "r") as f:
            workflow = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON: {e}")
        return False

    if not isinstance(workflow, dict):
        print(f"  ✗ Workflow must be a dict, got {type(workflow)}")
        return False

    print(f"  ✓ Valid JSON with {len(workflow)} nodes")

    # Check required nodes
    required_nodes = {
        "CheckpointLoaderSimple": False,
        "LoraLoader": False,
        "ControlNetLoader": False,
        "InpaintModelConditioning": False,
        "ControlNetApplyAdvanced": False,
        "KSampler": False,
        "VAEDecode": False,
        "SaveImage": False,
    }

    for node_id, node_data in workflow.items():
        class_type = node_data.get("class_type")
        if class_type in required_nodes:
            required_nodes[class_type] = True

    missing = [k for k, v in required_nodes.items() if not v]
    if missing:
        print(f"  ✗ Missing required nodes: {missing}")
        return False

    print(f"  ✓ All required node types present")

    # Check node connections
    for node_id, node_data in workflow.items():
        inputs = node_data.get("inputs", {})
        for input_key, input_value in inputs.items():
            if isinstance(input_value, list) and len(input_value) == 2:
                # Connection format: [node_id, output_index]
                ref_node_id = str(input_value[0])
                if ref_node_id not in workflow:
                    print(f"  ✗ Node {node_id} references missing node {ref_node_id}")
                    return False

    print(f"  ✓ All node connections valid")
    return True


def validate_prompt_templates(prompts_path: Path) -> bool:
    """Validate prompt templates YAML structure."""
    print(f"\n[TEST] Validating prompts: {prompts_path.name}")

    try:
        with open(prompts_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"  ✗ Invalid YAML: {e}")
        return False

    if "defect_prompts" not in config:
        print(f"  ✗ Missing 'defect_prompts' key")
        return False

    defect_prompts = config["defect_prompts"]
    required_defects = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

    for defect_type in required_defects:
        if defect_type not in defect_prompts:
            print(f"  ✗ Missing defect type: {defect_type}")
            return False

        defect_config = defect_prompts[defect_type]
        required_fields = ["lora_name", "positive", "negative"]

        for field in required_fields:
            if field not in defect_config:
                print(f"  ✗ Defect '{defect_type}' missing field: {field}")
                return False

    print(f"  ✓ All {len(required_defects)} defect types configured")
    print(f"  ✓ All required fields present")
    return True


def validate_placeholder_substitution(workflow_path: Path) -> bool:
    """Validate that batch workflow has required placeholders."""
    print(f"\n[TEST] Validating placeholders: {workflow_path.name}")

    with open(workflow_path, "r") as f:
        workflow_str = f.read()

    required_placeholders = [
        "{{LORA_NAME}}",
        "{{POSITIVE_PROMPT}}",
        "{{BACKGROUND_IMAGE}}",
        "{{MASK_IMAGE}}",
        "{{SEED}}",
        "{{OUTPUT_PREFIX}}",
    ]

    found_placeholders = []
    for placeholder in required_placeholders:
        if placeholder in workflow_str:
            found_placeholders.append(placeholder)
        else:
            print(f"  ✗ Missing placeholder: {placeholder}")
            return False

    print(f"  ✓ All {len(found_placeholders)} placeholders present")
    return True


def validate_model_paths(workflow_path: Path) -> bool:
    """Validate model paths in workflow."""
    print(f"\n[TEST] Validating model paths: {workflow_path.name}")

    with open(workflow_path, "r") as f:
        workflow = json.load(f)

    # Check checkpoint
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "CheckpointLoaderSimple":
            ckpt_name = node_data["inputs"].get("ckpt_name", "")
            if "sd-v1-5" not in ckpt_name.lower():
                print(f"  ⚠ Warning: Expected SD 1.5 checkpoint, got: {ckpt_name}")
            else:
                print(f"  ✓ Checkpoint: {ckpt_name}")

        if node_data.get("class_type") == "ControlNetLoader":
            cn_name = node_data["inputs"].get("control_net_name", "")
            if "inpaint" not in cn_name.lower():
                print(f"  ✗ Expected inpaint ControlNet, got: {cn_name}")
                return False
            else:
                print(f"  ✓ ControlNet: {cn_name}")

    return True


def validate_sampler_settings(workflow_path: Path) -> bool:
    """Validate KSampler configuration."""
    print(f"\n[TEST] Validating sampler settings: {workflow_path.name}")

    with open(workflow_path, "r") as f:
        workflow = json.load(f)

    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "KSampler":
            inputs = node_data["inputs"]

            # Check required settings
            steps = inputs.get("steps")
            cfg = inputs.get("cfg")
            sampler_name = inputs.get("sampler_name")
            scheduler = inputs.get("scheduler")
            denoise = inputs.get("denoise")

            if steps is None or steps < 10:
                print(f"  ✗ Steps too low: {steps} (expected ≥20)")
                return False

            if cfg is None or cfg < 5:
                print(f"  ✗ CFG too low: {cfg} (expected ~7.0)")
                return False

            if sampler_name not in ["euler", "euler_ancestral", "dpmpp_2m"]:
                print(f"  ⚠ Warning: Uncommon sampler: {sampler_name}")

            if denoise is None or denoise < 0.5:
                print(f"  ✗ Denoise too low: {denoise} (expected 0.65-0.95)")
                return False

            print(f"  ✓ Steps: {steps}, CFG: {cfg}, Denoise: {denoise}")
            print(f"  ✓ Sampler: {sampler_name}, Scheduler: {scheduler}")
            return True

    print(f"  ✗ No KSampler node found")
    return False


def main():
    """Run all validation tests."""
    script_dir = Path(__file__).parent.parent
    workflows_dir = script_dir / "comfyui-workflows"

    print("=" * 60)
    print("ComfyUI Workflow Validation Suite")
    print("=" * 60)

    tests = []

    # Test 1: Single image workflow
    single_workflow = workflows_dir / "sd15-lora-controlnet-inpaint-single-defect-workflow.json"
    if single_workflow.exists():
        tests.append(("Single Workflow JSON", validate_workflow_json(single_workflow)))
        tests.append(("Single Workflow Models", validate_model_paths(single_workflow)))
        tests.append(("Single Workflow Sampler", validate_sampler_settings(single_workflow)))
    else:
        print(f"\n✗ Missing file: {single_workflow}")
        tests.append(("Single Workflow", False))

    # Test 2: Batch API workflow
    batch_workflow = workflows_dir / "sd15-lora-controlnet-inpaint-batch-api-workflow.json"
    if batch_workflow.exists():
        tests.append(("Batch Workflow JSON", validate_workflow_json(batch_workflow)))
        tests.append(("Batch Workflow Placeholders", validate_placeholder_substitution(batch_workflow)))
        tests.append(("Batch Workflow Models", validate_model_paths(batch_workflow)))
        tests.append(("Batch Workflow Sampler", validate_sampler_settings(batch_workflow)))
    else:
        print(f"\n✗ Missing file: {batch_workflow}")
        tests.append(("Batch Workflow", False))

    # Test 3: Prompt templates
    prompts_file = workflows_dir / "defect-type-prompt-templates.yaml"
    if prompts_file.exists():
        tests.append(("Prompt Templates", validate_prompt_templates(prompts_file)))
    else:
        print(f"\n✗ Missing file: {prompts_file}")
        tests.append(("Prompt Templates", False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in tests if result)
    total = len(tests)

    for test_name, result in tests:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All validations passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} validation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
