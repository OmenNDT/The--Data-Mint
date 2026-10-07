# Không ngấu vòng 3: núm co bề rộng dải GỐC tại sinh (lof_band_width_scale) — KHÔNG đưa sản xuất

## Phân tích đặc trưng (round 18, 40 ca so tham chiếu W0003 thật 23 ca, 20 có vùng)

So trung vị 16 đặc trưng (ca có vùng, `result.json` round 18 vs `w0003-defect-features-v2.csv` lớp
`Lack_of_Fusion`):

| Đặc trưng | Thật | Sinh | Tỉ lệ sinh/thật | Nhận định |
|---|---|---|---|---|
| vung_tile (diện tích/khung) | 0,0060 | 0,0157 | 2,6× | sinh quá TO |
| vung_lon (diện tích vùng lớn nhất) | 0,0037 | 0,0095 | 2,6× | sinh quá TO |
| vung_dayhop (extent, tỉ lệ lấp bbox) | 0,686 | 0,681 | ~1,0 | khớp |
| vung_lechtam (độ lệch tâm) | 0,989 | 0,993 | ~1,0 | khớp |
| vung_huong (hướng, độ) | 88,45 | 86,66 | ~1,0 | khớp |
| bien_tuongphan (tương phản biên) | 1,90 | 2,53 | 1,33× | sinh quá TỐI |
| bien_daodong (dao động biên) | 0,493 | 0,414 | 0,84× | sinh quá TRƠN (thật gồ ghề hơn) |
| detection (tách vùng) | 0,870 | 0,625 | — | sinh THẤP hơn thật 24,5 điểm % |

Kết luận: diện tích dải sinh to gấp 2,6 lần thật — khớp đúng hướng báo cáo trước (`lof-crack-shape-
experiment`, `lof-mild-crack-widen-confirm`). Đã xem ảnh `lack_of_fusion_000000.png`,
`_000120.png`, `_000005.png` (round 18): dải sinh là một khối chữ nhật/hình thang liền đặc, mép
tương đối sắc, không có cấu trúc gồ ghề như biên thật bị dao động (bien_daodong thấp).

## Hướng đã chọn: co band_width_range GỐC tại sinh, khác hẳn cơ chế đã thử FAIL

Ba báo cáo trước (vòng D, vòng F) đã thử 7 tổ hợp `lof_width_scale` (hậu kỳ: `_affine` siết mask ĐÃ
sinh quanh tâm khối toàn cục bằng nội suy bậc 1) — mọi tổ hợp đều làm hỏng khả năng phát hiện nặng
hơn mốc. Giả thuyết ban đầu: `_affine` siết quanh TÂM TOÀN CỤC làm méo dải nghiêng (tilt lên tới
±20px), mất kết nối ở hai đầu.

Núm mới `lof_band_width_scale` (mặc định 1,0) kiểm giả thuyết đó bằng cách co TRỰC TIẾP
`band_width_range` của `LackOfFusionMaskGenerator` (mặc định (5, 12) điểm ảnh) TRƯỚC khi vẽ
`fillPoly` và làm mềm mép — không qua affine/nội suy, mép vẫn sắc như bộ sinh gốc.

## Code

- `realism/knobs.py`: thêm `lof_band_width_scale` (nhóm 6, khoảng 0,2–1,0, mặc định/đề xuất 1,0).
  Append, không đụng các mục khác (một nhánh song song đã thêm `lop_length_scale`/`lop_post_depth_*`
  đồng thời — đọc lại tệp trước khi sửa, không xung đột).
- `realism/generator_hooks.py`: thêm `LOF_BASE_BAND_WIDTH_RANGE = (5, 12)` và hàm
  `lof_generation_kwargs()` (trả `{}` ở mặc định, trả `{"band_width_range": (lo', hi')}` khi núm
  khác 1,0; nuốt lỗi như toàn bộ module). Thêm `lof_band_width_scale` vào `TYPE_KNOBS["lack_of_fusion"]`
  (nối dây `loop_partial.affected_types`: núm này chỉ khiến vòng sinh lại riêng lack_of_fusion, không
  phải "núm làm tối" nên KHÔNG thêm vào `DARKEN_TYPE_KNOBS`).
