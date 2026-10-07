# Metallic inclusion (bright-on-film) ruler feasibility — CPU-only scratch study

Scratch script: `/tmp/claude-1000/-home-sontn-Projects-The-Data-Mint/e51b2322-3e35-41c7-bfc8-a257b4def578/scratchpad/invert_calib.py`
(không sửa file repo, Pool=8). Dữ liệu: 3 ô W0003 thật (`dataset/4.Welds_W0003_Clear_Defects_278/Metallic_Inclusion/`),
40 ảnh tổng hợp (`output/realism-loop/remaining-types-prod/metallic_inclusion/`), 1654 ô nền sạch W0003 (278×278,
cắt×2 từ 827 mảnh, seed 42, giống `reference_w0003._clean_crops`).

## Câu 2 trước — 3 ô thật có đúng là vùng sáng kim loại không

Nhìn trực tiếp (Read 3 file PNG):

- `W0003_0053_tile_70.png`: có đốm trắng nhỏ rõ, hình chữ V/cánh bướm, nằm giữa bên phải ô.
- `W0003_0054_tile_78.png`: có đốm trắng rõ, hình giọt, giữa ô; thêm một vệt tối nhỏ (nứt?) góc dưới trái, không
  liên quan metallic.
- `W0003_0055_tile_78.png`: có một mảng sáng hơn nền, mờ, không sắc nét bằng hai ô trên nhưng vẫn phân biệt được.

Cả 3 ô đều đúng là lớp Metallic_Inclusion (đốm sáng cục bộ do kim loại đặc chắn tia), không bị gán nhầm nhãn.

**Nhưng** cả 3 ô cũng có đặc điểm chung làm hỏng phép đo: nửa trái ô tối (nền phim ngoài mối hàn), nửa phải sáng
(mối hàn), ranh giới tối/sáng này chiếm phần lớn diện tích ô, ảnh hưởng mạnh hơn đốm kim loại nhỏ về mặt diện tích.

## Câu 1 — đảo ảnh (bright→dark) rồi hiệu chỉnh ngưỡng kiểu cũ có chạy được không

**Hiệu chỉnh ngưỡng (region_scores, mức ô):** chạy được y hệt thủ tục `calibrate_thresholds`. Trên 1654 ô nền sạch
đã đảo (255 − ảnh), đạt `achieved_nd_rate = 0.1554` (mục tiêu 0,155), ngưỡng `thr_inv = {dom_16: 0.963, dai_8: 1.473,
ngang_8: 1.245}` — gần ngưỡng gốc dark-mode (`{dom_16: 0.919, dai_8: 1.828, ngang_8: 1.631}`), hợp lý vì đảo ảnh chỉ đổi
dấu građient chứ không đổi phân bố nhiễu.

**Nhưng ở mức đặc trưng 16 chiều (`defect_features`/`kernel_mask` + `_shape` chọn vùng LỚN NHẤT theo diện tích) phát
hiện lỗi nghiêm trọng, không đặc thù riêng cho đảo ảnh:**

1. **False-alarm mức đặc trưng cao gấp đôi mục tiêu, kể cả ở dark-mode gốc đang dùng cho các loại khác.** Trên
   200 ô nền sạch đầu tiên (chính các ô dùng hiệu chỉnh): `has_region` = 0,335 (đảo) và 0,300 (gốc, không đảo) — cả
   hai đều cao hơn nhiều so với 0,155 mà `achieved_nd_rate` báo cáo. Lý do: `region_scores` dùng `area_opening`
   connectivity=2 (chặt hơn), còn `kernel_mask`/`defect_features` dùng `label` mặc định + lọc `area>=25` (lỏng hơn).
   Đây là sai lệch đã tồn tại sẵn trong luật hiệu chỉnh của 11 loại dark-mode hiện có, **không phải lỗi mới của
   bright-mode** — nhưng nếu thêm bright-mode thì kế thừa luôn nhược điểm này.

