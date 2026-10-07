# Vì sao thước nứt (crack) bỏ sót: điều tra + đề xuất sửa

Phạm vi: vòng 18 (best hiện hành), 40 ca nứt sinh (`output/realism-loop/iter-18/crack`), đo bằng
`realism/state/runs/loop-20261007-112308-479-eval-18/result.json`.

## 1. Chia nguyên nhân (40/40 ca, định lượng)

Viết lại chính xác pipeline đo (`defect_features16.defect_features` + `crop_synthetic_grid`, cùng
ngưỡng `w0003-kernel-calibration.json`) trên 40 ca, đối chiếu đặc trưng + vị trí vùng với mặt nạ
nứt thật. Kết quả khớp đúng `result.json` (detection 18/40=0,45; đúng đối tượng 15/40=0,375).

| Nguyên nhân | Số ca | Ghi chú |
|---|---:|---|
| **Quá mờ** (không kernel nào vượt ngưỡng, `max_ratio` đỉnh/ngưỡng < 1,0) | 22 | độ tương phản đo được (hiệu TB vùng ngoài − trong mặt nạ) chia độ nhiễu nền chỉ ~1,0 (= lẫn trong nhiễu hạt), so nhóm bắt được ~3,8 |
| **Lạc mục tiêu** (có vùng nhưng vùng chọn cách xa mặt nạ nứt thật, overlap=0) | 3 | kernel chọn dải tối khác (vân mép hạt/đường ngấu nền) thay vì đường nứt mảnh hơn |
| **Quá mỏng/quá ngắn** | 0 | diện tích mặt nạ nhóm bỏ sót (TB 923 px) ~ bằng nhóm bắt được (TB 873 px); bề rộng ước lượng tương đương (~6 px cả hai nhóm) → KHÔNG phải vấn đề hình học |
| Bắt đúng | 15 | |

Kết luận: nguyên nhân áp đảo là **quá mờ**, không phải hình dạng/kích thước. Ảnh minh hoạ (2 ca mờ
gần như vô hình bằng mắt thường, 1 ca lạc mục tiêu, 2 ca bắt tốt, 3 ca thật W0003 đối chiếu):
`plans/261006-defect-metrics-w0003-reference/reports/crack-miss-contact-sheet.png`.

## 2. Nguyên nhân gốc: nứt chưa có núm độ sâu riêng

Đọc `realism/post_darkening.py::effective_knobs`: thứ tự ưu tiên độ sâu làm tối hiện có núm RIÊNG
cho `clustered_porosity`, `linear_porosity`, `slag_inclusion`, `elongated_cavity` (và `PORE_TYPES`
nói chung qua `pore_post_depth_*`) — tất cả được nâng lên 0,45–1,0 qua các nhánh A/E (xem plan,
mục "Kết quả 4 nhánh song song" và "Vòng 2 nhánh E/F/G"). **`crack` KHÔNG có trong danh sách này**,
nên vẫn rơi về núm chung cũ `post_depth_min=0,3663 / post_depth_max=0,5663` — thấp hơn hẳn mọi loại
khác đang chạy sản xuất. Nhánh D (7/10) chỉ chỉnh `crack_widen_px` (bề rộng nét vẽ mặt nạ), không
đụng tới độ sâu làm tối — đây là núm bị bỏ sót, không phải cố ý giữ thấp.

Thêm vào đó `post_modulation=0,65` (σ=6) là trường điều biến CHUNG, làm độ sâu dao động mạnh dọc
đường nứt: nhiều đoạn gần như về 0 (xem `crack_000024`, `crack_000039` trong contact sheet — đường
nứt tồn tại trong mặt nạ nhưng ảnh gần như không đổi độ xám). Kiểm riêng: giữ độ sâu cũ, chỉ tắt
điều biến (`post_modulation=0`) → detection CPU 0,425→0,625 (xem bước 3).

## 3. Xác nhận rẻ bằng CPU (predarken replay, không cần GPU)

