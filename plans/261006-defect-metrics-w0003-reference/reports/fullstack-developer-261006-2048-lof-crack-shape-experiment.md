# Nhánh D: hình dạng lack_of_fusion + độ dày crack (thước mới W0003)

## Việc đã làm

**Code (file ownership)**
- `realism/mask_shaping_lof.py`: cài `shape()` thay bản khung rỗng. Ba bước theo thứ tự núm
  `lof_length_scale` → `lof_width_scale` → `lof_gap_max`: rút ngắn (giữ một đoạn liên tục ngẫu
  nhiên theo chiều cột), thu mỏng (ép chiều đứng quanh tâm khối bằng `_affine` có sẵn trong
  `mask_shaping.py`), cắt khoảng đứt (giống `_lop`, cửa sổ 10 đến 35 điểm ảnh). Mặc định
  (1, 1, 0) trả nguyên mask, đúng yêu cầu không đổi hành vi cũ.
- `tests/test-realism-shaping-lof.py`: 12 ca, gồm mặc định bất biến, rút ngắn giảm nhịp cột
  đúng tỉ lệ, thu mỏng giảm diện tích giữ nhịp cột, cắt khoảng đứt tăng số vùng tách rời (đo
  bằng `ndi.label`), mask trống giữ trống, tất định theo seed. Chạy
  `.venv/bin/python3 tests/test-realism-shaping-lof.py -v` → 12/12 qua.

**Kiểm chứng FEATHER_RADIUS["lack_of_fusion"]=2 (lead yêu cầu xác nhận)**
- `mask_generator/lack-of-fusion-mask-generator.py` dòng 116: bộ sinh LF tự làm mềm mép bằng
  `blur_radius=2`. Khớp đúng `FEATHER_RADIUS["lack_of_fusion"]=2` trong `generator_hooks.py`.
  Số 40 ở dòng 179 cùng tệp là của `LackOfPenetrationMaskGenerator` (LoP), không phải LoF. Không
  cần sửa gì ở `generator_hooks.py`.

## Thí nghiệm (40 ca/biến thể, bộ đề thi cố định exam_set, núm sản xuất hiện tại + override)

Mốc so sánh: `output/realism-loop/depth-base/prod/{lack_of_fusion,crack}` (đã xác nhận cùng 40 ca
exam_set, cùng núm sản xuất hiện tại: `crack_widen_px=0`, `lof_*` ở mặc định tức không tạo hình)
→ dùng thẳng làm mốc, không sinh lại.

Biến thể sinh tại `output/realism-loop/shape-experiment-lof-crack/{tag}/`.

### Không ngấu (lack_of_fusion), vung_tile thật 0,006, bien_tuongphan thật 1,47, detection thật 0,87

| Biến thể | length/width/gap | detection sinh | C2ST | KID | density | coverage |
|---|---|---|---|---|---|---|
| mốc SX | 1 / 1 / 0 | 0,625 | 0,786 | 1,029 | 0,416 | 0,85 |
| lf-a | 0,6 / 0,7 / 2 | 0,400 | 0,806 | 1,780 | 0,275 | 0,50 |
| lf-b | 0,5 / 0,5 / 3 | 0,375 | 0,843 | 2,298 | 0,200 | 0,40 |
| lf-c | 0,7 / 0,6 / 1 | 0,425 | 0,871 | 1,566 | 0,365 | 0,55 |

Cả ba biến thể XẤU ĐI trên MỌI độ đo so mốc sản xuất: detection tụt 20 đến 25 điểm % (khoảng cách
với thật từ 24,5 điểm % lên 44 đến 50 điểm %, vượt xa ngưỡng chặn 10 điểm %), C2ST/KID/coverage
đều lệch xa thật hơn. Ghép cặp trên tập ca chung (n = 14 đến 16, do nhiều ca mất vùng ở cả hai
phía) cho khoảng tin cậy phủ 0 ở mọi độ đo (không đủ mẫu để khẳng định có ý nghĩa thống kê), nhưng
hướng điểm cũng nhất quán xấu đi.

Xem ảnh: `lack_of_fusion_000120.png` (mốc, cùng ca) so `lack_of_fusion_000000.png` (lf-c) cùng cảnh,
cùng seed. Về hình dạng: lf-c tách đúng thành hai đoạn ngắn như mong muốn (đúng hướng "đứt đoạn"
của thật), nhưng dải đã mỏng và ngắn đến mức bộ dò vùng kernel (defect_eval) không nhận ra vùng ở
nhiều ca hơn hẳn mốc (dải quá mảnh, có thể cả do ControlNot bám mask nhỏ kém hơn khi SD vẽ). Tức
là hướng tạo hình đúng (ngắn hơn, mỏng hơn, đứt đoạn), nhưng độ co hiện tại (0,5 đến 0,7 chiều dài,
0,5 đến 0,7 bề dày) đi quá xa, làm mất khả năng phát hiện nhanh hơn làm giống hình dạng.

