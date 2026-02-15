---
title: "The Data Mint - Synthetic Weld Defect X-ray Factory"
description: "ComfyUI+SD1.5+LoRA+ControlNet pipeline for 20K-100K synthetic weld defect X-ray images with auto-annotations"
status: in_progress
priority: P1
effort: 40h
branch: main
tags: [comfyui, stable-diffusion, lora, controlnet, synthetic-data, ndt, x-ray, weld-defect]
created: 2026-01-30
---

# The Data Mint - Implementation Plan

## Architecture Overview

```
[GDXray W0003] -> [Preprocess 512x512] -> [Train 5 LoRAs (kohya-ss)]
                                                    |
[Clean Backgrounds] -> [Procedural Masks] -> [ComfyUI Inpaint Pipeline] -> [Synthetic Image + Mask]
                                                    |
                                          [Post-Process: COCO+YOLO] -> [QA Filter] -> [Dataset Output]
```

**Hardware**: Dual Xeon E5-2696v4 (44c/88t) + RTX 3090 24GB + 64GB ECC RAM
**Stack**: SD 1.5 + LoRA (kohya-ss) + ControlNet v1.1 Inpaint + ComfyUI API + Python batch orchestration

## Phases

| # | Phase | Effort | Status | Dependencies |
|---|-------|--------|--------|-------------|
| 1 | [Environment Setup](phase-01-environment-setup.md) | 3h | **~90% done** | None |
| 2 | [Dataset Preprocessing](phase-02-dataset-preprocessing.md) | 4h | **complete** | Phase 1 |
| 3 | [LoRA Training](phase-03-lora-training.md) | 6h | **complete** | Phase 1, 2 |
| 4 | [ComfyUI Workflow Design](phase-04-comfyui-workflow-design.md) | 4h | **complete** | Phase 1, 3 |
| 5 | [Mask Generation Engine](phase-05-mask-generation-engine.md) | 4h | **complete** | Phase 2 |
| 6 | [Batch Production Automation](phase-06-batch-production-automation.md) | 6h | **complete** | Phase 4, 5 |
| 7 | [Post-Processing Pipeline](phase-07-post-processing-pipeline.md) | 4h | **complete** | Phase 5, 6 |
| 8 | [Quality Assurance](phase-08-quality-assurance.md) | 5h | **complete** | Phase 6, 7 |
| 9 | [Downstream Validation](phase-09-downstream-validation.md) | 4h | **complete** | Phase 7, 8 |

## Key Decisions

1. **SD 1.5 over SDXL**: Grayscale 512x512 sufficient, mature ControlNet ecosystem, low VRAM
2. **1 LoRA per defect type**: 5 separate LoRAs for independent quality control
3. **ControlNet Inpainting**: Mask = ground truth annotation (free bbox+segmentation)
4. **kohya-ss for production**: CLI-driven, comfyUI-Realtime-Lora for prototyping only
5. **COCO + YOLO dual export**: Maximum downstream model compatibility

## Throughput Target

- ~2-4s per image (512x512, 20 steps) -> 900-1800 images/hour
- 20K images: ~11-22 hours | 100K images: ~55-111 hours (2.3-4.6 days)

## Critical Path

Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 6 -> Phase 7 -> Phase 8 -> Phase 9
                         |
                     Phase 5 (parallel with Phase 3-4)

## Reports

- [Brainstorm](../reports/brainstorm-260130-0849-the-data-mint-xray-defect-synthetic-pipeline.md)
- [Research: ComfyUI/LoRA/ControlNet](research/researcher-01-comfyui-lora-controlnet.md)
- [Research: Masks/Annotations/QA](research/researcher-02-masks-annotations-qa.md)

---

## Validation Summary

**Validated:** 2026-01-30
**Questions asked:** 7

### Confirmed Decisions
- **LoRA training strategy**: Pilot crack LoRA first at rank 32, iterate until acceptable, apply learnings to remaining types. Rank 32 confirmed suitable for RTX 3090 + Dual Xeon 2696v4 hardware
- **Batch stability**: Checkpoint every 100 images + auto-restart ComfyUI on crash. Resume from last checkpoint
- **QA approach**: Skip FID/LPIPS (no X-ray domain standard). Use SSIM background check + visual 1-2% spot-check as Phase 8. Use downstream mAP (Phase 9) as primary quality metric
- **Pilot run**: 500 images (100/defect type) before full 20K-100K production

### Action Items (Plan Revisions Needed)
- [ ] **[CRITICAL] Defect types >5**: User confirmed GDXray W0003 has MORE than 5 defect types (undercut, burn-through, excess penetration, etc.). Phase 2 must parse annotations first to enumerate all types. Phase 3/5 LoRA count and mask generator count will increase accordingly
- [ ] **Phase 2 update**: Add step to parse W0003 annotation file and enumerate all defect types BEFORE designing LoRA training strategy. This is a prerequisite data discovery step
- [ ] **Phase 3 update**: LoRA count TBD based on Phase 2 enumeration. Update from "5 LoRAs" to "N LoRAs (1 per defect type, N determined in Phase 2)". May also need to group rare types
- [ ] **Phase 5 update**: Mask generator count TBD. May need additional morphology algorithms for undercut, burn-through, etc.
- [ ] **Phase 8 update**: Simplify to SSIM background check + annotation validation + visual spot-check. Remove FID/LPIPS evaluators. Add Phase 6 integration for 500-image pilot run as validation gate before full production
- [ ] **Phase 9 update**: mAP is now the PRIMARY quality metric (not just validation). Add pilot mAP check after 500-image run before scaling to 20K+
- [ ] **Add pilot gate**: Between Phase 6 and full production, insert 500-image pilot with visual QA + quick YOLOv8 test. If pilot passes, proceed to full scale