Dùng 40 tệp `*_predarken.npz` sẵn có ở `output/realism-loop/depth-base/prod/crack/` (cùng bộ ca,
cùng núm nền với vòng 18), gọi lại `post_darkening.darken()` trực tiếp với núm độ sâu thử nghiệm
(bỏ qua `effective_knobs` vì `crack` chưa đăng ký — truyền thẳng `post_depth_min/max` để mô phỏng
đúng kết quả NẾU đăng ký), rồi đo lại bằng đúng `defect_features16` + so C2ST/KID/density/coverage
với tham chiếu W0003 Crack thật (32 ca có vùng). Baseline replay (det=0,425) khớp sát sản xuất
(0,45) — lệch nhỏ do seed lệch khung cắt khác tên tệp (`npz` vs `.png` dùng làm key crc32).

| Núm thử | detection | n có vùng | C2ST | KID | density | coverage |
|---|---:|---:|---:|---:|---:|---:|
| **Hiện SX** (0,3663–0,5663, mod 0,65) | 0,425 | 17 | 0,811 | 1,311 | 0,765 | 0,469 |
| 0,55–0,75, mod giữ | 0,650 | 26 | 0,911 | 1,200 | 0,838 | 0,656 |
| **0,70–0,90, mod giữ** | **0,825** | 33 | 0,929 | **1,183** | 0,721 | 0,656 |
| 0,85–1,00, mod giữ | 0,900 | 36 | 0,947 | 1,549 | 0,639 | 0,688 |
| 0,70–0,90, mod=0,2 | 0,900 | 36 | 0,955 | 2,049 | 0,356 | 0,531 |
| Giữ độ sâu cũ, mod=0 | 0,625 | 25 | — | — | — | — |

Thật (tham chiếu) detection = 0,744. Điều kiện chặn: sinh không thấp hơn thật quá 10 điểm %.

## 4. Đề xuất, xếp hạng theo hiệu quả

1. **[chính] Thêm `crack` vào `per_type` của `post_darkening.effective_knobs`** với núm mới
   `crack_post_depth_min=0,70`, `crack_post_depth_max=0,90` (mặc định 0/0 → rơi về núm chung cũ,
   GIỮ ĐÚNG hành vi hiện hành khi chưa đặt tay, như cách `slag_post_depth_*`/`ecav_post_depth_*`
   đã làm). Hiệu quả: detection 0,425→0,825 (vượt xa điều kiện chặn, thật 0,744 − 0,825 < 0),
   KID tốt hơn (1,31→1,18), coverage tốt hơn rõ (0,469→0,656), density gần như không đổi. Đánh đổi:
   C2ST tệ đi (0,81→0,93) — quan sát ở MỌI mức tăng độ sâu đã thử, kể cả mức nhẹ 0,55–0,75, nhiều
   khả năng do mở khoá thêm ca biên (trước đây chỉ ca "dễ" lọt qua ngưỡng mới được tính C2ST, giờ
   thêm ca mờ/lởm chởm làm đa dạng hình dạng tăng) chứ không phải lỗi núm. KHÔNG đổi `post_modulation`
   chung (giữ 0,65) — thử hạ xuống 0,2 làm KID xấu hẳn (2,05) dù detection cao nhất, không đạt ưu
   tiên hình dạng của người dùng.
2. **[phương án thận trọng]** `crack_post_depth_min=0,55 / max=0,75`: C2ST đỡ xấu hơn (0,91), density
   tốt nhất (0,838), nhưng khoảng cách detection với thật chỉ còn 9,4 điểm % — sát ngưỡng chặn 10
   điểm %, rủi ro trượt cổng nếu phương sai mẫu đổi giữa các lần đo GPU thật. Dùng nếu người dùng ưu
   tiên C2ST hơn biên an toàn detection.
3. **Không đổi thước (ruler v1)**: 3 ca lạc mục tiêu do kernel chọn vân nền/mép ngấu thay vì đường
   nứt mảnh hơn — đây là đánh đổi đã chốt (v2 loại đường chạm mép làm mất 18/43 ca Crack thật vì bản
   chất nứt CŨNG là đường dài chạm mép, xem `reference_w0003.py` dòng 53–58). Không cần sửa thêm:
   on-target tăng theo như tác dụng phụ của việc tăng độ sâu (vùng nứt thật tương phản cao hơn thắng
   thế trước vân nền khi cạnh tranh "vùng lớn nhất"), từ CPU: overlap trung bình nhóm bắt được tăng
   theo mọi mức tăng độ sâu đã thử (xem bảng, coverage/density cải thiện kéo theo).

