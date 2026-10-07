# Phase 05 — Đa Khuyết Tật Trên Một Ảnh

**Ưu tiên**: P1 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 12h · **Phụ thuộc**: Phase 02, Phase 04

## Context Links

- [plan.md](./plan.md) · [Phase 02](./phase-02-seamless-blend-restore-diffusion.md) · [Phase 04](./phase-04-mask-morphology-and-polarity-fixes.md)
- Post-processing hiện tại: `pipeline/post_processing/`

## Overview

Hiện mỗi ảnh đúng một khuyết tật một lớp. Phim RT thật thường có nhiều khuyết tật khác lớp cùng xuất hiện. Phase này cho phép soạn "cảnh" 2–4 khuyết tật trên một ảnh, kèm cập nhật đồng bộ COCO/YOLO và QA.

## Key Insights

- Mỗi khuyết tật cần một LoRA khác nhau ⇒ **không thể** sinh cả cảnh trong một lần gọi ComfyUI. Phải sinh tuần tự: ảnh kết quả của khuyết tật thứ n làm nền cho khuyết tật thứ n+1.
- Sinh tuần tự nhân chi phí GPU theo số khuyết tật ⇒ ảnh hưởng thông lượng, phải tính vào ngân sách Phase 07.
- Một số cặp lớp không đồng xuất hiện về mặt vật lý (undercut ở chân mối vs LOP ở chân đường hàn tranh chỗ). Cần ma trận tương thích, không ghép ngẫu nhiên.
- Cần tránh chồng lấn mask: hai khuyết tật đè nhau làm nhãn vô nghĩa.
- Phase 7/8 hiện giả định một nhãn/ảnh — phải rà lại `mask-to-annotation-converter.py`, `coco-dataset-builder.py`, `yolo-dataset-builder.py`, `annotation-validator.py`.

## Requirements

**Chức năng**
- `SceneComposer` sinh mô tả cảnh: danh sách `(defect_type, seed, vị trí)` với 1–4 phần tử.
- Ma trận tương thích lớp + ràng buộc vị trí theo hình học mối hàn (từ Phase 04).
- Kiểm chồng lấn: IoU giữa các mask trong cảnh = 0, khoảng cách biên tối thiểu cấu hình được.
- Sinh tuần tự trong ComfyUI, kèm tích luỹ nhãn.
- Phân bố số khuyết tật/ảnh cấu hình được (mặc định: 60% một, 25% hai, 10% ba, 5% bốn).
- Giữ chế độ một-khuyết-tật làm mặc định (`scene.enabled: false`).

**Phi chức năng**
- Không phá checkpoint/resume hiện có: một cảnh = một job nguyên tử.
- COCO/YOLO xuất ra load được bằng công cụ chuẩn.

## Architecture

```
pipeline/scene/
├── scene-composer.py                  # sinh mô tả cảnh
├── defect-cooccurrence-matrix.yaml    # cặp lớp cho phép/cấm
└── scene-overlap-validator.py         # kiểm chồng lấn + khoảng cách

batch-production-main.py
  for defect in scene.defects:          # tuần tự, ảnh trước làm nền ảnh sau
      mask, thickness = generate(defect)
      raw   = comfyui_inpaint(current_image, mask, lora[defect])
      current_image = blend + render(raw, current_image, thickness)
      annotations.append(mask)
```

## Related Code Files

**Tạo**: `pipeline/scene/scene-composer.py`, `pipeline/scene/scene-overlap-validator.py`, `pipeline/scene/defect-cooccurrence-matrix.yaml`
**Sửa**: `batch-production-main.py` (vòng lặp trong cảnh), `batch-job-scheduler.py` (job = cảnh), `checkpoint-state-manager.py` (trạng thái cảnh), `post_processing/mask-to-annotation-converter.py`, `post_processing/coco-dataset-builder.py`, `post_processing/yolo-dataset-builder.py`, `qa/annotation-validator.py`, `config/batch-config.yaml` (khối `scene`)

