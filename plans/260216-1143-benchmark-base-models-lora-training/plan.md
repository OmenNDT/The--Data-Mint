---
title: "Benchmark 4 SD 1.5 Base Models for LoRA Training"
description: "Compare Medical X-Ray, Realistic Vision, AbsoluteReality, CyberRealistic against vanilla SD 1.5 for weld defect generation quality"
status: complete
priority: P1
effort: 14d
branch: master
tags: [benchmark, lora, sd15, base-model, evaluation]
created: 2026-02-16
---

# Benchmark Base Models for LoRA Training

## Goal
Find if domain-specific or photorealistic SD 1.5 checkpoints produce better weld defect textures after LoRA fine-tuning vs current vanilla SD 1.5 baseline.

## Models Under Test
| ID | Model | Source | VAE |
|----|-------|--------|-----|
| baseline | sd-v1-5-pruned-emaonly | Current production | Built-in |
| medxray | Osama03 Medical X-Ray | HuggingFace | External (sd-vae-ft-mse) |
| realvis | Realistic Vision V5.1 | HuggingFace | External (sd-vae-ft-mse) |
| absreal | AbsoluteReality v1.8.1 | CivitAI | External (sd-vae-ft-mse) |
| cyberreal | CyberRealistic V4.2 | HuggingFace | Built-in |

## Phases

| # | Phase | Effort | Status | File |
|---|-------|--------|--------|------|
| 1 | Download & Setup | 2h | [COMPLETE] | [phase-01](phase-01-download-and-setup.md) |
| 2 | Generate Training Configs | 3h | [COMPLETE] | [phase-02](phase-02-generate-training-configs.md) |
| 3 | Pipeline Integration | 4h | [COMPLETE] | [phase-03](phase-03-pipeline-integration.md) |
| 4 | LoRA Training Execution | 5d | [COMPLETE] | [phase-04](phase-04-lora-training-execution.md) |
| 5 | Pilot Generation | 3h | [COMPLETE] | [phase-05](phase-05-pilot-generation.md) |
| 6 | Evaluation Pipeline | 4h | [COMPLETE] | [phase-06](phase-06-evaluation-pipeline.md) |
| 7 | YOLOv8 Validation | 3d | [COMPLETE] | [phase-07](phase-07-yolov8-validation.md) |

## Key Dependencies
- All 4 checkpoints downloaded and verified before Phase 2
- Phase 2 (configs) + Phase 3 (pipeline) must complete before Phase 4 (training)
- Phase 4 (training) completes before Phase 5 (generation)
- Phase 6 selects top 2 models for Phase 7

## Critical Constraints
- SD 1.5 architecture only (reuse existing ControlNet v1.1)
- 512x512 resolution
- Do NOT modify production configs -- benchmark code is additive
- Hardware: RTX 3090 24GB, Dual Xeon 44c/88t, 64GB RAM

## Success Criteria
1. At least 1 alternative achieves higher mAP than baseline on YOLOv8 validation
2. Defect textures judged more realistic in visual comparison
3. No regression in pipeline stability

## Research References
- [Kohya Multi-Model Training](research/researcher-01-kohya-multi-model-training.md)
- [Evaluation Pipeline Design](research/researcher-02-evaluation-pipeline-design.md)
- [Brainstorm](../../plans/reports/brainstorm-260216-1143-base-model-selection-for-lora-training.md)

---

## Validation Log

### Session 1 — 2026-02-16
**Trigger:** Initial plan validation before implementation
**Questions asked:** 6

#### Questions & Answers

1. **[Assumption]** Plan giữ hyperparams giống hệt nhau cho tất cả 4 model (LR=5e-5, rank=32, epochs=20) để so sánh công bằng. Nhưng research cho thấy photorealistic models có thể cần LR thấp hơn (3e-5). Bạn muốn giữ nguyên hay cho phép điều chỉnh?
   - Options: Giữ giống nhau | Cho phép tùy chỉnh ngay | Chạy 2 round
   - **Answer:** Giữ giống nhau (Recommended)
   - **Rationale:** Fair comparison is priority. Use LR Fallback Strategy only if loss diverges during training.

