# Nhánh F vòng 2: không ngấu mức nhẹ + xác nhận crack_widen_px=2 (n=120)

## Việc đã làm
- Không sửa code (không tìm thấy lỗi trong `realism/mask_shaping_lof.py`, 12/12 test
  `tests/test-realism-shaping-lof.py` qua trước khi thí nghiệm). Chỉ chạy tham số qua
  `REALISM_KNOBS`, không ghi `knobs.json`/`candidate-knobs.json`.
- Xác nhận mốc LF: `realism-knobs-used.json` ở `output/realism-loop/depth-base/prod` có
  `lof_length_scale=1, lof_width_scale=1, lof_gap_max=0` tức mặc định, khớp sản xuất hiện
  tại (`realism/state/knobs.json`). Dùng thẳng mốc này, không sinh lại.
- 4 biến thể LF nhẹ hơn (40 ca `exam_set.subset(["lack_of_fusion"], 40)`), 1 job/biến thể.
- 120 ca crack cố định (seed `20261007`, nền lấy từ `exam_set`) × 2 mức `crack_widen_px`
  (0 và 2), mỗi mức chia 2 job (80+40) theo giới hạn ≤80 ảnh/lần thuê GPU.
- GPU bận bởi nhánh khác (`branch-e-slag-ecav-base`) lúc bắt đầu, script tự chờ/thử lại
  30 giây (code mới thêm `acquire_retry`, chờ thật ~7 phút rồi được cấp).

## Không ngấu (lack_of_fusion), mức nhẹ hơn round 1

Thật: detection 0,870 · n=40/biến thể. Mốc SX (1/1/0): detection 0,625.

| Biến thể | length/width/gap | detection sinh | C2ST | KID | density | coverage |
|---|---|---|---|---|---|---|
| mốc SX | 1 / 1 / 0 | 0,625 | 0,786 | 1,029 | 0,416 | 0,850 |
| lf-m1 | 0,9 / 0,9 / 1 | 0,550 | 0,850 | 1,593 | 0,455 | 0,750 |
| lf-m2 | 0,85 / 0,85 / 2 | 0,425 | 0,856 | 1,338 | 0,306 | 0,750 |
| lf-m3 | 1,0 / 0,85 / 1 | 0,475 | 0,879 | 1,052 | 0,337 | 0,800 |
| lf-m4 | 0,9 / 1,0 / 2 | 0,600 | 0,921 | 1,889 | 0,492 | 0,800 |

Ghép cặp (bootstrap B=400, ca chung 16 đến 22, `loop_gate_v2_metrics.paired_metrics`) so
từng biến thể với mốc SX:

| Biến thể | n chung | C2ST verdict | KID verdict | density verdict | coverage verdict |
|---|---|---|---|---|---|
| lf-m1 | 20 | same (tệ hơn điểm) | same (tệ hơn điểm) | same (nhỉnh hơn điểm) | same (tệ hơn điểm) |
| lf-m2 | 16 | same (gần như bằng) | same (nhỉnh hơn điểm) | same (tệ hơn điểm) | same (tệ hơn điểm) |
| lf-m3 | 18 | same (gần như bằng) | same (gần như bằng) | same (tệ hơn điểm) | same (tệ hơn điểm) |
| lf-m4 | 22 | same (tệ hơn điểm) | **worse** (CI [+0,09, +0,78], không phủ 0) | same (nhỉnh hơn điểm) | same (tệ hơn điểm) |

**Nhận định LF:** mức nhẹ hơn (0,85 đến 1,0 so 0,5 đến 0,7 ở round 1) giảm được thiệt hại
detection (round 1 tụt 20 đến 25 điểm %, round 2 tụt 2,5 đến 20 điểm % tuỳ biến thể, lf-m4
chỉ tụt 2,5 điểm %), nhưng KHÔNG biến thể nào có verdict "better" trên bất kỳ độ đo nào; chỉ
density nhỉnh hơn về điểm ở 2/4 biến thể (không có ý nghĩa thống kê, n quá nhỏ). lf-m4 còn
bị verdict "worse" có ý nghĩa trên KID. Hướng tạo hình (ngắn/mỏng/đứt đoạn) đúng về mặt khái
niệm nhưng cách triển khai hiện tại (affine thu mỏng đều + cắt khoảng liên tục) làm biên quá
mềm/mất nét so với thật, không bù được bằng việc giảm độ co.

**Khuyến nghị LF:** KHÔNG đưa biến thể nào vào ứng viên sản xuất. Cách tiếp cận
"length/width/gap scale" (cả round 1 và round 2, 7 tổ hợp tổng cộng) đã đi đến giới hạn: mọi
tổ hợp đều tệ hơn hoặc ngang mốc trên C2ST/KID/coverage. Vòng sau nên đổi hướng khác hẳn thay
vì dò thêm tham số trong không gian này, ví dụ: tăng `band_width_range` gốc của bộ sinh LF
(ngoài phạm vi sở hữu tệp nhánh này) trước khi co lại, hoặc xem lại hàm `_thin` (affine đều
toàn khối) có thể đang làm mất độ sắc biên cần có.

## Crack, xác nhận `crack_widen_px=2` với n=120 (so 18 ca ở vòng trước)

