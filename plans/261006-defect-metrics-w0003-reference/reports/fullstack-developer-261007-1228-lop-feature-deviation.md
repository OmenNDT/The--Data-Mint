# LOP (không ngấu/không thấu - lack_of_penetration): đặc trưng lệch nhiều nhất + đề xuất núm

Nguồn: round 18 (`realism/state/best.json`), eval `loop-20261007-112308-479-eval-18`, 40 ca sinh (27 có vùng),
16 ca thật W0003 có vùng (19 tổng). Ruler v1 (`w0003-16dac-trung-v1`, không loại đường mép). Ảnh: `output/realism-loop/iter-18/lack_of_penetration/`.

## 0. CẬP NHẬT (theo yêu cầu điều phối viên): kiểm tra lại tham chiếu thật — TÌM RA THƯỚC V1 HỎNG CHO LOP

**Kết luận ngắn: tham chiếu thật dùng ở mục 1-4 dưới đây KHÔNG đáng tin. 12/16 ca thật (75%) "có vùng" dưới ruler v1
thực ra là kernel bắt đường MÉP Ô (viền sáng/tối do chiếu sáng không đều ở rìa tile 278px), KHÔNG PHẢI vệt không
thấu. Đã DỪNG, KHÔNG chạy lưới GPU (việc 2) vì tinh chỉnh theo tham chiếu này là chỉnh sai hướng.**

Kiểm bằng cách vẽ đè vùng kernel chọn (`defect_features16.defect_features(..., return_region=True)`, ruler v1)
lên 16 ảnh thật có vùng, xem `reports/lop-real-region-overlay-261007.png` (4 ca mẫu, đỏ = vùng được chọn):
- `W0003_0035_tile_87`: vùng nhỏ (128 px), NẰM ĐÚNG trên vệt mảnh nhìn thấy được — hợp lệ.
- `W0003_0036_tile_47`: vùng dài gần hết bề ngang (261/278 px), nằm ở HÀNG 263-269 trên tổng 278 hàng — SÁT MÉP
  DƯỚI ảnh, không phải vệt lỗi (bản thân ảnh không có vệt rõ tại đó, vùng sáng/tối mịn do chiếu sáng).
- `W0003_0036_tile_65`: y như trên nhưng sát MÉP TRÊN (hàng 8-19/278).
- `W0003_0043_tile_24`: vùng cục bộ dạng khối thuôn, không chạm mép — hợp lệ (có thể là lỗi thật hoặc mép hàn,
  chưa phân biệt được chỉ bằng mắt).

Lượng hoá bằng chính hàm `_is_border_line` (tiêu chí v2 đã có sẵn trong code: aspect≥3, trải ≥85% cạnh, chạm
lề trong 20px): áp lên vùng lớn nhất của 16 ảnh thật → **12/16 bị đánh dấu là đường mép** (toàn bộ các tile
thuộc nguồn `W0003_0036`, trừ 2 ca nhỏ 87/88 và 2 ca thuộc `W0003_0043`). Dùng ruler v2 (loại đường mép trước
khi chọn vùng lớn nhất) trên đúng 19 ảnh LOP thật: tỉ lệ có vùng rơi còn **7/19 = 0,37** (không phải "9/19 mất"
như chú thích hiện tại trong `reference_w0003.py` dòng 55 — lệch số, cần soát lại).

**Đơn vị `bien_tuongphan`** (`defect_features16._shape`, dòng 132): `(diff[obj].mean() − diff[ring].mean()) /
noise`, với `diff = gaussian_filter(bg − img, 2.0)`, `bg = gaussian_filter(img, 25)`, `noise` = MAD mạnh của
`diff` toàn ảnh. Đây là đại lượng không thứ nguyên kiểu "số lần độ nhiễu" (SNR), không phải mức xám trực tiếp.
Dải viền mịn do chiếu sáng không đều có `diff` trong vùng gần bằng `diff` ở vành đai ngay sát nó (cả hai đều
nằm trên cùng gradient chiếu sáng trơn) → hiệu số gần 0, giải thích ĐÚNG tại sao trung vị thật ở mục 1 ra 0,004
(giả, do nhiễm đường mép) chứ không phải vì vệt không thấu thật "gần như trong suốt".

