# Phase 02 — Blend Liền Mạch, Khôi Phục Output Diffusion

**Ưu tiên**: P0 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 10h · **Phụ thuộc**: Phase 01

## Context Links

- [plan.md](./plan.md) · [Phase 01](./phase-01-metrics-baseline-and-ab-harness.md) · [Hiện trạng](../../docs/pipeline-generation-current.md) mục 6
- Code gốc vấn đề: `pipeline/batch_manager/batch-production-main.py:56-118`

## Overview

Gỡ bước thay-cứng-background và nhân-hệ-số-tối, thay bằng hoà trộn ở miền gradient để nội dung do SD1.5 + LoRA sinh ra được giữ lại mà vẫn không lộ đường viền hay quầng sáng.

## Key Insights

- Halo sinh ra ở vành đai giữa `annotation mask` (mảnh) và `inpaint mask` (dilate k=21). Cắt cứng chỉ **giấu** halo, đồng thời xoá luôn phần khuyết tật mà SD vẽ lan ra ngoài mask mảnh — trong khi khuyết tật thật vốn có vùng chuyển tiếp.
- Hoà trộn ở miền gradient (Poisson / Laplacian pyramid) khớp mức nền ở biên nên triệt được đường nối mà không phải cắt nội dung.
- Bậc thang độ sáng nền cũng góp phần: `denoise 0.85–0.90` khiến SD vẽ lại gần như toàn bộ vùng inpaint. Hạ denoise + đưa ControlNet inpaint gánh việc giữ nền sẽ giảm biên độ halo ngay từ nguồn.

## Requirements

**Chức năng**
- Module blend mới, thay thế bước 1 của `apply_dark_defect_convention()`.
- Ba chiến lược cắm được, chọn qua config: `poisson` (seamlessClone), `laplacian_pyramid`, `legacy_hard_cut` (giữ để so sánh).
- Hỗ trợ mask hoà trộn có dải chuyển tiếp rộng có kiểm soát (không còn sigma=1.5 cố định).

**Phi chức năng**
- Chi phí CPU < 40 ms/ảnh 512² để không thành nút cổ chai.
- Bật/tắt được qua config, không cần sửa mã.

## Architecture

```
pipeline/compositing/
├── gradient-domain-blender.py     # Poisson + Laplacian pyramid
├── blend-mask-builder.py          # dựng dải chuyển tiếp từ annotation + inpaint mask
└── __init__.py

batch-production-main.py
  └─ thay apply_dark_defect_convention() bước 1
     bằng gradient-domain-blender.blend(raw_sd_output, background, blend_mask)
```

`config/compositing-config.yaml` mới:
```yaml
blend:
  strategy: laplacian_pyramid   # poisson | laplacian_pyramid | legacy_hard_cut
  pyramid_levels: 5
  transition_width_px: 9        # dải chuyển tiếp quanh annotation mask
sampler_override:
  denoise_by_defect: {...}      # hạ denoise theo lớp
```

## Related Code Files

**Tạo**: `pipeline/compositing/gradient-domain-blender.py`, `pipeline/compositing/blend-mask-builder.py`, `pipeline/compositing/__init__.py`, `pipeline/config/compositing-config.yaml`
**Sửa**: `pipeline/batch_manager/batch-production-main.py` (bỏ bước 1 hard-cut, gọi blender), `pipeline/batch_manager/batch-job-scheduler.py` (đọc denoise override), `pipeline/config/mask-config.yaml` (thu `inpaint_dilation.kernel_size` xuống mức phù hợp từng lớp)
**Không đụng**: các mask generator (thuộc Phase 04)

## Implementation Steps

1. Viết `blend-mask-builder.py`: từ annotation mask, dựng mask hoà trộn có dải chuyển tiếp `transition_width_px` bằng distance transform (không dùng Gaussian đơn thuần — cho biên đều hơn).
2. Viết `gradient-domain-blender.py`:
   - `blend_laplacian(src, dst, mask, levels)` — dựng tháp Laplacian cho cả hai ảnh, trộn theo tháp Gaussian của mask.
   - `blend_poisson(src, dst, mask)` — bọc `cv2.seamlessClone(MIXED_CLONE)`, xử lý ảnh xám bằng cách nhân 3 kênh rồi lấy 1.
3. Bỏ bước 1 trong `apply_dark_defect_convention()`; đổi tên hàm còn lại thành `apply_rt_polarity()` (chỉ còn phần cực tính, sẽ thay tiếp ở Phase 03).
4. Nối blender vào vòng lặp chính, đọc `compositing-config.yaml`.
5. Thêm `denoise_by_defect` override, hạ denoise xuống dải 0.55–0.75 tuỳ lớp; giữ crack cao hơn (cần tự do latent).
6. Giảm `inpaint_dilation.kernel_size` theo lớp thay vì 21 cố định (crack ~9, porosity ~13, LOF ~15).
7. Chạy A/B: `baseline` vs `p02-laplacian` vs `p02-poisson` × 3 mức denoise.
8. Chốt cấu hình thắng, ghi vào `compositing-config.yaml`.

## Todo List

- [ ] `blend-mask-builder.py` (distance transform)
- [ ] `gradient-domain-blender.py` — Laplacian pyramid
- [ ] `gradient-domain-blender.py` — Poisson
- [ ] Gỡ hard-cut khỏi `apply_dark_defect_convention()`
- [ ] `compositing-config.yaml` + nối vào vòng lặp
- [ ] `denoise_by_defect` override trong scheduler
- [ ] Dilation kernel theo lớp trong `mask-config.yaml`
- [ ] Chạy A/B 3 chiến lược × 3 denoise, chọn cấu hình
- [ ] Ghi kết quả vào `plans/reports/`

## Success Criteria

- Chỉ số **đóng góp diffusion** (Phase 01) tăng từ ~0 lên ≥ 25% biên độ tín hiệu trong vùng khuyết tật.
- Không còn đường nối nhìn thấy: gradient lớn nhất trên vành đai biên ≤ 1,5× gradient nền cùng ảnh.
- FID không xấu đi so với baseline (mục tiêu giảm thực sự thuộc Phase 03).
- Thời gian post-process/ảnh < 40 ms.

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Poisson kéo lệch mức xám toàn vùng (mất độ tối khuyết tật) | Ưu tiên Laplacian pyramid; Poisson chỉ dùng MIXED_CLONE và có chốt so sánh A/B |
| Bỏ hard-cut ⇒ halo LoRA lộ ra | Hạ denoise + thu dilation kernel để giảm halo ở nguồn; giữ `legacy_hard_cut` làm đường lùi |
| Hạ denoise làm khuyết tật mờ đi | Bù bằng LoRA strength và Phase 03 (kết xuất vật lý) chứ không quay lại nhân hệ số |

## Security Considerations

Không phát sinh. Toàn bộ xử lý cục bộ, không thêm phụ thuộc mạng.

## Next Steps

→ [Phase 03](./phase-03-radiographic-physics-rendering.md) thay nốt bước nhân-hệ-số-tối bằng mô hình suy giảm tia X.