## Implementation Steps

1. `defect-cooccurrence-matrix.yaml`: ma trận 12×12 `allow/deny` + ghi chú lý do NDT. Soạn nháp rồi nhờ chuyên gia rà.
2. `scene-composer.py`: bốc số khuyết tật theo phân bố, bốc lớp theo ma trận tương thích, gán vùng đặt theo hình học mối hàn.
3. `scene-overlap-validator.py`: sinh thử mask, kiểm IoU = 0 và khoảng cách biên ≥ `min_separation_px`; bốc lại tối đa N lần rồi giảm số khuyết tật.
4. Đổi đơn vị job trong scheduler: một job = một cảnh, `job["defects"] = [...]`.
5. Sửa vòng lặp chính thành vòng lặp trong cảnh; ảnh sau mỗi bước làm nền bước kế; chỉ ghi file một lần ở cuối.
6. Tích luỹ nhãn: mỗi khuyết tật lưu một annotation mask riêng `{scene_id}_{k}_{class}_mask.png` + `scene.json` liệt kê.
7. Cập nhật `mask-to-annotation-converter.py` đọc nhiều mask/ảnh; COCO nhiều `annotations` cùng `image_id`; YOLO nhiều dòng.
8. Cập nhật `annotation-validator.py`: kiểm chồng lấn bbox, kiểm số nhãn khớp `scene.json`.
9. Cập nhật checkpoint để cảnh dở dang được sinh lại từ đầu (nguyên tử).
10. Chạy A/B `p05-multidefect` với 200 cảnh; kiểm bằng mắt 30 cảnh.

## Todo List

- [ ] `defect-cooccurrence-matrix.yaml` (nháp + rà soát NDT)
- [ ] `scene-composer.py`
- [ ] `scene-overlap-validator.py`
- [ ] Scheduler: job = cảnh
- [ ] Vòng lặp trong cảnh ở `batch-production-main.py`
- [ ] Ghi nhiều annotation mask + `scene.json`
- [ ] COCO builder nhiều annotation/ảnh
- [ ] YOLO builder nhiều dòng/ảnh
- [ ] `annotation-validator.py` kiểm cảnh
- [ ] Checkpoint nguyên tử theo cảnh
- [ ] A/B `p05-multidefect` + kiểm mắt 30 cảnh

## Success Criteria

- Sinh được cảnh 1–4 khuyết tật đúng phân bố cấu hình (sai lệch < 2%).
- IoU giữa mọi cặp mask trong cảnh = 0; khoảng cách biên ≥ ngưỡng ở 100% cảnh.
- COCO JSON load bằng `pycocotools` không lỗi; YOLO load bằng `ultralytics` không cảnh báo.
- Không có cặp lớp bị cấm nào xuất hiện cùng ảnh.
- Đường một-khuyết-tật (`scene.enabled: false`) cho kết quả không đổi so với Phase 04.
- Ảnh khuyết tật thứ 2–4 không làm hỏng khuyết tật trước (kiểm bằng IoU mask trước/sau ≥ 0,95).

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Sinh tuần tự khiến inpaint lần sau xoá khuyết tật lần trước | Mask inpaint bước sau phải loại trừ vùng khuyết tật đã có; kiểm bằng IoU trước/sau |
| Thông lượng giảm theo số khuyết tật | Chấp nhận ở phase này; Phase 07 bù bằng batch queue |
| Ma trận tương thích soạn sai về mặt NDT | Đánh dấu rõ là nháp, cần chuyên gia duyệt trước khi chạy sản xuất |
| Phase 7/8 hồi quy | Giữ `scene.enabled: false` mặc định; chạy bộ test hiện có trước/sau |

## Security Considerations

Không phát sinh.

## Next Steps

→ [Phase 06](./phase-06-label-fidelity-and-quality-gate.md).