2. **Lỗi nghiêm trọng hơn, đặc thù cho ảnh có viền hàn sáng/tối rõ (áp cho cả bright-mode VÀ dark-mode khi ảnh có
   viền hàn mạnh): vùng LỚN NHẤT mà `_shape` chọn để tính 12+4 đặc trưng không phải là đốm kim loại, mà là dải
   biên tối/sáng của mối hàn (macro gradient), vì dải này luôn lớn hơn đốm kim loại nhỏ về diện tích.**
   - Cả 3 ô thật: vùng lớn nhất chiếm 23–28% diện tích ô (bbox cao gần hết chiều cao 278, xem overlay mask đã lưu
     `scratchpad/mask_W0003_00{53,54}_*.png`) — đúng là dải biên sáng/tối của mối hàn, KHÔNG phải đốm kim loại
     (đốm chỉ vài chục đến vài trăm điểm ảnh).
   - Ảnh tổng hợp `metallic_inclusion_000160`: vùng lớn nhất là 2 dải mỏng ngang gần đỉnh ảnh (area 5233 và 3195,
     do viền chuyển sáng/tối ở top ảnh), còn đốm kim loại thật (area 178, đúng vị trí đốm trắng nhìn thấy) bị
     xếp hạng 3, bị `_shape` BỎ QUA hoàn toàn.
   - Hệ quả: `vung_lon`, `vung_tron`, `bien_*`... đo trên ảnh thật (0,23–0,29 diện tích, tròn thấp 0,09–0,18) và
     trên ảnh tổng hợp (trung vị diện tích 0,004, rất khác biệt) **không mô tả cùng một đối tượng vật lý** — thật
     đo macro-gradient mối hàn, tổng hợp (khi bắt trúng) đo đốm nhỏ cục bộ. So sánh trực tiếp 2 tập này là so sánh
     táo với cam, không phải do dòng kim loại sáng/tối khác nhau mà do lỗi chọn vùng.

   → **Kết luận câu 1: đảo ảnh + hiệu chỉnh kiểu cũ CHẠY ĐƯỢC về mặt kỹ thuật (có ngưỡng, có `has_region`), nhưng
   16 đặc trưng hình dạng/biên đo RA SAI ĐỐI TƯỢNG trên đa số mẫu có viền hàn rõ — không dùng được làm ruler tin
   cậy nếu không sửa luật chọn vùng (ví dụ: giới hạn vùng ứng viên trong bán kính quanh tâm mặt nạ khuyết tật thay
   vì lấy vùng lớn nhất toàn ảnh).** Đây không phải nhược điểm riêng của bright-mode — dark-mode cho các loại khác
   cũng có nguy cơ này bất cứ khi nào mảnh ảnh có viền hàn sáng/tối chiếm diện tích lớn, nhưng với metallic thì gần
   như LUÔN xảy ra vì đốm kim loại đặc trưng là NHỎ còn nền ảnh W0003 có viền hàn gần như luôn hiện diện.

   `has_region` (chỉ bật/tắt, không qua `_shape`) vẫn đúng hướng: 1,0/1,0/1,0 trên 3 ô thật (đảo và không đảo như
   nhau), 0,625 trên 40 ảnh tổng hợp (25/40) — khả dụng làm tín hiệu phát hiện thô, nhưng không đủ cho 16 đặc trưng.

## Câu 3 — khuyến nghị

Với 3 mẫu thật: không đủ cho bất kỳ thống kê nào có ý nghĩa (C2ST cần ≥10 hàng mỗi phía, KID/coverage CI cần
nhiều hơn nữa, ít nhất vài chục). 3 mẫu chỉ đủ xem định tính (đúng là có nhìn thấy đốm sáng, visual tham khảo).

**Khuyến nghị kết hợp (b) + (c):**

- **(c) Loại metallic_inclusion khỏi gate định lượng NGAY BÂY GIỜ** — không chỉ vì thiếu mẫu (3 ô), mà vì ruler
  hiện tại (kể cả thử bright-mode) đo sai đối tượng trên phần lớn mẫu có viền hàn, nên dù có đủ mẫu thật thì số đo
  cũng không đáng tin cho đến khi sửa luật chọn vùng.
- **(b) Thu thêm ảnh thật nếu muốn có ruler riêng cho metallic** — ước tính cần tối thiểu ~15–20 ô thật có
  `has_region=1` để đạt ngưỡng tối thiểu C2ST (10/phía, chừa dư cho lọc nhiễu), và ý nghĩa hơn là 40–60 ô để tính
  coverage CI ổn định (khớp quy mô RIAWELC tham chiếu cho porosity/crack trong plan). W0003 chỉ có 3 ô loại này
  trong bộ hiện có — khó thu thêm nếu không có dữ liệu W0003 mới.
- **(a) Không nên thêm bright-mode vào ruler sản xuất ở dạng hiện tại.** Nếu vẫn muốn làm: phải sửa `_shape`
  (hoặc thêm biến thể) để chọn vùng ứng viên gần tâm mặt nạ khuyết tật GT thay vì vùng lớn nhất toàn ảnh — nếu
  không, 16 đặc trưng tiếp tục đo nhầm viền hàn thay vì đốm kim loại, bất kể đảo ảnh hay không.

## Tệp phụ lưu ở scratchpad (không trong repo)

`invert_calib.py`, `inverted-kernel-calibration.json`, `synthetic-metallic-inverted-features.csv`,
`real-metallic-inverted-features.csv`, `clean-inverted-features-sample.csv`, `real-metallic-darkmode-features.csv`,
`mask_W0003_0053_tile_70.png`, `mask_W0003_0054_tile_78.png`, `mask_syn160.png`.

**Status:** DONE
**Summary:** Đảo ảnh + hiệu chỉnh ngưỡng kiểu cũ chạy được kỹ thuật nhưng `_shape` chọn vùng lớn nhất nên đo trúng
viền sáng/tối mối hàn thay vì đốm kim loại nhỏ trên cả 3 ô thật và phần lớn ảnh tổng hợp — ruler cần sửa luật chọn
vùng trước khi dùng được. 3 mẫu thật không đủ thống kê dù sửa ruler. Khuyến nghị loại metallic khỏi gate ngay, thu
thêm mẫu thật nếu cần ruler riêng về sau.
**Concerns:** False-alarm mức đặc trưng (has_region trên nền sạch) cao gấp đôi `achieved_nd_rate` báo cáo ở mọi
loại hiện có (dark lẫn thử đảo), do `region_scores` (area_opening) và `kernel_mask` (label+area filter) không khớp
luật — đáng xem xét lại cho các loại đang dùng dark-mode, ngoài phạm vi câu hỏi này.