- `batch_manager/mask_prefetch_worker_pool.py`: `_generate_mask_worker` tính `extra_kwargs` (gọi
  `lof_generation_kwargs()` chỉ khi `defect_type == "lack_of_fusion"`), truyền vào constructor của
  generator VÀ vào `regenerate` lambda (mặt nạ trống sinh lại cũng phải dùng đúng band_width_range
  đã co). Loại khác `extra_kwargs = {}`, không đổi gì (`**{}`).
- `tests/test-realism-lof-band-width.py` (10 ca unittest, mới): mặc định trả `{}` + mask y nguyên
  từng điểm ảnh (so sinh có/không kwargs, cùng seed); núm 0,5 co đúng tỉ lệ band_width_range; núm 0,4
  làm diện tích mask nhỏ hơn mặc định (3 seed); env hỏng → `{}` an toàn; núm có trong `TYPE_KNOBS`,
  không có trong `DARKEN_TYPE_KNOBS`; đổi núm chỉ ảnh hưởng `lack_of_fusion` trong `affected_types`.

## Thí nghiệm GPU (3 mức, 40 ca cố định — TÁI DÙNG đúng seed/nền của round 18)

Thuê GPU qua `plant_gpu_lease` (rảnh, không ai tranh). Dùng lại `fixed-jobs.json` của
`output/realism-loop/iter-18` (lọc đúng 40 ca `lack_of_fusion`) làm đề thi, núm nền = núm sản xuất
hiện tại (`knobs.resolve("production")`), chỉ đè `lof_band_width_scale`. Đo bằng
`realism.defect_eval.evaluate_defects` + so cặp bằng `loop_gate_v2._type_entry` (đúng hàm cổng thật
dùng, bootstrap B=400) với mốc = `defect_metrics.types.lack_of_fusion` của round 18.

| Mức | band_width_range hiệu dụng | detection sinh | gap so thật | C2ST | KID | coverage |
|---|---|---|---|---|---|---|
| mốc (1,0) | (5, 12) | 0,625 | 24,5 điểm % | 0,70 (best) | 1,02 | 0,90 |
| 0,8 | (4, 10) | 0,500 | 36,9 điểm % | 0,83 | 0,79 | 0,75 |
| 0,6 | (3, 7) | 0,450 | 41,9 điểm % | 0,79 | 0,79 | 0,90 |
| 0,4 | (2, 5) | 0,425 | 44,6 điểm % | 0,66 | 0,61 | 0,80 |

CẢ BA mức bị `loop_gate_v2` CHẶN tách vùng ngay (detection tụt thêm 12,5 đến 20 điểm % so mốc, vượt
rất xa hạn 10 điểm %, và không cải thiện ≥ 2 điểm % so mốc để được miễn chặn). Đáng chú ý: ở
0,6/0,4 bốn độ đo hình dạng (C2ST, KID, coverage) có xu hướng ĐIỂM SỐ tốt hơn mốc (đúng hướng co
diện tích về gần thật), nhưng verdict ghép cặp đều "same" (CI rộng, n chung 16–19 ca) — và vô
nghĩa vì đã bị chặn ở điều kiện tách vùng.

## Nhận định

