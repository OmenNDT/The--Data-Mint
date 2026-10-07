# Độ sâu làm tối riêng cho clustered_porosity và linear_porosity

Nhánh A, phase 2, plan `261006-defect-metrics-w0003-reference`. File sở hữu: `realism/post_darkening.py`
(chỉ `effective_knobs`), `tests/test-realism-pore-type-depth.py`.

## 1. Code

`effective_knobs(knobs, defect_type)` trong `realism/post_darkening.py` nay có 3 mức ưu tiên độ sâu làm tối,
mỗi mức chỉ áp dụng khi CẢ cận dưới và cận trên > 0:

1. Riêng dạng: `clustered_post_depth_min/max` (cho `clustered_porosity`), `linear_post_depth_min/max` (cho
   `linear_porosity`).
2. Riêng rỗ khí nói chung: `pore_post_depth_min/max` (áp cho cả 3 dạng rỗ khí).
3. Độ sâu chung: `post_depth_min/max`.

Mặc định mọi núm riêng = 0 nên hành vi cũ giữ nguyên hoàn toàn (đã kiểm bằng test pixel y hệt).

9 test trong `tests/test-realism-pore-type-depth.py`: mặc định không đổi gì (2 test, gồm 1 test so điểm ảnh
`darken()`), ưu tiên đúng thứ tự riêng dạng > riêng rỗ khí > chung (4 test), loại không phải rỗ khí không bị
đụng (2 test), yêu cầu cả 2 cận > 0 mới áp (1 test). Chạy: `.venv/bin/python3 tests/test-realism-pore-type-depth.py`
= OK (9/9). Không ảnh hưởng `tests/test-realism-linear-porosity-knobs.py` (5/5 OK), `tests/test-realism-loop-partial.py`
(14/14 OK), `tests/test-realism-pore-darken-depth.py` (4/4 OK).

## 2. Dữ liệu gốc

Sinh 40 ca `clustered_porosity` + 40 ca `linear_porosity` bằng núm SẢN XUẤT hiện tại (seed cố định, nền lấy từ
bộ đề thi, `REALISM_SAVE_PREDARKEN=1`), GPU 100% thành công 80/80. Lưu tại
`output/realism-loop/pore-type-depth-base/`. Từ đó tính lại (replay CPU, không tốn GPU) nhiều mức độ sâu,
đo bằng `realism.defect_eval.evaluate_defects` (so W0003) và ghép cặp với mức hiện tại bằng
`realism.loop_gate_v2_metrics.paired_metrics`.

Mức hiện tại (production): cả 2 dạng đang rơi về `pore_post_depth_min/max` = 0,80 đến 1,00 (núm riêng dạng
đang = 0).

## 3. Kết quả clustered_porosity (W0003 tham chiếu chỉ 5 hàng, `small_reference=true`, chưa đủ 10 hàng để tính C2ST)

| Mức | bien_tuongphan syn (thật 2,03) | det_syn (thật 0,833) | KID | density | KID so hiện tại |
|---|---|---|---|---|---|
| 0,30 đến 0,50 | ra khỏi top đặc trưng lệch (AUC 0,04 đến 0,26 cho vùng/hình) | 0,575 (lệch 25,8 đp) | 1,685 | 0,859 | tốt hơn (giảm 2,95) |
| 0,45 đến 0,65 | 3,71 (AUC 0,75) | 0,825 (lệch 0,8 đp) | 0,542 (THẤP NHẤT) | 0,811 (tốt hơn) | tốt hơn nhiều (giảm 4,03) |
| 0,60 đến 0,80 | 4,58 (AUC 0,87) | 0,85 (lệch 1,7 đp) | 1,969 | 0,831 (tốt hơn) | tốt hơn (giảm 2,19) |
| 0,80 đến 1,00 (hiện tại) | 5,16 (AUC 0,92, lệch nhất) | 0,925 (lệch 9,2 đp) | 2,568 (CAO NHẤT) | 0,669 | (gốc) |