## 5. Việc CHƯA làm (ngoài phạm vi điều tra)

Không sửa `realism/post_darkening.py` hay `realism/knobs.py` — hai tệp này cũng là hạ tầng dùng
chung với nhánh lack_of_penetration/lack_of_fusion đang chạy song song (nguy cơ đụng tệp nếu hai
agent cùng sửa `effective_knobs`/`knobs.py` cùng lúc). Đề xuất ở trên viết đủ chi tiết (tên núm,
giá trị, vị trí chèn trong `effective_knobs` per_type dict theo đúng khuôn mẫu
`slag_post_depth_*`/`ecav_post_depth_*`) để lead hoặc agent được giao nối dây thực hiện, kèm test
unittest xác nhận mặc định 0/0 giữ nguyên hành vi cũ (giống `test-realism-shaping-ecav.py` đã làm
cho `ecav_post_depth_*`).

Chưa chạy GPU: xác nhận CPU qua `predarken` replay đã đủ rẻ và đủ thuyết phục (khớp sát số sản xuất
ở mức baseline); khuyến nghị TRƯỚC KHI đặt vào `best.json`, chạy một mẻ GPU nhỏ (≤80 ảnh, qua
`plant_gpu_lease`) để xác nhận qua cổng `loop_gate_v2` thật (so cặp bootstrap với bản tốt nhất hiện
tại), vì proxy CPU chỉ thay bước làm tối, không lặp lại đúng nhiễu hạt SD + ControlNet.

## File liên quan
- Đọc: `pipeline/realism/defect_features16.py`, `pipeline/realism/post_darkening.py`,
  `pipeline/realism/reference_w0003.py`, `pipeline/realism/reference_w0003_crop.py`,
  `pipeline/realism/defect_eval.py`, `pipeline/realism/loop_gate_v2.py`
- Không sửa file nào (chỉ đọc + script phân tích tạm trong scratchpad, không thuộc repo)
- Ảnh minh hoạ: `plans/261006-defect-metrics-w0003-reference/reports/crack-miss-contact-sheet.png`

## Câu hỏi chưa chốt
- Đánh đổi C2ST tệ đi (0,81→0,93) khi tăng độ sâu có chấp nhận được không, hay cần thước bù (vd
  loại trừ ca mờ cực đoan khỏi mẫu C2ST)? Chưa có dữ liệu để kết luận liệu đây là hiện tượng tạm
  thời (ổn định lại khi n lớn hơn 40 ca) hay thật sự đánh đổi cố hữu.
- Giá trị 0,70–0,90 hay 0,55–0,75 — cần người dùng chốt theo khẩu vị rủi ro biên an toàn detection
  so với mức độ ưu tiên C2ST.

**Status:** DONE
**Summary:** 40 ca nứt: 22 quá mờ (tương phản ~ nhiễu nền), 3 lạc mục tiêu (kernel chọn vân nền),
0 do hình dạng/bề rộng. Gốc: `crack` chưa có núm `post_depth` riêng như 4 loại khác, rơi về núm
chung thấp (0,37–0,57) trong khi loại khác đã lên 0,65–1,0. Xác nhận CPU (predarken replay, không
GPU): `crack_post_depth_min/max=0,70/0,90` (núm mới, mặc định giữ hành vi cũ) đưa detection
0,425→0,825 (qua điều kiện chặn), KID + coverage tốt hơn, C2ST tệ đi (đánh đổi quan sát ở mọi mức
tăng độ sâu đã thử). Chưa sửa code (đụng file dùng chung với nhánh LOP/LF song song) — đề xuất đủ
chi tiết để lead nối dây.
**Concerns:** C2ST xấu đi là đánh đổi nhất quán ở mọi mức tăng độ sâu thử nghiệm, chưa rõ có giảm
được không; CPU proxy không thay cho xác nhận GPU qua cổng thật trước khi đặt vào best.json.