Co bề rộng dải TẠI SINH (mép sắc, không affine) vẫn làm hỏng khả năng phát hiện theo đúng QUY LUẬT
như co hậu kỳ (`lof_width_scale`, 7 tổ hợp trước), thậm chí NẶNG HƠN ở cùng mức co tương đối (0,8
ở đây ≈ ngang `lf-m1` 0,9 trước nhưng tụt sâu hơn: −12,5 so −7,5 điểm %). Điều này LOẠI TRỪ giả
thuyết ban đầu (affine siết quanh tâm sai làm méo dải nghiêng là nguyên nhân chính): kể cả co sạch,
không nội suy, bộ dò vùng + pipeline SD vẫn không giữ được dải đủ để kernel (`min_area=25`, ngưỡng
hiệu chỉnh trên W0003) nhận ra khi bề rộng gốc giảm. Nguyên nhân nhiều khả năng ở khâu SD vẽ lại
mask mỏng (ControlNet bám mask nhỏ kém hơn) hoặc ngưỡng kernel nhạy với bề rộng tuyệt đối, không chỉ
diện tích tương đối — ngoài phạm vi một núm hình học.

**Khuyến nghị:** GIỮ `lof_band_width_scale = 1,0` (không đổi sản xuất). Đóng hướng "co bề rộng" cho
LF (cả hai cơ chế, hậu kỳ và tại sinh, đều thất bại trên 10 tổ hợp tổng cộng qua 3 vòng). Hướng khả
thi còn lại cho LF (chưa thử, ngoài phạm vi núm hình học): cải thiện độ bám ControlNet riêng cho dải
mỏng, hoặc tăng diện tích thay vì giảm (bù lại phần detection, đổi lấy area-AUC xấu hơn) — cần người
dùng/điều phối quyết định có đáng đổi hay không trước khi làm tiếp.

## Tệp liên quan

- Code: `pipeline/realism/knobs.py`, `pipeline/realism/generator_hooks.py`,
  `pipeline/batch_manager/mask_prefetch_worker_pool.py`, `pipeline/tests/test-realism-lof-band-width.py`
- Dữ liệu sinh: `output/realism-loop/lf-band-width-variants/{lf-bw-08,lf-bw-06,lf-bw-04}/`
- Mốc dùng lại: `pipeline/realism/state/runs/loop-20261007-112308-479-eval-18/result.json`
  (không sinh lại mốc)
- Script + kết quả thô: scratchpad `lf_band_width_variants.py`, `lf_band_width_result.json`,
  `lf_band_width_compare.py`

## Kiểm thử

`tests/test-realism-*.py` (37 tệp) + `tests/test-plant-hmi-*.py` (12 tệp): tất cả `OK` (bao gồm
10 ca mới `test-realism-lof-band-width.py`). Không ghi `knobs.json`/`candidate-knobs.json`/
`best.json`; không commit; không restart dịch vụ; không thuê GPU đè agent khác (kiểm `gpu-lease`
rảnh trước khi thuê, trả lease ngay khi xong qua `finally`).

**Status:** DONE
**Summary:** Co band_width_range GỐC tại sinh (núm mới `lof_band_width_scale`, mặc định 1,0 =
đúng hành vi cũ, đã kiểm pixel-identical) vẫn bị cổng v2 CHẶN tách vùng ở cả 3 mức (0,8/0,6/0,4),
tụt sâu hơn cả cách hậu kỳ đã thử trước — loại trừ giả thuyết "lỗi affine", xác nhận hướng co bề
rộng (bất kỳ cơ chế nào) không khả thi cho LF trong pipeline hiện tại. Không đưa núm vào sản xuất,
giữ mặc định 1,0. Nối dây đầy đủ TYPE_KNOBS/loop_partial, test pass, toàn bộ 49 tệp test realism +
plant-hmi OK.
**Concerns:** n ghép cặp nhỏ (16–19 ca) nên CI các độ đo hình dạng không khẳng định được dù điểm số
có vẻ tốt hơn ở mức co sâu — nhưng vô nghĩa vì đã bị chặn tách vùng, không cần n lớn hơn để xác nhận
thêm.
**Câu hỏi còn mở:** có nên thử hướng NGƯỢC (mở rộng band_width_range > 1,0 để bù detection, đổi lấy
area-AUC xấu hơn) hay tập trung vào ControlNet strength riêng cho LF? Cần người dùng/điều phối chốt
trước khi giao nhánh tiếp theo.