Mức 0,45 đến 0,65 vượt trội toàn diện: KID thấp nhất trong cả 4 mức (không chỉ so hiện tại), density gần 1
nhất, tỉ lệ tách vùng khớp thật gần như tuyệt đối (0,825 so 0,833, lệch 0,8 điểm phần trăm, thừa biên so ngưỡng
10 đp), và bien_tuongphan (độ tương phản biên) giảm từ lệch AUC 0,92 xuống 0,75, tức đỡ "quá đậm" rõ rệt dù
chưa về đúng 2,03 của thật. Mức 0,30 đến 0,50 nhạt quá, tỉ lệ tách vùng tụt xuống 0,575, lệch 25,8 điểm phần
trăm (vượt ngưỡng 10), vi phạm ưu tiên của người dùng (giữ lệch tách vùng dưới 10 đp), dù một số đặc trưng
hình (vung_tron, vung_dayhop) coi được tốt lên.

**Đề xuất clustered_porosity: `clustered_post_depth_min=0,45`, `clustered_post_depth_max=0,65`.**

Lưu ý: tham chiếu thật chỉ 5 hàng (vật lý lỗi cụm hiếm trong bộ ảnh gốc), nên AUC/KS từng đặc trưng dao động
mạnh, C2ST không tính được (cần ≥ 10 hàng mỗi phía). Kết luận có hướng rõ (đơn điệu qua 3/4 mức) nhưng độ tin
cậy số liệu thấp hơn linear; nên xác nhận lại khi có thêm ảnh chụp cụm thật.

## 4. Kết quả linear_porosity (tham chiếu 10 hàng, C2ST tính được)

| Mức | bien_tuongphan syn (thật 12,13) | bien_doc syn (thật 20,31) | det_syn (thật 1,0) | C2ST | KID | density |
|---|---|---|---|---|---|---|
| 0,80 đến 1,00 (hiện tại) | 5,47 (AUC 0,195) | 11,72 (AUC 0,133) | 0,975 | 0,882 | 1,605 | 0,733 |
| 1,00 đến 1,00 (trần độ sâu) | 6,20 (AUC 0,21) | 11,64 (AUC 0,149) | 0,975 | 0,790 (tốt hơn, CI chưa chắc) | 1,032 (tốt hơn) | 0,805 (tốt hơn) |
| 0,80 đến 1,00 + tắt điều biến* | 8,28 (AUC 0,28) | 13,88 (AUC 0,21) | 1,0 | 0,755 (tốt hơn, CI loại 0) | 0,500 (tốt hơn) | 0,99 (tốt hơn) |
| 1,00 đến 1,00 + tắt điều biến* | 9,39 (AUC 0,315, GẦN NHẤT) | 14,15 (AUC 0,218) | 1,0 | 0,7325 (TỐT NHẤT) | 0,411 (TỐT NHẤT) | 1,08 |

(*) tắt điều biến (`post_modulation=0`) là núm CHUNG, không riêng theo dạng; thử trong replay chỉ để đo
hiệu ứng, KHÔNG nằm trong núm được giao (`linear_post_depth_*`) nên không đưa vào đề xuất núm sản xuất.

Mọi mức thử đều tốt hơn hiện tại trên cả 4 độ đo ghép cặp (C2ST, KID, density, một số coverage bằng nhau),
không mức nào tệ hơn. Trong phạm vi núm được giao (chỉ độ sâu, không đổi điều biến), mức trần
`linear_post_depth_min/max = 1,00/1,00` là lựa chọn tốt nhất đạt được: C2ST giảm từ 0,882 xuống 0,790, KID
giảm từ 1,605 xuống 1,032, density từ 0,733 lên 0,805 (gần 1 hơn), detection không đổi (0,975, lệch thật 1,0
chỉ 2,5 đp, trong ngưỡng).

**Đề xuất linear_porosity: `linear_post_depth_min=1,00`, `linear_post_depth_max=1,00`.**

