# Tạo hình mask xỉ (slag_inclusion) theo thước mới W0003

Nhánh B pha 2. Phạm vi: `realism/mask_shaping_slag.py` (triển khai), `tests/test-realism-shaping-slag.py` (mới).
Không đụng `generator_hooks.py`, `knobs.py`, `mask_shaping.py` (chỉ đọc, dùng lại `_affine`, `_stretch`, `_warp`).

## 1. Hiện trạng bộ sinh và FEATHER_RADIUS

`mask_prefetch_worker_pool.py` ánh xạ `defect_type="slag_inclusion"` → `SlagInclusionMaskGenerator` (1 khối,
`blur_radius=5`), KHÔNG phải `LinearSlagInclusionMaskGenerator` (3-6 khối, `blur_radius=4`, dùng cho
`linear_slag_inclusion`, loại khác). `generator_hooks.FEATHER_RADIUS["slag_inclusion"]=5` **đúng**, khớp bộ
sinh thật đang chạy. Không cần sửa.

## 2. Thực hiện: `realism/mask_shaping_slag.py`

Ba núm độc lập (mặc định 1/1/0 giữ nguyên mask, test `test_default_knobs_return_mask_unchanged` xác nhận):

- `slag_scale`: giãn đẳng hướng quanh tâm từng vùng liên thông, hệ số dài `s = sqrt(slag_scale)` (diện tích
  nhân đúng `slag_scale` lần, test đo được tỉ lệ 8,01 khi núm = 8).
- `slag_elongation`: kéo theo trục gần ngang (trục hàn) bằng `_stretch` có sẵn, lệch góc ngẫu nhiên nhỏ
  `N(0, 8°)` quanh 0° (không phải núm riêng, hằng số cố định) vì đo W0003 thật `vung_huong` phân bố 86-90°
  chứ không đúng 90° tuyệt đối mọi mẫu. Phép giãn bảo toàn diện tích (test tỉ lệ diện tích ~1,0 khi chỉ bật
  núm này).
- `slag_irregularity_px`: dời điểm mượt (trường Gauss lọc σ=2,5, chuẩn hoá biên độ theo px), làm giảm độ đặc
  (solidity) đơn điệu theo núm (test `assertLess` xác nhận).

Xử lý riêng từng vùng liên thông (`ndi.label` + `ndi.find_objects`) với lề (pad) tính theo trị kỳ dị lớn nhất
của ma trận biến đổi, để nhiều hạt xỉ trong một mask không trộn lẫn và không bị cắt mất khi giãn to. Vùng sát
biên ảnh: `_affine`/`_warp` dùng `mode="constant"`, phần giãn ra ngoài khung tự cắt, không văng lỗi (test
`test_blob_near_image_edge_does_not_crash`).

Test đơn vị: 9/9 qua (`.venv/bin/python3 tests/test-realism-shaping-slag.py`), gồm mặc định bất biến, mask
rỗng, tỉ lệ diện tích theo `slag_scale`, bbox dẹt + bảo toàn diện tích theo `slag_elongation`, độ đặc giảm
đơn điệu theo `slag_irregularity_px`, hai vùng tách biệt giữ đúng tâm, vùng sát biên không lỗi, hợp đồng
shape/dtype đầu ra.

## 3. Thí nghiệm 40 ca cố định, 3 bộ núm, GPU thuê có chờ

Núm sản xuất hiện hành (mọi núm khác giữ nguyên) + 3 biến thể slag:

| | slag_scale | slag_elongation | slag_irregularity_px |
|---|---|---|---|
| v1 | 4 | 2 | 2 |
| v2 | 8 | 3 | 3 |
| v3 | 10 | 4 | 5 |

Baseline dùng lại `output/realism-loop/remaining-types-prod/slag_inclusion` (40 ca núm sản xuất, đã có sẵn,
không sinh lại). Seed/nền của 40 ca thí nghiệm lấy đúng từ `fixed-jobs.json` của baseline (ghép cặp được).
GPU bận lúc bắt đầu (lease `pore-type-depth-base` rồi `ecav-tilt-variants`), script tự chờ 30 s/lần, tổng
chờ khoảng 20 phút rồi mới chiếm được, sinh 3×40=120 ảnh, không vượt mức khuyến nghị ~80 ảnh/lần gọi batch.