Tính lại 16 đặc trưng bằng ruler v2 (loại đường mép) trên 7 ca thật hợp lệ so synthetic (round 18, cũng đo lại
bằng v2, n=26/40 có vùng) — BỨC TRANH ĐẢO NGƯỢC so mục 1:
- `bien_tuongphan`: thật trung vị ở 7 ca hợp lệ nằm 0,8–6,2 (không còn gần 0), NGANG HOẶC CAO HƠN sinh (3,66) —
  không còn bằng chứng "sinh quá đậm so thật" rõ ràng như kết luận cũ.
- `vung_thuon` (độ thuôn): thật 6,73 (v2) so sinh 12,0 — **THẬT NGẮN/TRÒN HƠN SINH**, NGƯỢC HẲN kết luận mục 1
  ("thật dài thuôn hơn sinh" dựa trên v1 nhiễm đường mép kéo median lên 39,8 giả).
- `xuong_dai`: thật 0,141 (v2) so sinh 0,56 — cùng chiều đảo ngược.
- n quá nhỏ (7 thật, một số vẫn chưa chắc phải là LOP chứ không phải mép hàn thật — xem tile_24 ở trên) nên
  CHƯA kết luận số cụ thể, chỉ đủ để khẳng định: **phương hướng tinh chỉnh ở mục 1-4 (bien_tuongphan hạ sâu,
  lop_length_scale kéo dài) được suy ra từ một tham chiếu bị nhiễm nặng, cần coi là KHÔNG CÒN GIÁ TRỊ cho tới
  khi ruler LOP được sửa.**

Phụ: kiểm nhanh `Crack` (cũng giữ ruler v1 với cùng lý do "đường dài chạm mép tile" trong `reference_w0003.py`
dòng 54-57) — 12/32 = 37,5% ca cũng bị đánh dấu đường mép, nhẹ hơn LOP (75%) nhưng vẫn đáng ngại, NGOÀI PHẠM VI
LOP nên chỉ nêu để người giữ `defect_metrics`/ruler cân nhắc, không tự sửa trong báo cáo này.

**Quyết định theo đúng yêu cầu điều phối viên: KHÔNG chạy lưới GPU `lop_length_scale` ∈ {1,2; 1,3; 1,5} (việc 2).**
Lý do thước đo không đáng tin ở gốc; chạy lưới bây giờ sẽ tối ưu theo nhiễu, lãng phí 120 ảnh GPU của lưới dùng
chung với nhánh LF. Núm `lop_length_scale`/`lop_post_depth_min/max` đã nối dây ở mục 4 VẪN giữ nguyên trong code
(an toàn, mặc định = hành vi cũ, có test) nhưng giá trị đề xuất 1,3 cho `lop_length_scale` bị RÚT LẠI — không còn
cơ sở, chờ ruler sửa xong rồi đo lại từ đầu.

**Đề xuất sửa ruler cho LOP (không tự làm, ngoài phạm vi báo cáo này — cần người dùng quyết hướng):**
1. Đơn giản nhất: đổi `TYPE_RULER_OVERRIDES["lack_of_penetration"]` sang v2 (loại đường mép) như mặc định đa số
   loại khác. Cái giá: tỉ lệ có vùng thật tụt xuống 0,37 (rất thấp, < MIN_C2ST_N cho nhiều phép đo, `small_reference`
   sẽ bật) — có thể KHÔNG đủ mẫu để tính C2ST/KID tin cậy (ngưỡng tối thiểu 10 hàng).
2. Hoặc: giữ v1 nhưng nới `_is_border_line`/`BORDER_MARGIN` theo đặc điểm riêng LOP (lỗi thật nằm ở TÂM mối hàn
   theo chiều dọc, không sát mép trên/dưới tile như nhiễu chiếu sáng quan sát được) — ví dụ chặn thêm theo vị trí
   hàng tâm (chỉ giữ vùng nằm gần hàng giữa tile, loại vùng nằm trong dải N px sát mép trên/dưới bất kể aspect).
   Cần dữ liệu `weld_center_y` tương đương cho ảnh W0003 thật (hiện không có, cần suy ra từ cấu trúc ảnh hoặc từ
   vị trí tile trong ảnh gốc).
3. Hoặc: coi LOP là loại "reference_only" tạm thời (như metallic_inclusion) cho tới khi có ruler đáng tin, không
   dùng để chặn cổng.
Không chọn hộ hướng nào — cần người dùng/chủ sở hữu `defect_metrics` quyết, vì ảnh hưởng tới cổng nghiệm thu
chung, không riêng phạm vi LOP của báo cáo này.

---

## Nội dung gốc (mục 1-4 dưới đây dựa trên ruler v1 CHƯA sửa — ĐỌC KÈM CẢNH BÁO Ở MỤC 0)