**Phát hiện thêm, KHÔNG thuộc phạm vi núm được giao:** dù đã kéo lên trần độ sâu, bien_tuongphan sinh ra
(6,20) vẫn cách xa thật (12,13), vì điều biến dọc lỗi (`post_modulation=0,65`, núm CHUNG) làm nhạt biên ngẫu
nhiên. Tắt điều biến riêng cho chuỗi (giữ chung cho cụm/đơn) cho kết quả tốt hơn RÕ RỆT trên mọi độ đo kể cả
khi vẫn ở độ sâu thấp (0,80 đến 1,00): C2ST 0,755 (CI loại 0, có ý nghĩa), KID 0,500, density 0,99 (gần như
hoàn hảo), detection đúng 1,0. Kết hợp cả trần độ sâu và tắt điều biến cho kết quả tốt nhất tuyệt đối
(C2ST 0,7325, KID 0,411). Để khai thác hết mức này cần núm `linear_post_modulation` RIÊNG (hiện chưa có
trong `realism/knobs.py`), vì `post_modulation` hiện là núm chung ảnh hưởng cả rỗ khí đơn/cụm/nứt/vv. Đề xuất
lead xem xét đăng ký núm riêng này ở lượt sau nếu muốn khai thác tiếp (ngoài phạm vi file sở hữu của nhánh
này, `realism/knobs.py` + `realism/loop_partial.py` không thuộc quyền sửa ở đây).

Ngay cả ở mức tốt nhất đo được (trần độ sâu + tắt điều biến), bien_tuongphan sinh (9,39) vẫn thấp hơn thật
(12,13): trần `base_strength=0,92` cho `linear_porosity` (hằng số `DARKEN_BY_TYPE` trong
`batch_manager/batch-production-main.py`, ngoài phạm vi sở hữu của nhánh này) có thể là giới hạn vật lý
cuối cùng chặn không cho vượt qua; cần phase khác nếu muốn đẩy tiếp.

## 5. Tệp liên quan

- Sửa: `/home/sontn/Projects/The Data Mint/pipeline/realism/post_darkening.py` (chỉ `effective_knobs`)
- Mới: `/home/sontn/Projects/The Data Mint/pipeline/tests/test-realism-pore-type-depth.py`
- Dữ liệu gốc (predarken): `/home/sontn/Projects/The Data Mint/output/realism-loop/pore-type-depth-base/`
- Kết quả lưới replay (thô): `/tmp/claude-1000/.../scratchpad/pore-type-depth-report.json` (tạm, trong
  scratchpad phiên này, không phải tài sản dự án)

## 6. Chưa áp dụng vào sản xuất

Đúng theo chỉ dẫn: KHÔNG ghi `realism/state/knobs.json` hay `candidate-knobs.json`. Hai giá trị đề xuất ở
trên (`clustered_post_depth_min/max = 0,45/0,65`; `linear_post_depth_min/max = 1,00/1,00`) chờ lead/người
dùng duyệt rồi đưa vào qua HMI (promote) như mọi núm khác.

**Status:** DONE
**Summary:** Đã nối dây `effective_knobs` theo 3 mức ưu tiên (riêng dạng > riêng rỗ khí > chung), 9 test
qua, không hồi quy 3 bộ test liên quan. Sinh 80 ảnh gốc GPU, lưới replay CPU 8 biến thể. Đề xuất clustered
0,45 đến 0,65 (KID thấp nhất, detection khớp thật, density tốt hơn), linear 1,00 đến 1,00 (tốt hơn hiện tại
trên mọi độ đo ghép cặp). Phát hiện thêm: điều biến (`post_modulation`) riêng cho chuỗi sẽ cải thiện mạnh
hơn nữa nhưng cần núm mới ngoài phạm vi file sở hữu.
**Concerns/Blockers:** clustered chỉ 5 hàng tham chiếu thật (C2ST không tính được, độ tin cậy thấp hơn
linear). Trần độ sâu + base_strength 0,92 có thể chặn linear không bao giờ về đúng độ tương phản biên thật;
cần phase khác (núm điều biến riêng theo dạng, hoặc xem lại base_strength) nếu muốn đóng hết khoảng cách.
