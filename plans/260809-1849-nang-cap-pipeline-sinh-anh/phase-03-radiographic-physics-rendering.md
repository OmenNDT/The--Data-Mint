# Phase 03 — Kết Xuất Theo Vật Lý Chụp Ảnh Phóng Xạ

**Ưu tiên**: P0 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 12h · **Phụ thuộc**: Phase 02

## Context Links

- [plan.md](./plan.md) · [Phase 02](./phase-02-seamless-blend-restore-diffusion.md)
- Tham chiếu hình thái: `docs/defect-morphology-undercut.md`

## Overview

Thay phép nhân hệ số tối cố định bằng chuỗi kết xuất mô phỏng đường đi của tia X: suy giảm theo bề dày ở miền log → bán dạ hình học → hàm truyền điều biến của phim/detector → nhiễu lượng tử. Đây là phase quyết định chỉ số FID.

## Key Insights

- Ảnh RT tuân theo Beer–Lambert: `I = I₀·exp(−μ·t)`. Khuyết tật là **thay đổi bề dày vật liệu**, nên phải cộng/trừ ở **miền log**, không nhân ở miền cường độ. Nhân hệ số cố định như hiện tại cho ra vùng phẳng, không có gradient bề dày.
- Khuyết tật thật không có cạnh cứng: bán dạ hình học `Ug = f·t/(d−t)` làm nhoè biên vài pixel, cộng thêm MTF của phim/detector.
- Nhiễu trong ảnh RT là nhiễu lượng tử, **phụ thuộc cường độ** (σ ∝ √I). Vùng khuyết tật tối hơn ⇒ ít photon ⇒ nhiễu tương đối lớn hơn. Hiện tại vùng khuyết tật lại mịn hơn nền — dấu hiệu giả rõ nhất.
- Cực tính phụ thuộc lớp: rỗng/nứt/thiếu ngấu ⇒ **tối**; ngậm kim loại đặc (vonfram) ⇒ **sáng**; ngậm xỉ ⇒ tối vừa. Cần bảng cực tính theo lớp thay vì `if metallic_inclusion: return`.

## Requirements

**Chức năng**
- Bản đồ bề dày (thickness map) liên tục từ mask thay vì mask nhị phân.
- Kết xuất 4 bước: attenuation (log-domain) → penumbra → MTF → quantum noise.
- Bảng tham số theo lớp: hệ số suy giảm tương đối, dấu cực tính, profile bề dày.
- Giữ được nội dung do SD sinh: SD đóng vai trò texture/chi tiết bên trong, mô hình vật lý đóng vai trò mức xám và biên.

**Phi chức năng**
- Toàn bộ vectorised numpy/OpenCV, < 60 ms/ảnh 512².
- Tham số nằm trong YAML, không hard-code.

## Architecture

```
pipeline/rendering/
├── thickness-map-builder.py        # mask nhị phân → bản đồ bề dày liên tục
├── beer-lambert-attenuator.py      # suy giảm miền log theo lớp
├── geometric-penumbra-filter.py    # nhoè bán dạ (Ug)
├── detector-mtf-filter.py          # MTF phim/detector
├── quantum-noise-injector.py       # nhiễu phụ thuộc cường độ
└── radiographic-renderer.py        # điều phối 4 bước

config/radiographic-physics-config.yaml
```

Luồng mới trong vòng lặp chính:
```
raw_sd_output ─┐
background ────┼─► gradient blend (P02) ─► radiographic_renderer(thickness_map) ─► final
thickness_map ─┘
```

## Related Code Files

**Tạo**: 6 file trong `pipeline/rendering/`, `pipeline/config/radiographic-physics-config.yaml`
**Sửa**: `pipeline/batch_manager/batch-production-main.py` (bỏ hẳn `apply_rt_polarity()`, gọi renderer), `pipeline/batch_manager/mask_prefetch_worker_pool.py` (trả thêm `thickness_path` cạnh `annotation_path`/`inpaint_path`)
**Xoá**: `DARKEN_BY_TYPE` và toàn bộ logic nhân hệ số trong `batch-production-main.py`

## Implementation Steps

