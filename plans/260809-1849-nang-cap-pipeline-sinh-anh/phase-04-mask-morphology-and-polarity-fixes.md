# Phase 04 — Sửa Hình Thái & Cực Tính Mask

**Ưu tiên**: P1 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 10h · **Phụ thuộc**: Phase 01 (chạy song song Phase 02/03)

## Context Links

- [plan.md](./plan.md) · `pipeline/mask_generator/README.md` · `docs/defect-morphology-undercut.md`
- Bằng chứng trực quan: `output/10class.png`

## Overview

12 mask generator hiện sinh hình học quá đều: đĩa tròn hoàn hảo cho rỗng khí, hình chữ nhật cho thiếu ngấu, đa giác đặc cho ngậm kim loại. Phase này đưa hình thái về sát tiêu chuẩn NDT và bổ sung bản đồ bề dày mà Phase 03 cần.

## Key Insights

- Từ `output/10class.png`: porosity là các đĩa đen bán kính đều, không có phân bố kích thước; linear_porosity là chuỗi hạt thẳng tắp; metallic_inclusion là đa giác trắng đặc; lack_of_penetration là dải chữ nhật.
- `base-defect-mask-generator.py` chỉ yêu cầu trả `(binary_mask, feathered_mask)` — không có chỗ cho bề dày. Cần mở rộng hợp đồng thành 3 output.
- `_detect_weld_center_y()` lấy hàng sáng nhất làm tâm mối hàn — với ảnh nền có gradient mạnh (thấy rõ ở mẫu porosity) sẽ lệch. Cần dò biên mối hàn (hai vai) thay vì đỉnh sáng.
- Một số lớp phải bám vào biên vùng nóng chảy chứ không phải tâm: undercut ở chân mối, LOSWF ở vách, LOP ở chân đường hàn.

## Requirements

**Chức năng**
- Mở rộng hợp đồng base class: `generate() -> (binary_mask, feathered_mask, thickness_map)`.
- Dò hình học mối hàn: tâm + hai biên + bề rộng, thay cho một giá trị `weld_center_y`.
- Sửa hình thái 12 lớp theo mô tả NDT (bảng ở Implementation Steps).
- Phân bố kích thước ngẫu nhiên có căn cứ (log-normal cho đường kính lỗ khí, power-law cho chiều dài nứt).

**Phi chức năng**
- Giữ khả năng tái lập theo seed.
- Không phá tương thích ngược: `generate_legacy()` trả 2 giá trị cho mã cũ trong thời gian chuyển tiếp.

## Architecture

```
pipeline/mask_generator/
├── base-defect-mask-generator.py      # SỬA: hợp đồng 3 output
├── weld-geometry-detector.py          # MỚI: tâm + biên + bề rộng mối hàn
├── thickness-profile-library.py       # MỚI: parabolic / flat_top / tapered / irregular
├── <12 generator hiện có>             # SỬA hình thái + trả thickness
└── weld-roi-constraint.py             # SỬA: ràng buộc theo biên thay vì dải cố định
```

## Related Code Files

**Tạo**: `weld-geometry-detector.py`, `thickness-profile-library.py`
**Sửa**: `base-defect-mask-generator.py`, `weld-roi-constraint.py`, cả 12 generator, `mask_prefetch_worker_pool.py` (`_detect_weld_center_y` → gọi detector mới), `config/mask-config.yaml` (tham số hình thái mới cho 12 lớp)

## Implementation Steps

1. `weld-geometry-detector.py`: từ ảnh nền, lấy profile độ sáng theo hàng, làm trơn, dò hai điểm gấp khúc (biên mối hàn) bằng đạo hàm bậc hai → trả `{center_y, top_y, bottom_y, width}`. Có đường lùi về `height//2` khi dò thất bại.
2. `thickness-profile-library.py`: 4 hàm profile nhận distance-transform chuẩn hoá → trả bề dày 0–1.
3. Sửa `base-defect-mask-generator.py`: hợp đồng 3 output, nhận `weld_geometry` thay vì `weld_center_y`, giữ `generate_legacy()`.
4. Sửa hình thái theo lớp:

| Lớp | Vấn đề hiện tại | Hướng sửa |
|---|---|---|
| porosity | đĩa tròn đều | đường kính log-normal, độ tròn 0,7–1,0, profile parabolic |
| clustered_porosity | cụm rời rạc | cụm theo tiến trình điểm Neyman–Scott, mật độ giảm dần từ tâm cụm |
| linear_porosity | chuỗi thẳng tắp | bám đường chân mối hàn, khoảng cách jitter, kích thước biến thiên |
| crack | đường zigzag đơn | phân nhánh có thứ bậc, thuôn dần về hai đầu, bề rộng giảm theo chiều dài |
| lack_of_fusion | sóng sin | bám biên vùng nóng chảy do detector trả về, biên độ bất quy tắc |
| lack_of_penetration | chữ nhật | dải hẹp ở **chân** đường hàn, bề rộng biến thiên, hai đầu thuôn, **cực tính tối** |
| lack_of_side_wall_fusion | — | bám vách vát, nghiêng theo góc vát |
| undercut | đường thẳng | rãnh ở chân mối, mặt cắt bán nguyệt, chiều sâu biến thiên |
| slag_inclusion | blob nhiễu ngưỡng | đa giác bất quy tắc + nhiễu Perlin ở biên |
| linear_slag_inclusion | chuỗi blob | dải đứt đoạn dọc biên hạt hàn |
| metallic_inclusion | đa giác trắng đặc | mảnh nhỏ góc cạnh, **cực tính sáng**, kích thước 1–4 mm quy đổi |
| elongated_cavity | ellipse | dạng lỗ sâu (wormhole) nghiêng, thuôn một đầu |

5. Sửa `weld-roi-constraint.py` để ràng buộc theo biên thật thay vì `zone_height_pct` cố định.
6. Cập nhật `mask-config.yaml` với tham số mới, giữ khoá cũ để không vỡ config hiện hành.
7. Cập nhật `mask_prefetch_worker_pool.py` gọi detector mới, trả thêm `thickness_path`.
8. Chạy `test-mask-generators-visual.py` xuất lưới 12 lớp × 10 mẫu, đối chiếu với ảnh RT thật.
9. Chạy A/B `p04-morphology`.

## Todo List

- [ ] `weld-geometry-detector.py` + kiểm trên 50 ảnh nền
- [ ] `thickness-profile-library.py`
- [ ] Hợp đồng 3 output ở base class + `generate_legacy()`
- [ ] Sửa 12 generator (theo bảng)
- [ ] `weld-roi-constraint.py` theo biên thật
- [ ] `mask-config.yaml` tham số mới
- [ ] Mask worker trả `thickness_path`
- [ ] Lưới trực quan 12×10, đối chiếu ảnh thật
- [ ] A/B `p04-morphology`
- [ ] Cập nhật `mask_generator/README.md`

## Success Criteria

- 12/12 generator trả về thickness map hợp lệ (float32, 0–1, liên tục).
- Dò hình học mối hàn đúng trên ≥90% trong 50 ảnh nền kiểm tay.
- Lưới trực quan: chuyên gia NDT nhận diện đúng lớp ≥10/12 khi xem mù.
- Phân bố kích thước khuyết tật sinh khớp phân bố của RIAWELC (kiểm định KS, p > 0,05) ở ≥8/12 lớp.
- `lack_of_penetration` và `metallic_inclusion` ra đúng cực tính.

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Sửa 12 generator cùng lúc dễ hồi quy | Mỗi lớp một commit, lưới trực quan chạy sau mỗi lớp |
| Dò biên mối hàn thất bại trên nền gradient mạnh | Đường lùi + lọc bỏ ảnh nền không dò được ra khỏi pool |
| Kiểm định KS không đạt vì nhãn RIAWELC là nhãn phân loại, không có kích thước | Nếu thiếu, đo tay 30 mẫu/lớp làm tham chiếu; hạ tiêu chí xuống so sánh định tính |
| Mất tương thích với checkpoint đang chạy dở | `generate_legacy()` + giữ khoá config cũ |

## Security Considerations

Không phát sinh.

## Next Steps

→ [Phase 05](./phase-05-multi-defect-scene-composition.md) khi hình thái từng lớp đã ổn.