### Kết quả (thước mới, n_real=14, cờ `small_reference`: CI rộng, chỉ báo không dùng làm cổng chặn)

| | baseline (SX) | v1 | v2 | v3 |
|---|---|---|---|---|
| tỉ lệ tách vùng (sinh) | 0,30 | 0,475 | 0,60 | 0,675 |
| C2ST | 0,839 | 0,786 | 0,851 | 0,807 |
| KID | 4,05 [2,64; 5,69] | 3,70 | 3,39 | 3,17 |
| KID ghép cặp so baseline | — | −1,30 (tốt hơn, CI không chứa 0) | −2,42 (tốt hơn) | −2,79 (tốt hơn, mạnh nhất) |
| density / coverage | 0,55 / 0,429 | 0,568 / 0,429 | 0,575 / 0,429 | 0,570 / 0,50 |
| vung_tile (diện tích, trung vị) | 0,0073 (thật 0,0627) | 0,0095 | 0,0089 | 0,0083 |
| xuong_dai (xương, trung vị) | 0,117 (thật 1,088) | 0,176 | 0,251 | 0,203 |
| vung_dac (độ đặc) AUC phân biệt | 0,917 (còn trong top 6 lệch) | ra khỏi top 6 | ra khỏi top 6 | ra khỏi top 6 |

**Diễn giải theo thứ tự ưu tiên người dùng chốt (hình dạng trước, hiển thị sau):**

- Hình dạng: cả 3 biến thể đều cải thiện so baseline trên hầu hết độ đo; KID ghép cặp cải thiện có ý nghĩa
  (CI không chứa 0) ở cả 3 mức, mạnh dần theo núm, tốt nhất ở v3. `vung_dac` (độ đặc, lệch AUC 0,92 ở
  baseline, tức sinh quá tròn/trơn so thật) không còn lọt top 6 đặc trưng lệch nhiều nhất ở cả 3 biến thể,
  tức đã hoà vào phân bố thật, đúng mục tiêu knob `slag_irregularity_px`. `xuong_dai` (xương dài) cải thiện
  tỉ lệ thật/sinh từ 9,3 lần (baseline) xuống còn 4,3-6,2 lần, chưa về bằng thật nhưng rút ngắn rõ. C2ST và
  coverage dao động trong CI, không đổi có ý nghĩa ("same" ở cả 4 độ đo ghép cặp trừ KID).
- Hiển thị (tỉ lệ tách vùng): tăng đều 0,30 → 0,475 → 0,60 → 0,675 theo núm mạnh dần, nhưng **chưa đạt mức
  thật 1,00 trong khoảng cách ≤ 10 điểm % người dùng chốt** (khoảng cách còn 32,5 điểm % ở v3, biến thể mạnh
  nhất đã thử). Tăng núm từ v2 lên v3 (gần gấp đôi slag_scale, elongation, irregularity) chỉ thêm 7,5 điểm %
  tỉ lệ tách vùng, cho thấy lợi suất giảm dần, không chắc đạt ≤10 điểm % dù đẩy núm lên trần đăng ký
  (slag_scale 12, elongation 6, irregularity_px 8).
- `vung_tile`/`vung_lon` (diện tích vùng) gần như không đổi dù `slag_scale` tăng từ 4 lên 10 (0,95 → 0,89 →
  0,83 ×10⁻² trung vị, thật 6,27×10⁻²): mask hình học đã giãn đúng tỉ lệ đo được trong test đơn vị (tỉ lệ
  diện tích mask 8,0 lần khi `slag_scale=8`, xem mục 2), nhưng **đặc trưng `vung_tile` đo trên ẢNH SINH sau
  ControlNet/SD vẽ, không đo trực tiếp mask nhị phân**: vùng tương phản đủ ngưỡng để tính là "vùng" trong ảnh
  cuối không lớn theo cùng tỉ lệ mask đầu vào. Khả năng ControlNet strength (0,7 hiện hành) hoặc độ sâu làm
  tối chung (không có núm riêng cho xỉ như đã có cho rỗ khí `pore_post_depth_*`) giới hạn độ tương phản vùng
  lớn, khiến bộ dò ngưỡng của thước đo chỉ bắt được phần lõi, không phải toàn bộ mask đã giãn.