## 1. Xếp hạng 16 đặc trưng theo |AUC-0,5| (lệch real so synthetic)

Tính lại bằng `defect_metrics.per_feature` trên toàn bộ 16 đặc trưng (bảng `top_features` trong result.json chỉ lưu 6):

| # | Đặc trưng | AUC | lệch | KS | thật (trung vị) | sinh (trung vị) | Ý nghĩa |
|---|---|---|---|---|---|---|---|
| 1 | bien_tuongphan | 0,947 | 0,447 | 0,86 | 0,004 | 3,66 | tương phản vùng/nền quanh |
| 2 | xuong_dai | 0,172 | 0,328 | 0,75 | 1,14 | 0,59 | chiều dài khung xương (chuẩn hoá) |
| 3 | vung_tron | 0,810 | 0,310 | 0,75 | 0,072 | 0,199 | độ tròn vùng lớn nhất |
| 4 | vung_lechtam | 0,213 | 0,287 | 0,75 | 0,9997 | 0,9967 | độ lệch tâm |
| 5 | vung_thuon | 0,213 | 0,287 | 0,75 | 39,8 | 12,3 | tỉ lệ trục dài/ngắn |
| 6 | vung_trontb | 0,748 | 0,248 | 0,59 | 0,068 | 0,242 | độ tròn trung bình MỌI vùng |
| 7 | vung_tile | 0,264 | 0,236 | 0,55 | 0,034 | 0,0205 | tỉ lệ diện tích toàn khung |
| 8 | bien_doc | 0,729 | 0,229 | 0,52 | 7,39 | 9,65 | độ dốc biên (độ sắc nét) |
| 9 | bien_sau | 0,303 | 0,197 | 0,59 | 13,2 | 8,54 | độ tối đỉnh / nhiễu |
| 10 | vung_sodom | 0,360 | 0,140 | 0,39 | 2 | 1 | số vùng tách được |
| 11 | vung_huong | 0,616 | 0,116 | 0,35 | 89,7° | 89,8° | góc hướng |
| 12 | vung_dayhop | 0,613 | 0,113 | 0,25 | 0,768 | 0,816 | độ lấp bbox |
| 13 | vung_dac | 0,604 | 0,104 | 0,20 | 0,877 | 0,895 | độ đặc (solidity) |
| 14 | xuong_renhanh | 0,574 | 0,074 | 0,15 | 0 | 0 | số điểm rẽ nhánh |
| 15 | vung_lon | 0,450 | 0,050 | 0,37 | 0,020 | 0,016 | diện tích vùng lớn nhất |
| 16 | bien_daodong | 0,481 | 0,019 | 0,33 | 0,379 | 0,409 | dao động biên |