Thật: detection 0,744. n=120 ca/mức, ca còn vùng cả hai phía để so hình dạng: 77/120.

| Mức | detection (n=120) | C2ST | KID | density | coverage |
|---|---|---|---|---|---|
| widen=0 (trước khi lên SX) | 0,642 | 0,860 | 1,501 | 0,660 | 0,688 |
| widen=2 (SX hiện tại) | 0,675 | 0,897 | 1,772 | 0,725 | 0,688 |

Ghép cặp (bootstrap B=400, ca chung hình dạng n=77, detection ghép cặp n=120):

| Độ đo | delta (widen2 − widen0) | CI 95% | Verdict |
|---|---|---|---|
| detection (tỉ lệ tách vùng) | +0,033 | [+0,008, +0,067] | **better** (toàn dương) |
| C2ST | +0,037 | [−0,143, +0,123] | same |
| KID | +0,271 | [+0,093, +0,624] | **worse** (toàn dương) |
| density | −0,065 (phí tổn giảm = tốt hơn) | [−0,133, +0,044] | same |
| coverage | 0,000 | [−0,0625, +0,0625] | same |

**Nhận định crack:** với n lớn hơn hẳn (120 so 18), kết luận ĐẢO NGƯỢC một phần so vòng D:
detection cải thiện có ý nghĩa thống kê (+3,3 điểm %, nhỏ nhưng CI không phủ 0), nhưng KID
(một trong 4 độ đo hình dạng, ưu tiên 1 theo yêu cầu người dùng) TỆ HƠN có ý nghĩa thống kê
(CI [+0,09, +0,62] không phủ 0). C2ST cũng lệch hướng tệ hơn về điểm (0,897 so 0,860) dù CI
còn phủ 0 (n=77 cho so hình dạng, hẹp hơn n=120 dùng cho detection). density/coverage không
đổi rõ rệt.

Vòng D (n=18) từng thấy cr-2 tốt hơn trên "cả bốn độ đo cùng lúc" nhưng tự ghi nhận CI quá
rộng để khẳng định; n=120 lần này cho thấy nhận định đó không giữ được: mẫu nhỏ (18 ca) đã
đánh giá quá lạc quan, đặc biệt trên KID.

**Khuyến nghị crack:** vì SHAPE là ưu tiên 1 (trên detection theo yêu cầu), `crack_widen_px=2`
có một độ đo hình dạng tệ hơn có ý nghĩa thống kê (KID) đổi lấy một ít lợi ích detection. Đề
xuất CÂN NHẮC ROLLBACK về `crack_widen_px=0` hoặc thử mức trung gian (vd 1, đã có số liệu
round D cho thấy gần trùng mốc, chưa xác nhận lại n lớn). Không tự rollback (nhánh này không
sở hữu tệp knobs/HMI) — chuyển quyết định lên người dùng/điều phối.

## Dữ liệu & tệp liên quan
- Sinh LF: `output/realism-loop/lf-mild-variants/{lf-m1,lf-m2,lf-m3,lf-m4}/`
- Sinh crack: `output/realism-loop/crack-widen-confirm-120/{widen0,widen2}-part{0,1}/`
- Mốc dùng lại: `output/realism-loop/depth-base/prod/lack_of_fusion`
- Script + kết quả thô: scratchpad `lf_mild_variants.py`, `lf_mild_result.json`,
  `lf_mild_paired.json`, `crack_widen_confirm.py`, `crack_widen_result.json`

## Việc chưa làm / câu hỏi còn mở
- Chưa thử hướng thay thế cho LF (tăng `band_width_range` gốc hoặc sửa `_thin`); cần người
  sở hữu `mask_generator/lack-of-fusion-mask-generator.py` hoặc vòng sau có quyền sửa file đó.
- Chưa xác nhận lại `crack_widen_px=1` (round D) với n lớn; nếu rollback widen=2 thì nên thử
  mức 1 trước khi quay lại 0 hẳn.
- C2ST cho crack dùng n=77 (chỉ ca còn vùng cả 2 phía) trong khi detection dùng n=120; CI C2ST
  rộng do đó, chưa đủ để khẳng định/loại trừ hướng tệ hơn trên C2ST.

**Status:** DONE
**Summary:** LF mức nhẹ (4 biến thể) vẫn không cải thiện được độ đo hình dạng nào có ý nghĩa
(1 biến thể còn "worse" trên KID) dù detection đỡ tụt hơn round 1 — không đưa biến thể nào lên
sản xuất, cần đổi hướng tạo hình khác cho vòng sau. Xác nhận n=120 cho crack_widen_px=2: detection
tốt hơn có ý nghĩa (+3,3 điểm %) NHƯNG KID (độ đo hình dạng, ưu tiên 1) tệ hơn có ý nghĩa thống
kê — đảo ngược phần kết luận "tốt hơn cả 4 độ đo" của vòng D (n=18 quá nhỏ), nên cân nhắc rollback
hoặc thử mức 1.
**Concerns:** quyết định rollback crack_widen_px cần người dùng/điều phối phê duyệt (không
thuộc file ownership nhánh này); LF cần hướng thiết kế mới, không chỉ dò thêm tham số.
