# Phase 01 — Đo Lường & A/B Harness

**Ưu tiên**: P0 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 6h · **Phụ thuộc**: —

## Context Links

- [plan.md](./plan.md) · [Hiện trạng pipeline](../../docs/pipeline-generation-current.md)
- Code tham chiếu: `pipeline/benchmark/benchmark-metrics-calculator.py`, `pipeline/qa/ssim-background-checker.py`

## Overview

Không sửa gì trước khi đo được. Phase này dựng một bộ chỉ số khách quan + rig A/B chạy lại được, để mọi thay đổi ở Phase 02–06 đều chứng minh được bằng số trên cùng một tập hạt giống.

## Key Insights

- `benchmark-metrics-calculator.py` đã có FID/SSIM/Sharpness nhưng chỉ dùng trong nhánh benchmark, không tái sử dụng được cho pipeline chính.
- FID một mình không bắt được lỗi "cạnh cứng" và "nhiễu không liên tục" — cần chỉ số cục bộ vùng khuyết tật.
- Cần một chỉ số đo **đóng góp thực của diffusion**: so ảnh ComfyUI trả về với ảnh sau post-process. Nếu chênh lệch ≈ 0 thì SD đang bị vô hiệu hoá (giả thuyết hiện tại).

## Requirements

**Chức năng**
- Sinh bộ A/B cố định: 200 ảnh/lớp × 12 lớp, seed manifest cố định, cùng danh sách background.
- Tính 5 nhóm chỉ số: FID/KID toàn cục, profile gradient biên, tỉ số phương sai nhiễu, cực tính Δ, đóng góp diffusion.
- Xuất `metrics.json` + báo cáo HTML so sánh cạnh nhau nhiều biến thể (variant).

**Phi chức năng**
- Chạy lại cho kết quả giống hệt với cùng seed manifest.
- Toàn bộ chạy < 30 phút cho 2.400 ảnh trên RTX 3090.

## Architecture

```
pipeline/evaluation/
├── seed-manifest-builder.py          # sinh/khoá seed + background cố định
├── realism-metrics-calculator.py     # 5 nhóm chỉ số
├── edge-gradient-profiler.py         # lấy profile vuông góc biên khuyết tật
├── noise-continuity-analyzer.py      # phương sai nhiễu trong/ngoài mask
├── diffusion-contribution-probe.py   # Δ(pre-postprocess, post-postprocess)
└── ab-comparison-report-generator.py # HTML nhiều variant
```

Rig chạy: `run-ab-variant.sh <variant-name> <config>` → `output/ab/<variant>/` → report gộp.

## Related Code Files

**Tạo mới**: 6 file trong `pipeline/evaluation/` (trên), `pipeline/run-ab-variant.sh`
**Đọc tham chiếu**: `pipeline/benchmark/benchmark-metrics-calculator.py`, `pipeline/batch_manager/batch-production-main.py`
**Sửa**: `pipeline/batch_manager/batch-production-main.py` — thêm cờ `--keep-raw-output` để lưu ảnh ComfyUI trước post-process (phục vụ diffusion probe)

## Implementation Steps

1. Chốt tập ảnh thật làm tham chiếu FID (xem câu hỏi mở #1 ở plan.md). Ghi đường dẫn vào `config/evaluation-config.yaml`.
2. Viết `seed-manifest-builder.py`: xuất `output/ab/seeds.json` gồm `{defect_type, seed, background_path}` × 200 × 12.
3. Viết `realism-metrics-calculator.py` gọi 3 module con; dùng `torchmetrics` hoặc `clean-fid` cho FID/KID.
4. `edge-gradient-profiler.py`: lấy 64 đoạn cắt vuông góc biên mask, nội suy, ghi `mean ± std` của độ dốc (đơn vị mức xám/px); làm cùng phép đo trên khuyết tật thật đã khoanh tay.
5. `noise-continuity-analyzer.py`: high-pass residual, tính `var(inside)/var(ring_outside)`.
6. `diffusion-contribution-probe.py`: yêu cầu `--keep-raw-output`; tính `mean|raw - final|` trong vùng annotation mask.
7. Thêm cờ `--keep-raw-output` vào `batch-production-main.py` (lưu vào `output/.../raw/`).
8. `ab-comparison-report-generator.py`: bảng chỉ số + lưới ảnh so sánh variant, HTML tự chứa.
9. Chạy `baseline` variant trên pipeline hiện tại → khoá số làm mốc.

## Todo List

- [ ] Chốt tập ảnh thật tham chiếu, ghi vào `config/evaluation-config.yaml`
- [ ] `seed-manifest-builder.py` + `output/ab/seeds.json`
- [ ] `edge-gradient-profiler.py` + đo trên khuyết tật thật
- [ ] `noise-continuity-analyzer.py`
- [ ] `diffusion-contribution-probe.py`
- [ ] Cờ `--keep-raw-output` trong `batch-production-main.py`
- [ ] `realism-metrics-calculator.py` gộp 5 nhóm chỉ số
- [ ] `ab-comparison-report-generator.py`
- [ ] `run-ab-variant.sh`
- [ ] Chạy variant `baseline`, lưu `output/ab/baseline/metrics.json`

## Success Criteria

- Chạy `bash run-ab-variant.sh baseline config/batch-config.yaml` cho ra `metrics.json` đầy đủ 5 nhóm chỉ số + HTML.
- Chạy hai lần cùng seed manifest ⇒ chỉ số lệch < 1%.
- Trả lời được định lượng: SD hiện đóng góp bao nhiêu % vào ảnh cuối.

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| FID không ổn định với 200 ảnh/lớp | Tính thêm KID (ít lệch ở mẫu nhỏ); báo cáo cả hai |
| Không có khuyết tật thật đã khoanh để đo profile biên | Dùng nhãn RIAWELC theo lớp; nếu thiếu, khoanh tay 20 mẫu/lớp |
| `--keep-raw-output` làm phình đĩa | Chỉ bật ở chế độ A/B, tự xoá sau khi tính chỉ số |

## Security Considerations

Không có dữ liệu nhạy cảm. Đường dẫn dataset đọc từ config, không hard-code. Không đẩy ảnh lên dịch vụ ngoài.

## Next Steps

Số baseline khoá xong → mở [Phase 02](./phase-02-seamless-blend-restore-diffusion.md) và [Phase 04](./phase-04-mask-morphology-and-polarity-fixes.md) song song.
