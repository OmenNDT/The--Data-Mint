# Nhánh C: hình dạng rỗ khí kéo dài (elongated_cavity) so W0003 thật

Plan: `plans/261006-defect-metrics-w0003-reference/plan.md`. Mục tiêu: trục rỗ khí kéo dài sinh ra
xiên giống thật (vung_huong), ưu tiên hình dạng trước, độ thấy sau.

## Code

- `realism/mask_shaping_ecav.py`: `shape(m, rng, knobs)`. Mỗi vùng liên thông xoay độc lập quanh tâm
  chính nó, góc rút đều trong `[-ecav_tilt_max_deg, ecav_tilt_max_deg]`. Núm = 0 trả nguyên mask
  (hành vi cũ, test xác nhận). Dời nguyên vùng (không cắt) nếu xoay làm chạm viền khung ảnh.
  Dùng lại `_affine`/`_rot` từ `mask_shaping.py` (không sửa tệp đó).
- `tests/test-realism-shaping-ecav.py`: 10 test (núm 0 không đổi, mask rỗng không đổi, núm thiếu mặc
  định 0, giữ diện tích + trong khung ảnh ở 4 mức góc, trung bình bbox dọc tăng khi xoay, xác định
  theo seed, nhiều vùng xoay độc lập). Chạy `python3 -m pytest tests/test-realism-shaping-ecav.py -q`
  (không dùng `.venv` vì thiếu pytest ở đó; `/home/sontn/.local/bin/pytest` có): **10 passed**.
- Kiểm `FEATHER_RADIUS["elongated_cavity"]=12`: khớp đúng `feather_mask(mask, blur_radius=12)` trong
  `mask_generator/elongated-cavity-mask-generator.py::generate()`. Không cần sửa.

## Ý nghĩa núm (quy đổi vung_huong)

`vung_huong = abs(orientation độ)` (skimage regionprops, đo từ trục ĐỨNG). Bộ sinh gốc vẽ trục gần
nằm NGANG nên vung_huong ≈ 90° (đo được 85,9°); thật trung bình 60,4° (ảnh thật đa số xiên gần đứng
hơn, xem ảnh mẫu bên dưới). Xoay mask khỏi phương ngang trung bình θ thì vung_huong mới ≈ 90 − θ.
Rút góc đều trong `[-max, max]` thì trung bình |góc| = max/2, nên núm = 60 → trung bình xoay 30° →
vung_huong kỳ vọng ≈ 60, đúng mục tiêu. Khớp thực đo (xem bảng dưới): núm 60 cho vung_huong trung vị
sinh 63,9° (thật 60,4°).

## Kết quả đo (40 ca cố định, seed+nền giống hệt núm SX; thước 16 đặc trưng W0003)

Tham chiếu W0003 chỉ 9 hàng tách được vùng (`small_reference=True`) → C2ST không tính được ở MỌI mức
(kể cả nền SX, cần ≥10 mỗi bên) — không dùng C2ST để so núm lần này, chỉ KID/density/coverage/AUC
từng đặc trưng + tỉ lệ tách vùng.

| Núm | vung_huong sinh (thật 60,4) | AUC vung_huong (0,5=giống) | bien_tuongphan sinh (thật 3,38) | tách vùng sinh | KID | density | coverage |
|---|---|---|---|---|---|---|---|
| SX (0, nền ngang) | 85,9° | 0,77 | 1,89 | 0,525 (21/40) | 0,698 [0,03;1,77] | 0,90 | 1,00 |
| 30 | 76,5° | 0,63 | 2,32 | 0,45 (18/40) | 0,440 | 1,12 | 1,00 |
| 45 | 71,1° | 0,60 | 2,24 | 0,45 (18/40) | 0,527 | 1,04 | 1,00 |
| 60 | **63,9°** | **0,58** | 2,29 | 0,45 (18/40) | 0,519 | 1,04 | 1,00 |

Thật: detection_rate_real = 0,90 (9/10 ô W0003 tách được vùng).

Ghép cặp (paired, 18 ca chung với nền SX, bootstrap 200, n nhỏ nên CI rộng): KID/density/coverage ở
cả 3 mức tilt đều "same" so nền SX (CI phí tổn phủ 0) — xoay không làm các độ đo này xấu đi có ý
nghĩa thống kê, dù điểm trung tâm dao động nhẹ.

vung_thuon (quá thuôn, thật 2,76 so SX 4,22, AUC 0,69 ở nền ngang): ở cả 3 mức tilt đều RỚT khỏi top-6
đặc trưng lệch nhất (tác dụng phụ có lợi, có thể do nội suy láng giềng gần nhất khi xoay làm mép hơi
"vuông" lại, giảm tỉ lệ trục đo được). Không cần núm riêng cho elongation ở bước này.

