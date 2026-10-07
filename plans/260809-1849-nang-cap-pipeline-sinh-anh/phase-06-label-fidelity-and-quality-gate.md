# Phase 06 — Nhãn Đo Từ Ảnh Thực Sinh & Cổng Chất Lượng

**Ưu tiên**: P1 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 8h · **Phụ thuộc**: Phase 03, Phase 05

## Context Links

- [plan.md](./plan.md) · [Phase 03](./phase-03-radiographic-physics-rendering.md) · [Phase 05](./phase-05-multi-defect-scene-composition.md)
- Hạ tầng liên quan: `pipeline/auto_labeler/` (YOLO + SAM), `pipeline/qa/`

## Overview

Nhãn hiện lấy từ mask đầu vào — tức là **ý định**, không phải **kết quả**. Sau Phase 02/03, khuyết tật thực sinh có vùng chuyển tiếp và biên mềm, nên nhãn từ mask đầu vào sẽ vừa chật vừa lệch. Phase này đo nhãn từ chính ảnh sinh ra, và chặn lại những ảnh hỏng trước khi vào dataset.

## Key Insights

- Ta có **ảnh nền gốc** và **ảnh cuối** cho từng khuyết tật ⇒ tính được `delta = |final − background|` sạch, không cần dò tìm mù như auto-labeler.
- Delta-image cho nhãn trung thực hơn cả SAM: không phải suy đoán, mà là đo trực tiếp thay đổi do khuyết tật gây ra.
- Cần một cổng chặn: khuyết tật quá mờ (SD/LoRA không vẽ ra gì), quá lớn (LoRA loạn), lệch khỏi vùng mối hàn, hoặc lệch cực tính — đều phải loại.
- `auto_labeler/` (YOLO+SAM) vẫn hữu ích để **kiểm chéo độc lập**, không phải nguồn nhãn chính.

## Requirements

**Chức năng**
- Sinh nhãn từ delta-image: ngưỡng thích ứng theo nhiễu nền, làm sạch hình thái, lấy contour.
- Xuất cả bbox và polygon segmentation cho COCO.
- Cổng chất lượng với 5 phép kiểm, cấu hình ngưỡng, ghi lý do loại.
- Báo cáo tỉ lệ loại theo lớp để phát hiện lớp có LoRA yếu.

**Phi chức năng**
- < 30 ms/khuyết tật.
- Ảnh bị loại được lưu riêng kèm lý do, không xoá thẳng.

## Architecture

```
pipeline/labeling/
├── delta-image-annotator.py       # ảnh cuối − nền ⇒ contour ⇒ bbox/polygon
├── defect-quality-gate.py         # 5 phép kiểm chấp nhận/loại
└── label-agreement-reporter.py    # so nhãn đo được vs mask đầu vào

output/rejected/{reason}/          # ảnh bị loại kèm sidecar JSON
```

5 phép kiểm của cổng chất lượng:

| Kiểm | Loại khi |
|---|---|
| Độ tương phản | `|Δ| trung bình` < `k·σ_nền` (khuyết tật không hiện ra) |
| Diện tích | diện tích đo được / diện tích mask ∉ [0,3; 3,0] |
| Vị trí | trọng tâm nằm ngoài vùng mối hàn do detector Phase 04 trả về |
| Cực tính | dấu Δ trung bình sai so với bảng cực tính Phase 03 |
| Rời rạc | số thành phần liên thông vượt ngưỡng theo lớp (LoRA loạn) |

## Related Code Files

**Tạo**: `pipeline/labeling/delta-image-annotator.py`, `pipeline/labeling/defect-quality-gate.py`, `pipeline/labeling/label-agreement-reporter.py`, `pipeline/config/quality-gate-config.yaml`
**Sửa**: `batch-production-main.py` (gọi annotator + gate trước khi ghi), `post_processing/mask-to-annotation-converter.py` (ưu tiên nhãn đo được nếu có), `qa/qa-pipeline-main.py` (đọc thống kê loại)

## Implementation Steps

1. `delta-image-annotator.py`: `delta = final − background` (có dấu); ước lượng `σ_nền` bằng MAD ngoài vùng mask; ngưỡng `k·σ`; `morphologyEx OPEN` khử đốm; `findContours`; xuất bbox + polygon đã đơn giản hoá.
2. `quality-gate-config.yaml`: ngưỡng cho 5 phép kiểm, riêng cho từng lớp khi cần.
3. `defect-quality-gate.py`: trả `(accepted: bool, reasons: list)`.
4. Nối vào vòng lặp chính **sau** renderer, **trước** khi ghi file. Cảnh (Phase 05) chỉ bị loại phần khuyết tật hỏng; nếu mất hết thì loại cả cảnh.
5. Ghi ảnh loại vào `output/rejected/{reason}/` kèm sidecar JSON (job, lớp, seed, chỉ số đo được).
6. `label-agreement-reporter.py`: tính IoU giữa nhãn đo được và mask đầu vào, thống kê theo lớp.
7. Sửa `mask-to-annotation-converter.py` ưu tiên nhãn đo được, có cờ lùi về mask đầu vào.
8. Bổ sung bảng tỉ lệ loại theo lớp vào QA report.
9. Chạy chéo: cho `auto_labeler/` chạy trên 200 ảnh đã chấp nhận, so IoU với nhãn delta-image.

## Todo List

- [ ] `delta-image-annotator.py`
- [ ] `quality-gate-config.yaml` (ngưỡng 12 lớp)
- [ ] `defect-quality-gate.py` (5 phép kiểm)
- [ ] Nối gate vào vòng lặp chính + `output/rejected/`
- [ ] `label-agreement-reporter.py`
- [ ] `mask-to-annotation-converter.py` dùng nhãn đo được
- [ ] Bảng tỉ lệ loại trong QA report
- [ ] Kiểm chéo với `auto_labeler/` trên 200 ảnh
- [ ] Kiểm mắt 50 ảnh có vẽ nhãn chồng lên

## Success Criteria

- IoU giữa nhãn đo được và khuyết tật khoanh tay ≥ 0,75 trên mẫu 50 ảnh.
- Tỉ lệ loại của cổng chất lượng < 15% tổng thể; lớp nào > 30% thì được nêu tên để xử lý riêng (nhiều khả năng LoRA yếu).
- Không còn ảnh "không có khuyết tật nhìn thấy" lọt vào dataset (kiểm mắt 100 ảnh ngẫu nhiên).
- IoU giữa nhãn delta-image và nhãn `auto_labeler` ≥ 0,6 (kiểm chéo độc lập).

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Ngưỡng delta quá nhạy ⇒ nhãn bám cả nhiễu | Ngưỡng theo `σ_nền` ước lượng bằng MAD, không dùng hằng số tuyệt đối |
| Cổng loại quá tay, mất năng suất | Bắt đầu ngưỡng lỏng, siết dần theo dữ liệu; luôn ghi lý do để phân tích |
| Nhãn đo được nhỏ hơn mask ⇒ bbox chật hơn nhãn RIAWELC | Báo cáo hệ số co và cân nhắc nới bbox theo tỉ lệ cố định |
| Tỉ lệ loại cao ở nhiều lớp ⇒ lộ ra LoRA hiện tại quá yếu | Nếu > 30% ở ≥4 lớp, escalate: nối lại benchmark Phase 10 hoặc retrain LoRA |

## Security Considerations

Không phát sinh. Ảnh bị loại lưu cục bộ, dọn định kỳ.

## Next Steps

→ [Phase 07](./phase-07-throughput-and-tech-debt.md), và cập nhật `docs/` theo quy trình tài liệu.