Gộp hai cụm chính:
- **Cụm tương phản (#1 bien_tuongphan, #8 bien_doc, #9 bien_sau):** sinh tối/tương phản MẠNH HƠN thật rất nhiều (0,004→3,66). Đây là đặc trưng phân biệt tốt nhất (AUC gần hoàn hảo), khả năng cao là lực đẩy chính của KID 2,10 (tệ nhất trong 4 loại).
- **Cụm hình dạng dài/thuôn (#2,3,4,5,6,10):** vùng kernel dò được ở thật DÀI, MẢNH, gần như thẳng tắp hết khung (xuong_dai 1,14, vung_thuon 39,8, vung_tron 0,07); ở sinh thì NGẮN và tròn/cục hơn hẳn (0,59 / 12,3 / 0,20). Khớp quan sát bằng mắt: đường sinh đúng là một vệt thẳng sắc nhưng ngắn hơn phần thấy được ở ảnh thật.

## 2. Nhìn ảnh

Contact sheet (`reports/lop-contact-sheet-261007.png`, hàng trên = 3 ô thật W0003_0035_tile_84/85/86, hàng dưới = 3 ảnh sinh round 18): ảnh thật là vệt mảnh RẤT nhạt gần như chìm trong hạt phim, trải gần hết bề ngang ô; ảnh sinh có vệt rõ/đậm hơn thấy bằng mắt, ngắn hơn, và nền phông khác hẳn giữa các ca (một ca có mép hàn sáng lộ rõ phía trên) — có thể là nguyên nhân phụ khiến `bien_tuongphan` tính trên `diff` (nền trừ ảnh) bị nhiễu bởi cấu trúc nền, không riêng gì lỗi.

## 3. Kiểm chứng rẻ bằng CPU (không chạm GPU)

Replay `post_darkening.darken()` trên 20 `_predarken.npz` LOP cũ (`output/realism-sensitivity/sens-20261002-173715/base/lack_of_penetration/`, trước khi núm hình dạng LOP được bật — chỉ dùng để dò HƯỚNG hiệu ứng độ sâu, không phải số tuyệt đối vì bộ mask khác round 18), quét `post_depth_min/max` + `post_modulation`, đo lại 16 đặc trưng + tỉ lệ tách vùng bằng đúng ruler v1:

| biến thể | tỉ lệ tách vùng | bien_tuongphan | bien_sau |
|---|---|---|---|
| base (0,45-0,65, mod 0,65) | 0,55 | 4,87 | 10,9 |
| round18 (0,3663-0,5663, mod 0,65) | 0,60 | 3,76 | 9,75 |
| hạ sâu 0,25-0,40, mod 0 | 0,45 | 4,08 | 7,58 |
| hạ sâu 0,15-0,30, mod 0 | 0,30 | 4,84 | 8,43 |
| hạ sâu 0,15-0,30, mod 0,4 | 0,35 | 3,28 | 7,06 |
| hạ rất nhẹ 0,08-0,15, mod 0 | 0,15 | 0,49 (≈thật) | 4,02 |

Kết luận kiểm: **không có mức hạ sâu nào vừa an toàn cho tỉ lệ tách vùng vừa đưa bien_tuongphan về gần 0 như thật.** Tỉ lệ tách vùng rơi tuyến tính-dốc theo độ sâu; chỉ ở mức cực thấp (0,08-0,15) `bien_tuongphan` mới gần thật nhưng tỉ lệ tách vùng sập còn 0,15 (round18 đã 0,675, thật 0,842, cách nhau 16,7 điểm % — ĐÃ vượt hạn 10 điểm %, hạ thêm sẽ phạm chặn nặng hơn). `post_modulation` giúp cả hai chiều cùng lúc nhẹ (biến thể mod 0,4 tốt hơn mod 0 ở CÙNG mức sâu) nhưng không đủ bù. → không đề xuất hạ `post_depth_*` chung/riêng cho LOP lúc này; để núm `lop_post_depth_min/max` ở 0 (dùng chung) tới khi có vòng GPU đo trên đúng ảnh round 18 xác nhận mức an toàn.

Không replay được núm hình dạng (tilt/wave/gap/length) bằng CPU vì chúng tác động trước khi SD vẽ (đổi mặt nạ nguồn), cần sinh ảnh thật.

## 4. Núm đã nối dây (bước 2, additive, mặc định = hành vi cũ)

| Núm | Mặc định | Đề xuất | File | Ghi chú |
|---|---|---|---|---|
| `lop_length_scale` | 1,0 | 1,3 (CHƯA xác nhận GPU) | `mask_shaping.py` (`_lop`), `knobs.py`, `generator_hooks.py` TYPE_KNOBS | kéo dài mặt nạ theo chiều ngang quanh tâm khối, giữ bề dày — nhắm cụm #2-6 |
| `lop_post_depth_min/max` | 0 (dùng chung) | 0 (chưa đề xuất giá trị) | `knobs.py`, `post_darkening.py` (`effective_knobs`), `loop_partial.py` DARKEN_TYPE_KNOBS | độ sâu riêng LOP, theo đúng mẫu slag/ecav; để 0 vì mục 3 chưa tìm được mức an toàn |

Không đề xuất bật `lop_tilt_max_deg` / `lop_wave_amp_px` / `lop_gap_max` (đã có sẵn trong knobs.py, giá trị gợi ý cũ 4,0/2,5/3,0): phân tích cụm #2-6 cho thấy **thật ELONGATED/LIỀN MẠCH hơn sinh**, các núm này làm vệt NGHIÊNG/LƯỢN/ĐỨT thêm — đi SAI hướng cần cho LOP (có thể hợp cho crack, không hợp LOP). Nên giữ 0 trừ khi có bằng chứng khác.

Sửa file dùng chung (cờ theo quy tắc hợp tác, additive, test đạt):
- `realism/knobs.py`: thêm 3 mục REGISTRY (`lop_length_scale`, `lop_post_depth_min`, `lop_post_depth_max`) + comment lý do.
- `realism/post_darkening.py`: thêm `"lack_of_penetration": ("lop_post_depth_min", "lop_post_depth_max")` vào `per_type` của `effective_knobs`.
- `realism/loop_partial.py`: thêm 2 mục vào `DARKEN_TYPE_KNOBS`.
- `realism/generator_hooks.py`: thêm `"lop_length_scale"` vào `TYPE_KNOBS["lack_of_penetration"]`.
- `realism/mask_shaping.py`: thêm nhánh kéo dài trong `_lop()` (trước nghiêng/lượn/cắt).

Không ghi `realism/state/knobs.json`, `candidate-knobs.json`, `best.json`. Không khởi động lại dịch vụ, không commit.

## 5. Test

File mới `pipeline/tests/test-realism-shaping-lop.py` (9 test, unittest, không pytest): mặc định không đổi mặt nạ/ảnh, `lop_length_scale` kéo dài đúng chiều giữ bề dày, `shape_mask` tạo hình lại khi CHỈ núm length_scale khác mặc định, `lop_post_depth_*` chỉ chạm loại LOP (không ảnh hưởng crack/LF/porosity/slag), `loop_partial.affected_types` map đúng. Chạy toàn bộ `tests/test-realism-*.py` (kể cả các bộ không thuộc LOP) sau khi sửa: tất cả PASS, không có regressions.

## 6. Đề xuất bước tiếp theo (không tự làm, cần người dùng/GPU)

1. Chạy lưới GPU nhỏ (≤~120 ảnh) qua `plant_gpu_lease`: `lop_length_scale` ∈ {1,0 (mốc), 1,2, 1,3, 1,5} × 40 ca `exam_set.subset(["lack_of_penetration"], 40)`, đo lại bằng `defect_eval.evaluate_defects`, so sánh xuong_dai/vung_tron/vung_thuon/vung_trontb/C2ST/KID với mốc round 18. Mẫu script tham khảo `/tmp/.../scratchpad/lf_mild_variants.py` (đã dùng làm khuôn cho script sweep CPU ở đây).
2. Nếu cụm hình dạng cải thiện mà tỉ lệ tách vùng không xấu đi, GHÉP thêm một mức hạ `lop_post_depth_min/max` RẤT nhẹ (ví dụ 0,30/0,45, cao hơn round18's shared range một chút để tránh cộng dồn rủi ro) + đo lại, vì cụm tương phản (#1 bien_tuongphan) vẫn là lực đẩy KID lớn nhất chưa xử lý được an toàn bằng CPU.
3. Gốc rễ #1 (bien_tuongphan) có thể một phần do ĐO chứ không chỉ do SINH: ảnh thật đạt tỉ lệ tách vùng cao (0,84) dù tương phản trung bình gần 0 — gợi ý kernel Hessian dò theo cấu trúc rãnh chứ không cần tối sâu; ảnh sinh dùng độ sâu làm tối tuyệt đối (phù hợp quy ước phim X-quang, post_darkening.py dòng 7-9) nên luôn có tương phản thật sự lớn hơn. Khó đóng hoàn toàn khoảng cách này mà không phá tỉ lệ tách vùng — nên bàn với người dùng có chấp nhận một mức dư `bien_tuongphan` làm đánh đổi lấy tỉ lệ tách vùng hay không, thay vì coi đây thuần là bài toán chỉnh núm.

## Câu hỏi chưa giải quyết
- **(MỚI, chặn mọi tinh chỉnh tiếp theo)** Ruler LOP dùng sai: cần người dùng/chủ `defect_metrics` chọn 1 trong 3
  hướng sửa ở mục 0 (đổi sang v2, thu hẹp vùng loại-mép riêng cho LOP theo vị trí tâm hàn, hoặc tạm đặt
  `reference_only`) trước khi bất kỳ ai tinh chỉnh núm LOP tiếp — đo trên thước hỏng sẽ tối ưu nhầm hướng.
- Soát lại chú thích "9/19 mất" ở `reference_w0003.py` dòng 55: số đo lại ra 12/19 mất (v1→v2), không phải 9/19;
  chưa rõ do thay đổi threshold/calibration giữa lúc viết chú thích và hiện tại, hay nhầm số khi viết.
- Crack cũng giữ ruler v1 với lý do tương tự và cũng bị nhiễm đường mép (12/32 = 37,5%, nhẹ hơn LOP) — ngoài
  phạm vi LOP, nên người giữ ruler cân nhắc kiểm luôn.
- Mức `lop_length_scale` 1,3 đề xuất ở mục 4/6 (dựa trên ruler v1 hỏng) coi như RÚT LẠI; số liệu v2 sơ bộ (n=7,
  quá nhỏ) cho chiều NGƯỢC LẠI (thật ngắn/tròn hơn sinh) — cần đo lại từ đầu sau khi ruler sửa, KHÔNG dùng 1,3.
- Tỉ lệ tách vùng của sinh dưới ruler v1 (0,675) thấp hơn thật (0,842) quá hạn chặn (10 điểm %) — nhưng con số
  "thật 0,842" CŨNG dựa trên ruler v1 nhiễm đường mép (12/16 ca "có vùng" là giả), nên bản thân con số 16,7 điểm %
  cách biệt này không đáng tin cho tới khi ruler sửa xong; không còn là kết luận chắc chắn như báo cáo gốc.
- Việc 2 (lưới GPU `lop_length_scale`) CHƯA chạy theo đúng chỉ đạo điều phối viên (dừng khi tham chiếu không
  hợp lệ) — không phải bị bỏ sót, là quyết định có chủ đích.

**Status:** DONE_WITH_CONCERNS (việc 1 xong, phát hiện tham chiếu hỏng → việc 2 CHỦ ĐỘNG DỪNG theo đúng chỉ đạo, không chạy lưới GPU)
**Summary:** Việc 1 (soát tham chiếu thật): vẽ đè vùng kernel chọn lên ảnh thật + lượng hoá bằng `_is_border_line`
có sẵn trong code → 12/16 ca thật (75%) "có vùng" dưới ruler v1 thực ra là đường MÉP TILE do chiếu sáng không đều
(dải đầy ngang, sát hàng 0 hoặc hàng 277/278), KHÔNG PHẢI vệt không thấu — giải thích đúng tại sao `bien_tuongphan`
thật ra gần 0 (0,004): vành mép và vành đai quanh nó cùng nằm trên gradient sáng trơn nên hiệu số gần 0, không
phải vì lỗi thật "mờ gần trong suốt". Đo lại bằng ruler v2 (loại đường mép, đã có sẵn trong code) trên 7 ca thật
còn hợp lệ: `bien_tuongphan` thật 0,8-6,2 (ngang/cao hơn sinh, không còn thấp bất thường), `vung_thuon`/`xuong_dai`
thật THẤP hơn sinh (ngược hẳn kết luận v1). → Toàn bộ phân tích + đề xuất núm ở mục 1-6 (dựa trên v1) KHÔNG còn
hiệu lực cho tới khi ruler LOP được sửa. Đã DỪNG theo đúng chỉ đạo, không chạy lưới GPU `lop_length_scale`.
**Concerns:** (1) đây là lỗi ở ruler dùng chung (`defect_features16._is_border_line`/`reference_w0003.
TYPE_RULER_OVERRIDES`), không phải lỗi riêng của núm LOP — sửa cần người giữ `defect_metrics` quyết hướng, ngoài
quyền hạn/phạm vi file sở hữu của báo cáo LOP; (2) n=7 real sau lọc v2 quá nhỏ để kết luận số cụ thể, chỉ đủ để
khẳng định chiều phân tích cũ sai, chưa đủ để đề xuất số mới; (3) Crack cùng cơ chế, cùng bị ảnh hưởng nhẹ hơn —
cần ai đó kiểm ngoài phạm vi báo cáo này; (4) núm `lop_length_scale`/`lop_post_depth_min/max` đã nối dây trong
code vẫn AN TOÀN (mặc định = hành vi cũ, có test, không đổi production) nên không cần revert, chỉ cần không dùng
giá trị đề xuất 1,3 cho tới khi đo lại.

---

## 7. Tinh chỉnh bằng mắt (việc mới, 7/10): LOP đã thành reference-only, chọn núm qua sheet đối chiếu

Theo quyết định người dùng (ruler v3 chỉ còn 6/19 ca thật có vùng → LOP ra khỏi cổng, chuyển `reference_only`),
không dùng C2ST/KID/tách-vùng để chặn nữa — chọn núm BẰNG MẮT qua sheet đối chiếu thật/sinh. Mục tiêu hình dạng
(từ `v3-overlay-real-lack_of_penetration-261007.png`): vệt RẤT MỜ, MẢNH, THẲNG, trải gần hết bề ngang ô.

### Đã sinh (40/48 ảnh GPU, trong hạn)
Dùng ĐÚNG 8 ca/seed LOP đầu tiên của round 18 (`output/realism-loop/iter-18/fixed-jobs.json`, case 000-007),
qua `REALISM_KNOBS` + `plant_gpu_lease` (chờ lượt, không chen ngang cycle `loop-20261007-132215-585` đang giữ GPU):

| Thẻ | Núm (khác mặc định) | Ảnh |
|---|---|---|
| lop-depth-low | `lop_post_depth_min=0.15, lop_post_depth_max=0.25` | 8 |
| lop-depth-mid | `lop_post_depth_min=0.25, lop_post_depth_max=0.35` | 8 |
| lop-length-1.3 | `lop_length_scale=1.3` | 8 |
| lop-length-1.6 | `lop_length_scale=1.6` | 8 |
| lop-combo (thêm, còn hạn GPU) | `lop_post_depth_min=0.25, lop_post_depth_max=0.35, lop_length_scale=1.3` | 8 |

Tổng 40 ảnh (≤48). Thư mục: `output/realism-loop/lop-visual-variants/<thẻ>/`.

### Sheet đối chiếu
`plans/261006-defect-metrics-w0003-reference/reports/lop-visual-variants-contact-sheet-261007.png` — hàng 1 = 8 ô
thật (đa dạng cả 3 nguồn W0003_0035/0036/0043), hàng 2 = round18 gốc (mốc), 5 hàng sau = 5 biến thể. Ảnh sinh
CẮT cửa sổ 278px quanh tâm mặt nạ (`reference_w0003.crop_synthetic_grid`, đúng cách `defect_eval` dùng để so
thật/sinh) thay vì co nhỏ cả khung 512 — co nhỏ làm sai tỉ lệ mỏng/dày so thật.

### Tỉ lệ tách vùng (ruler v3, chỉ để tham khảo — KHÔNG còn chặn cổng vì đã reference_only)
Thật (tham chiếu) = 0,32 (6/19).

| Biến thể | Tỉ lệ tách vùng |
|---|---|
| round18 (mốc) | 0,65 |
| lop-depth-low | 0,00 |
| lop-depth-mid | 0,12 |
| lop-length-1.3 | 0,38 |
| lop-length-1.6 | 0,38 |
| lop-combo | 0,12 |

### Đo thêm bằng mắt pixel thô (độ tương phản tại lõi vệt, không qua kernel)
Đo `nền cục bộ quanh mặt nạ − trung bình trong mặt nạ` (mức xám thô, cửa sổ ±15px quanh mặt nạ), so với
4 ca thật đo tương tự tại điểm lệch nền lớn nhất (DoG): thật dao động 5,0-10,7 (case có vùng hợp lệ; case
`tile_47` cho giá trị âm vì đỉnh lệch nền rơi đúng vào đường mép tile giả, khớp phát hiện ở mục 0 — bỏ qua):

| | Tương phản thô | Nhịp (cột mặt nạ) |
|---|---|---|
| THẬT (3 ca hợp lệ) | 5,0 / 5,6 / 10,7 | — |
| round18 | 17,1 | 98-410 (61%) |
| lop-depth-low | 2,7 | 98-410 (61%) |
| lop-depth-mid | 7,7 | 98-410 (61%) |
| lop-length-1.3 | 17,7 | 51-457 (79%) |
| lop-length-1.6 | 17,4 | 4-504 (98%) |
| lop-combo | 8,1 | 51-457 (79%) |

### Xếp hạng bằng mắt (nhìn trực tiếp sheet + số đo thô ở trên)

1. **lop-combo** (depth 0,25-0,35 + length 1,3) — HẠNG 1: tương phản 8,1 rơi đúng dải thật (5-11), nhịp 79% bề
   ngang khớp "trải gần hết tile" của mục tiêu; nhìn sheet vệt mảnh, không còn sắc/đậm như round18, độ dài hợp lý.
2. **lop-length-1.3** — nhịp tốt (79%) nhưng tương phản vẫn ở mức round18 (17,7, gấp ~2-3 lần thật) — vệt vẫn
   đậm/sắc hơn thật rõ khi nhìn so hàng 1.
3. **lop-depth-mid** — tương phản đúng dải thật (7,7) nhưng nhịp chỉ 61% (ngắn hơn mục tiêu "gần hết bề ngang").
4. **lop-depth-low** — tương phản 2,7 là MỜ NHẤT trong các biến thể (gần ca thật mờ nhất), nhưng nhìn sheet vài
   ca gần như BIẾN MẤT hoàn toàn (tách vùng tụt về 0,00) — rủi ro đi quá tay, mất luôn khuyết tật thay vì chỉ làm mờ.
5. **lop-length-1.6** — nhịp 98% (gần hết khung, hơi quá — vài ca thật chỉ 1/3-1/2 bề ngang) và tương phản vẫn cao
   (17,4) — không cải thiện so 1,3, chỉ kéo dài thêm không cần thiết.
6. **round18 (mốc)** — hạng chót: tương phản cao nhất (17,1), nhịp ngắn nhất trong nhóm sinh (61%) — xa thật nhất.

### Đề xuất núm (chưa ghi vào knobs.json/best.json, chờ người dùng duyệt)
**`lop_post_depth_min=0,25`, `lop_post_depth_max=0,35`, `lop_length_scale=1,3`** (= biến thể `lop-combo`).
Lý do: cân bằng tốt nhất cả 4 tiêu chí mắt (mờ, mảnh, dài, thẳng) trong 5 biến thể đã thử, số đo tương phản thô
khớp dải thật. Tỉ lệ tách vùng 0,12 thấp hơn thật (0,32) nhưng KHÔNG còn là điều kiện chặn (reference_only) —
chỉ nêu để biết.

Gợi ý tinh thêm một vòng sau (không tự làm, vượt hạn ảnh của việc này): thử `lop_post_depth 0,20-0,30` (giữa
depth-low và depth-mid) + `length_scale 1,3` xem có đẩy tương phản xuống gần giữa dải thật (≈7) mà không rơi
vào vùng biến mất như depth-low hiện tại.

### Test/kiểm
Không sửa code sản xuất ở việc này (chỉ dùng núm đã nối dây từ mục 4-6, qua `REALISM_KNOBS`), không ghi
knobs.json/candidate-knobs.json/best.json, không khởi động lại dịch vụ, không commit. GPU: 40/48 ảnh, lấy phiếu
đúng quy trình `plant_gpu_lease`, không chen ngang cycle 585.

**Status:** DONE
**Summary:** 5 biến thể (depth-low, depth-mid, length-1.3, length-1.6, combo) × 8 ảnh = 40/48 ảnh GPU, dùng đúng
8 ca/seed LOP của round 18. Sheet đối chiếu + đo tương phản thô xác nhận **combo (depth 0,25-0,35 + length
1,3)** khớp mục tiêu "mờ, mảnh, thẳng, trải gần hết bề ngang" tốt nhất trong 5 biến thể — ĐỀ XUẤT dùng biến thể
này. depth-low mờ nhất nhưng rủi ro biến mất khuyết tật (tách vùng 0,00); length-1.6 kéo hơi quá dài; length-1.3
riêng lẻ vẫn còn đậm. Tỉ lệ tách vùng chỉ còn mang tính tham khảo, không chặn (LOP đã reference-only).
**Concerns:** (1) chỉ 8 ca/biến thể, n nhỏ, nhận định hình dạng dựa phần lớn vào quan sát mắt + đo tương phản
thô 1 điểm đại diện/ảnh (không phải đo đầy đủ 16 đặc trưng) — nếu cần số liệu chắc hơn trước khi đặt vào
production nên sinh thêm ca; (2) chưa thử núm "dải mỏng hơn" (độ dày) vì không có núm sẵn — xem đề xuất bên dưới,
KHÔNG tự refactor bộ sinh; (3) biến thể combo chưa chạy qua bootstrap ghép cặp đầy đủ, chỉ so trực quan + 1 chỉ
số tương phản thô mỗi ca.
**Đề xuất núm dùng:** `lop_post_depth_min=0,25`, `lop_post_depth_max=0,35`, `lop_length_scale=1,3` (biến thể combo).

### Đề xuất núm "dải mỏng hơn" (CHỈ ĐỀ XUẤT, không tự làm — đúng yêu cầu không refactor bộ sinh)
`mask_generator/lack-of-penetration-mask-generator.py` hiện hardcode `thickness_range: Tuple[int, int] = (2, 4)`
(dòng 45, `LackOfPenetrationMaskGenerator.__init__`). Có thể thêm núm `lop_thickness_scale` (mặc định 1,0) theo
đúng mẫu `lof_band_width_scale` (`generator_hooks.lof_generation_kwargs`, truyền `thickness_range` đã co qua
kwargs khi khởi tạo generator, KHÔNG đổi logic vẽ). Ngoài phạm vi việc này (không refactor), chỉ ghi lại hướng
làm cho vòng sau nếu người dùng muốn vệt mảnh hơn nữa ngoài núm làm tối/kéo dài đã có.