1. `thickness-map-builder.py`: distance transform bên trong mask → chuẩn hoá → áp profile theo lớp (`parabolic` cho rỗng khí, `flat_top` cho thiếu ngấu, `tapered` cho nứt). Xuất float32 0–1.
2. `config/radiographic-physics-config.yaml`: cho 12 lớp, mỗi lớp gồm `polarity` (+1/−1), `mu_relative`, `max_thickness_fraction`, `profile`.
3. `beer-lambert-attenuator.py`: `log_I = log(I+ε)`, `log_I += polarity·mu_relative·thickness`, quay lại miền cường độ. Đây là chỗ thay hoàn toàn phép nhân 0.92.
4. `geometric-penumbra-filter.py`: nhoè Gaussian bán kính suy từ `Ug = f·t/(d−t)`; nếu chưa có thông số chụp thật (câu hỏi mở #2), hiệu chỉnh ngược từ profile biên khuyết tật thật đo ở Phase 01.
5. `detector-mtf-filter.py`: nhân phổ với MTF dạng `1/(1+(f/f₀)²)`, `f₀` hiệu chỉnh sao cho sharpness ảnh sinh khớp ảnh thật.
6. `quantum-noise-injector.py`: `σ(x,y) = k·√I(x,y)`; `k` hiệu chỉnh để tỉ số phương sai nhiễu trong/ngoài mask về 1,0.
7. `radiographic-renderer.py`: nối 4 bước, nhận `raw_sd_output` làm nguồn texture bên trong khuyết tật (trộn trọng số với thickness map).
8. Sửa mask worker trả thêm thickness map; sửa vòng lặp chính gọi renderer.
9. Hiệu chỉnh tham số theo lớp bằng A/B (Phase 01), quét `mu_relative` và `k`.
10. Kiểm cực tính toàn bộ 12 lớp — đặc biệt `lack_of_penetration` (đang sai, hiện ra sáng) và `metallic_inclusion`.

## Todo List

- [ ] `thickness-map-builder.py` + 3 profile bề dày
- [ ] `radiographic-physics-config.yaml` cho 12 lớp
- [ ] `beer-lambert-attenuator.py`
- [ ] `geometric-penumbra-filter.py`
- [ ] `detector-mtf-filter.py`
- [ ] `quantum-noise-injector.py`
- [ ] `radiographic-renderer.py` điều phối
- [ ] Mask worker trả `thickness_path`
- [ ] Gỡ `DARKEN_BY_TYPE` khỏi `batch-production-main.py`
- [ ] Quét tham số `mu_relative`, `k`, `f₀` bằng A/B
- [ ] Kiểm cực tính 12/12 lớp

## Success Criteria

- **FID giảm ≥30%** so với baseline Phase 01.
- Độ dốc biên khuyết tật sinh nằm trong ±1σ của khuyết tật thật.
- Tỉ số phương sai nhiễu trong/ngoài mask ∈ [0,8; 1,25] cho cả 12 lớp.
- Dấu Δ trung bình đúng cực tính RT ở 12/12 lớp.
- Không còn vùng phẳng: độ lệch chuẩn mức xám trong lòng khuyết tật > 0.

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Thiếu thông số chụp thật ⇒ penumbra/MTF đoán mò | Hiệu chỉnh ngược từ profile biên khuyết tật thật (Phase 01) thay vì suy từ hình học |
| 12 lớp × 4 tham số = không gian quét lớn | Quét theo nhóm hình thái (rỗng khí / dạng đường / ngậm tạp) rồi tinh chỉnh riêng lẻ |
| Renderer đè lên texture SD, quay lại tình trạng cũ | Thêm trọng số trộn `sd_texture_weight`, đo lại bằng diffusion-contribution probe mỗi lần đổi |
| Chi phí CPU vượt ngân sách | Tiền tính MTF kernel, dùng `cv2.filter2D` separable |

## Security Considerations

Không phát sinh.

## Next Steps

→ [Phase 06](./phase-06-label-fidelity-and-quality-gate.md) sau khi mức xám đã đúng, để đo nhãn từ ảnh thực sinh.