2. **[Risk]** Phase 7 cần real test set (ảnh X-ray thật có annotation YOLO) để đánh giá mAP. Bạn đã có sẵn annotated real test set chưa?
   - Options: Có, đã có sẵn | Có ảnh nhưng chưa có labels | Chưa có
   - **Answer:** Có, đã có sẵn
   - **Custom input:** Cần sửa `/home/sontn/Projects/The Data Mint/output/dataset-test/yolo/data.yaml` và `/home/sontn/Projects/The Data Mint/output/dataset-test/annotations/coco_test.json` để đúng với thực tế mới (chỉ training cho crack)
   - **Rationale:** Real test set exists but paths need updating. Current test set may only cover crack defect type — needs verification and possible expansion for full 5-defect evaluation.

3. **[Tradeoff]** Về sampler: Production dùng euler/normal. Photorealistic models recommend DPM++ SDE Karras. Giữ euler cho tất cả hay cho phép đổi sampler?
   - Options: Giữ euler cho fair | Đổi sang DPM++ cho tất cả | Mỗi model dùng sampler riêng
   - **Answer:** Giữ euler cho fair (Recommended)
   - **Rationale:** Single variable isolation — only checkpoint changes, everything else stays constant. If a model wins with euler, it's genuinely better.

4. **[Risk]** Nếu Osama03 Medical X-Ray model là diffusers format (không phải single .safetensors), cần convert. Nếu convert fail thì sao?
   - Options: Bỏ qua Osama03, thay model khác | Cố gắng convert, skip nếu fail | Tìm single safetensors trước
   - **Answer:** Tìm single safetensors trước
   - **Rationale:** Check HuggingFace repo for direct .safetensors file before planning complex conversion. Saves effort.

5. **[Scope]** Real test set nằm ở đâu?
   - Options: output/dataset/yolo/test/ | dataset/gdxray/test/ | Thư mục khác
   - **Answer:** Custom path
   - **Custom input:** `output/dataset-test/yolo/data.yaml` and `output/dataset-test/annotations/coco_test.json` — needs fixing for crack-only training context
   - **Rationale:** Critical for Phase 7. Test set YAML needs updating to reflect current defect scope before validation runs.

6. **[Scope]** Nếu không model nào thắng baseline, coi benchmark là thành công?
   - Options: Có, giữ baseline = thành công | Không, phải có improvement
   - **Answer:** Không, phải có improvement
   - **Rationale:** Benchmark MUST produce at least 1 model with higher mAP. If all fail, need further investigation (more models, hyperparams tuning, SDXL).

#### Confirmed Decisions
- **Hyperparams**: Identical across all models (5e-5 LR, rank 32, 20 epochs). LR fallback only if diverging.
- **Sampler**: euler/normal for all models. No per-model sampler customization.
- **Osama03**: Check for single safetensors first, don't pre-plan conversion pipeline.
- **Success bar**: Must beat baseline mAP. No "moral victory" for benchmark alone.
- **Real test set**: At `output/dataset-test/` — needs YAML/JSON path fix before Phase 7.

#### Action Items
- [ ] Phase 1: Check Osama03 HuggingFace repo for single `.safetensors` file before download
- [ ] Phase 7: Update real test set data.yaml paths at `output/dataset-test/yolo/data.yaml`
- [ ] Phase 7: Verify test set covers all 5 defect types (currently may be crack-only)
- [ ] Plan: Update success criteria to mandate improvement (remove "or tie" language)

#### Impact on Phases
- **Phase 1**: Add step to check Osama03 repo file listing before download. If no single safetensors, try conversion; if conversion fails, substitute with Prompt2MedImage or epiCRealism.
- **Phase 7**: Use real test set at `output/dataset-test/yolo/data.yaml`. Add pre-validation step to verify/fix data.yaml paths and ensure all 5 defect types have test images.