**Khuyến nghị LF:** KHÔNG đưa biến thể nào trong ba biến thể trên vào sản xuất. Vòng sau nên thử
mức nhẹ hơn nhiều (ví dụ length_scale ≥ 0,85, width_scale ≥ 0,85, chỉ dùng gap_max = 1 đến 2 để
tạo đứt đoạn mà không co diện tích mạnh), hoặc tăng band_width_range gốc của bộ sinh (ngoài phạm vi
sở hữu tệp của nhánh này) để bù lại phần diện tích mất do co. Cần đo lại cả bốn độ đo mỗi lần chỉnh.

### Crack, detection thật 0,744

| Biến thể | crack_widen_px | detection sinh | C2ST | KID | density | coverage |
|---|---|---|---|---|---|---|
| mốc SX | 0 | 0,450 | 0,896 | 1,241 | 0,789 | 0,594 |
| cr-1 | 1 | 0,450 | 0,863 | 1,226 | 0,756 | 0,594 |
| cr-2 | 2 | 0,500 | 0,820 | 0,948 | 0,870 | 0,625 |

cr-2 (làm dày tối đa 2 điểm ảnh) tốt hơn mốc sản xuất trên CẢ BỐN độ đo cùng lúc thu hẹp khoảng
cách phát hiện (0,744 − 0,500 = 24,4 điểm %, so mốc 29,4 điểm %). Ghép cặp (n = 18 ca chung): C2ST
delta −0,043 CI [−0,095, +0,017], KID delta −0,260 CI [−0,469, +0,024], cả hai gần ngưỡng có ý
nghĩa (cận trên CI sát 0) dù danh nghĩa "same" với n nhỏ; density/coverage không đổi hoặc nhỉnh hơn.
cr-1 (widen=1) không rõ lợi ích, gần như trùng mốc.

Xem ảnh: `crack_000000.png` mốc so cr-2 cùng ca, thấy vệt nứt góc dưới phải dày hơn rõ, hình dạng
vẫn giữ đường zigzag mảnh đặc trưng của crack (không bị nhầm sang không ngấu).

**Khuyến nghị crack:** đưa `crack_widen_px = 2` vào ứng viên sản xuất tiếp theo (không phải nhánh
này ghi, nhánh D không sở hữu tệp knobs/HMI). Xác nhận giả thuyết ban đầu: bề dày là đòn bẩy đúng,
không phải độ sâu làm tối (độ tương phản biên đã khớp thật ở mức sản xuất).

## Việc chưa làm / câu hỏi còn mở

- Chưa thử tổ hợp LF nhẹ hơn (do ngân sách GPU dùng chung với 4 đến 5 nhánh song song khác suốt
  phiên, mỗi job 40 ảnh mất 15 đến 40 phút chờ thuê GPU). Đề xuất vòng sau.
- `cr-2` nên chạy lại với n lớn hơn (ví dụ 80 đến 120 ca) để khoảng tin cậy ghép cặp thu hẹp đủ
  kết luận "tốt hơn" thay vì "same" danh nghĩa.
- Một lần chạy đầu bị kill giữa chừng (tiến trình chính nhận SIGTERM sau khi 4/5 batch đã xong,
  lý do không rõ, có thể do giới hạn thời lượng phiên nền); đã tự phục hồi qua checkpoint
  (`realism/state/checkpoints/cr-2`) chạy lại đúng batch còn thiếu, không ảnh hưởng số liệu.

## Tệp liên quan
- Code: `pipeline/realism/mask_shaping_lof.py`, `pipeline/tests/test-realism-shaping-lof.py`
- Dữ liệu sinh: `output/realism-loop/shape-experiment-lof-crack/{lf-a,lf-b,lf-c,cr-1,cr-2}/`
- Mốc dùng lại: `output/realism-loop/depth-base/prod/{lack_of_fusion,crack}/`
- Kết quả thô: scratchpad `lof_crack_result.json`, `baseline_eval.json`, `paired_result.json`

**Status:** DONE_WITH_CONCERNS
**Summary:** LF shaping đúng hướng hình dạng (đứt đoạn) nhưng co quá mạnh làm sập detection, không
nên lên sản xuất; crack_widen_px=2 cải thiện cả bốn độ đo kiêm detection, nên nhận làm ứng viên.
**Concerns:** mẫu ghép cặp còn nhỏ (14 đến 18 ca) nên CI chưa khẳng định ý nghĩa thống kê cho cr-2
dù điểm số nhất quán; chưa thử mức LF nhẹ hơn do ngân sách GPU.