## Ảnh kiểm bằng mắt

- Mask SX (gần ngang) so mask tilt60 (xiên rõ) cùng seed: xem
  `output/realism-loop/remaining-types-prod/elongated_cavity/elongated_cavity_000040_mask.png` so
  `output/realism-loop/ecav-tilt-variants/tilt60/elongated_cavity/elongated_cavity_000000_mask.png`.
  Xoay đúng như kỳ vọng, vùng vẫn trong khung ảnh.
- Ảnh thật `dataset/4.Welds_W0003_Clear_Defects_278/Elongated_Cavity/W0003_0041_tile_37.png`: vệt gần
  đứng, xác nhận hướng mục tiêu đúng (không phải chéo ngẫu nhiên, mà lệch hẳn về phía đứng so bộ sinh
  cũ).
- 3 ca MẤT tách vùng ở MỌI mức tilt (elongated_cavity-011/032/034, giống hệt nhau cả 3 mức, không
  tăng theo góc): cả 3 có mask gốc đặt sát mép TRÊN khung (cy gần cận dưới `max_w+5` của bộ sinh gốc).
  Xoay đẩy vùng sát viền hơn (`FRAME_MARGIN=2`), vào vùng rìa ảnh vốn đã có vignette/nhiễu nền của
  patch W0003 → kernel ngưỡng không tách được vùng nữa dù mask vẫn vẽ đúng. Đây là tương tác giữa vị
  trí đặt mặc định của bộ sinh gốc (không phải lỗi mô-đun xoay) và ngưỡng tách vùng gần biên ảnh.

## Khuyến nghị

1. **Chốt `ecav_tilt_max_deg = 60`** cho sản xuất (lead bấm "Đưa vào sản xuất"): hình dạng gần thật
   nhất (vung_huong trung vị 63,9° so thật 60,4°; AUC 0,58 gần 0,5), 30/45/60 không khác nhau có ý
   nghĩa ở KID/density/coverage (n ghép cặp nhỏ, 18 ca) nên chọn mức khớp trung vị tốt nhất.
2. **Cần thêm núm độ sâu làm tối riêng elongated_cavity** (như `pore_post_depth_min/max` đã làm cho rỗ
   khí): bien_tuongphan vẫn thấp hơn thật dù xoay giúp nhích lên chút (1,89→2,2-2,3 so thật 3,38,
   thiếu khoảng 1,5 lần độ tương phản). Đề nghị thử `ecav_post_depth_min≈0,75–0,85`,
   `ecav_post_depth_max≈0,90–1,00` (tương tự khoảng rỗ khí 0,80–1,00 đã xác nhận hiệu quả ở pha trước),
   đo lại bien_tuongphan sau khi thêm.
3. **Tỉ lệ tách vùng thấp (0,45 so thật 0,90) nằm ngoài phạm vi núm này**: xoay làm mất thêm đúng 3/40
   ca (0,525→0,45) do vị trí sát mép trên, KHÔNG proportional theo góc (30/45/60 giống hệt nhau) → ưu
   tiên theo đúng thứ tự người dùng duyệt (hình dạng trước), chấp nhận phần mất này ở bước này. Nếu
   sau này cần kéo detection gần thật hơn 10 điểm %, gợi ý lead xem lại khoảng đặt `cy` trong
   `elongated-cavity-mask-generator.py` (tăng biên cách mép trên/dưới) — KHÔNG thuộc phạm vi tệp được
   giao, chỉ ghi nhận.
4. Không cần núm aspect/elongation riêng ở bước này: vung_thuon đã tự rớt khỏi top-6 lệch nhất nhờ tác
   dụng phụ của phép xoay (nội suy láng giềng gần nhất).

## Dữ liệu chạy

- Script: `scratchpad/ecav_tilt_variants.py` (tạm, không trong repo). Núm thử = núm SẢN XUẤT hiện tại
  (`knobs.resolve("production")`) + override `ecav_tilt_max_deg`; KHÔNG ghi `knobs.json` /
  `candidate-knobs.json`.
- 40 ca cố định lấy từ `output/realism-loop/remaining-types-prod/fixed-jobs.json` (lọc
  `defect_type=="elongated_cavity"`, đúng seed + nền nền SX đã dùng).
- Output: `output/realism-loop/ecav-tilt-variants/tilt{30,45,60}/`.
- GPU lease: `acquire("ecav-tilt-variants", ...)`, retry 30s khi bận (đợi ~14 phút do nhánh khác giữ
  GPU), release trong finally. 3×40=120 ảnh.