### Kiểm bằng mắt

Xem vài ảnh sinh v3 (`output/realism-loop/slag-shaping-experiment/v3_scale10_elong4_irr5/slag_inclusion/`):
ca có vùng rõ (vd `_000003.png`) cho đám tối kéo dài theo phương ngang, biên lởm chởm nhiều thuỳ nhỏ,
hình dạng gần giống xỉ thật (so ảnh thật `W0003_0010_tile_73.png`, `W0003_0049_tile_67.png`: vài đốm/khối
tối nằm rải dọc một dải ngang). Một số ca không có vùng nào đủ tương phản ở cả núm sản xuất lẫn 3 biến thể
(nền + vị trí mối hàn không thuận lợi cho khối xỉ, không phải lỗi núm). Không nhầm sang rỗ khí (tròn đều)
hay không ngấu (dải dài mảnh liên tục).

## 4. Khuyến nghị

Đề xuất đưa **v3 (`slag_scale=10, slag_elongation=4, slag_irregularity_px=5`)** vào núm thử ứng viên: tốt
nhất hoặc đồng hạng tốt nhất trên cả 4 độ đo thước mới so baseline (KID −2,79 CI không chứa 0, mạnh nhất;
coverage 0,50 cao nhất; density/C2ST trong khoảng dao động CI như hai biến thể kia), tỉ lệ tách vùng cao
nhất (0,675). Có thể thử đẩy tới trần đăng ký (`slag_scale=12, slag_elongation=6, slag_irregularity_px=8`)
nếu muốn vắt thêm, nhưng xu hướng lợi suất giảm dần giữa v2→v3 cho thấy mức tăng thêm sẽ nhỏ.

**Việc mask shaping một mình không đủ đóng khoảng cách tỉ lệ tách vùng ≤10 điểm %** (nguyên tắc cổng v2 người
dùng chốt 6/10). Cần nhánh khác (ngoài phạm vi file tôi được giao, `knobs.py`/`generator_hooks.py` người dùng
duyệt file khác) thêm núm độ sâu làm tối riêng cho xỉ (kiểu `slag_post_depth_min/max`, giống đã làm cho rỗ
khí) hoặc tăng `controlnet_strength` riêng loại xỉ, để vùng tối trong ảnh sinh bắt kịp diện tích mask đã
giãn. Đề nghị lead cân nhắc giao việc này cho nhánh phụ trách `post_darkening.py`/`knobs.py`.

## Tệp

- Sửa: `realism/mask_shaping_slag.py` (66 dòng)
- Mới: `tests/test-realism-shaping-slag.py` (9 test, qua hết)
- Kết quả thí nghiệm thô: `/tmp/claude-1000/.../scratchpad/slag-shaping-result.json` (tạm, không trong repo)
- Ảnh sinh 3 biến thể: `output/realism-loop/slag-shaping-experiment/{v1,v2,v3}_*/slag_inclusion/`

**Status:** DONE_WITH_CONCERNS
**Summary:** Viết xong `shape()` cho slag (giãn đẳng hướng + kéo dài trục hàn + méo biên), 9 test đơn vị qua,
đo thước mới qua 3 biến thể núm trên 40 ca cố định ghép cặp baseline sản xuất. Hình dạng cải thiện rõ (KID,
độ đặc, xương dài); tỉ lệ tách vùng tăng đều nhưng không đạt mục tiêu ≤10 điểm % dù đã thử núm gần trần.
Khuyến nghị v3 (10/4/5) làm núm thử ứng viên; cờ FEATHER_RADIUS["slag_inclusion"]=5 đã đúng, không cần sửa.
**Concerns/Blockers:** Khoảng cách tỉ lệ tách vùng (hiển thị) có thể cần núm độ sâu làm tối riêng cho xỉ nằm
ngoài phạm vi file được giao (`knobs.py`, `generator_hooks.py`) để đóng hẳn; n_real=14 nên mọi so sánh này
chỉ báo (cờ `small_reference`), không dùng làm cổng chặn một mình.
