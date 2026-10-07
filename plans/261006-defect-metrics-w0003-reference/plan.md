# Thước đo độ thật mới: 16 đặc trưng khuyết tật, tham chiếu W0003 thật, nhiều độ đo

Trạng thái: PHA 1 XONG 6/10 (bước 1–6). Pha 2 chờ người dùng chốt. Người dùng duyệt 6/10: (1) mục tiêu là khuyết tật giống thật để huấn luyện, chỉ đánh giá
đặc trưng khuyết tật, không đánh giá toàn ảnh; (2) thêm độ đo ngoài C2ST (KID...); (3) W0003 thật làm tham chiếu chính.

## Phát hiện dẫn tới thay đổi (6/10)
- 47 đặc trưng toàn ảnh: C2ST 0,99 cả khi nền sạch chưa có lỗi (kết cấu LBP, nhiễu, độ sáng) → đo miền phim, không đo lỗi.
- 16 đặc trưng khuyết tật (họ hình dạng 12 + biên khuyết tật 4) trên nền sạch: C2ST 0,49–0,51 → đo đúng phần lỗi.
- So với RIAWELC: C2ST 16 đặc trưng LF 0,912, PO 0,919 (6 đặc trưng chỉ 0,700 / 0,819). Lệch chính: PO 1 lỗ so 2,5,
  diện tích nhỏ 3 lần, quá tròn; LF liền một dải so đứt đoạn, tỉ lệ tách được vùng 71% so 96%.
- Tỉ lệ ×2 chưa kiểm chứng: hạt nhiễu RIAWELC to hơn 2,55 lần nhưng lỗ khí thật hai bộ cùng cỡ (21,6 / 23,6 px).
  Bộ tách vùng hiệu chỉnh trên RIAWELC → so xuyên miền lẫn sai số tỉ lệ + bộ dò. → tham chiếu chính W0003 thật, ×1.

## Pha 1: thước đo (không đổi cổng, không đổi sản xuất)
1. `realism/defect_features16.py`: 16 đặc trưng chép nguyên văn từ `Data_Science/analysis/riawelc-features/v2-kernel/
   feature_bank_kernel.py` (_shape, biên), tách vùng bằng kernel v2 với NGƯỠNG THEO THAM CHIẾU. Test: tái lập đúng
   v2-kernel/features.csv trên mẫu ảnh RIAWELC.
2. `realism/reference_w0003.py`: hiệu chỉnh ngưỡng 3 kernel trên nền sạch W0003 (15,5% mảnh sạch có vùng, như RIAWELC);
   tính 16 đặc trưng cho `dataset/4.Welds_W0003_Clear_Defects_278/<lớp>/` (×1) → `realism/reference/w0003-defect-features.csv`
   + `w0003-kernel-calibration.json`. Ánh xạ loại lỗi sinh → thư mục W0003.
3. `realism/defect_metrics.py` (hàm thuần): C2ST (16), KID (MMD² không chệch, kernel đa thức bậc 3, trên đặc trưng chuẩn
   hoá theo tham chiếu, CI bootstrap), density/coverage (Naeem 2020, k=5), tỉ lệ tách được vùng, AUC + trung vị từng đặc trưng.
4. `realism/evaluate.py`: thêm khối `defect_metrics` cho mỗi loại: `w0003` (chính, ×1, khung = cỡ ô W0003) và `riawelc`
   (phụ, ×2 như cũ). Giữ nguyên trường cũ (cổng/lịch sử cũ không vỡ).
5. Trang Độ thật + ô "Đánh giá độ thật" HMI: hiện bảng độ đo mới (chính/phụ), CI, cỡ mẫu.
6. Chạy lại trên các bộ đã có (LF 200, PO 200, CR/LP 150, vòng 7/11) → bảng mốc.

## Pha 2 (sau khi có số pha 1, cần người dùng chốt)
- Mục tiêu (issues.py) viết lại theo thống kê W0003; cổng dùng C2ST16 + KID (+ coverage) thay C2ST 6 đặc trưng.
- Đo độ nhạy lại trên thước mới; sửa bộ sinh mask (rỗ khí nhiều lỗ, to hơn; không ngấu đứt đoạn).

## Rủi ro
- W0003 ít mẫu (3–43/lớp): CI rộng; lớp < 10 mẫu chỉ báo, không dùng cho cổng.
- Ô W0003 278 px có thể không căn giữa lỗi; ảnh sinh cắt quanh tâm mask → chênh vị trí. Kiểm bằng phân bố vị trí vùng.

## Kết quả pha 1 (6/10)
- Code: defect_features16.py, reference_w0003.py (+crop_synthetic_grid), reference_w0003_null.py (cache mức hoàn hảo),
  defect_metrics.py (+rank_normal; null_reference chia đôi tách rời), defect_metrics_density.py (KID CI lấy mẫu con
  không lặp), defect_eval.py (+CLI), evaluate.run ghi `defect_metrics` (ruler w0003-16dac-trung-v1), HMI panel + trang Độ thật.
- Lỗi tự sửa khi nghiệm thu: (1) null_reference so mẫu con với chính tập chứa nó → C2ST hoàn hảo 0,1–0,2; (2) KID z-score
  theo thật bùng nổ (1e6) với mẫu nhỏ + đặc trưng gần hằng → rank_normal gộp; (3) cột "hoàn hảo" trống do đọc sai lớp lồng.
- Test: 13 bộ realism + 12 bộ plant HMI đạt. Nghiệm thu click: LF 200 → C2ST 0,958 (hoàn hảo 0,505), KID 1,618 [0,909; 2,387]
  (−0,121), density 0,336 (1,06), coverage 0,85 (1), tách vùng 0,57 so 0,87.
- Bảng mốc (lưới): xem báo cáo trong phiên; điểm chính: núm sản xuất tốt hơn mặc định ở LF/CR/PO trên mọi độ đo trừ tách
  vùng; tách vùng sản xuất 50–69% so thật 74–94% (lỗi quá mờ); LP: C2ST tốt hơn nhưng KID/coverage xấu hơn.

## Pha 2 (người dùng duyệt nguyên tắc 6/10)
Nguyên tắc: cổng dùng cả 4 độ đo thước mới; tỉ lệ tách được vùng là điều kiện CHẶN (sinh không thấp hơn thật quá 10 điểm %).
- 2a Cổng v2 (subagent): `realism/loop_gate_v2.py`, mục tiêu v2 theo loại, bộ đề thi mặc định 40 ca/loại, trang Độ thật.
- 2b Độ sâu làm tối (main): sinh 40 ca × 4 loại có ảnh trước-làm-tối (núm SX), dò độ sâu bằng CPU replay trên thước mới.
- 2c Bộ sinh mask: rỗ khí nhiều lỗ/to hơn, không ngấu đứt đoạn (đo trước).
- 2d Đo độ nhạy lại trên thước mới (sensitivity_screen dùng hiệu ứng theo 4 độ đo).

## Tiến độ pha 2 (6/10 tối)
- 2a cổng v2 xong (22 test). 2b: độ sâu chung làm hình dạng nứt/không ngấu xấu (vòng 13 loại); người dùng chọn ƯU TIÊN
  HÌNH DẠNG. Thêm núm pore_post_depth (0 = dùng chung); vòng 14 rỗ khí: đạt cả 5 mục tiêu v2; xác nhận 200 ca ghép cặp
  (coverage tốt hơn có ý nghĩa, không độ đo nào xấu; tách vùng 0,50→0,78) → ĐÃ đưa SX (best = vòng 14, ghi chú).
  Kiểm: nứt/không ngấu/không thấu trùng từng điểm ảnh khi đổi núm rỗ khí.
- Sửa lỗi: ghép kết quả loại dùng lại thiếu defect_metrics (all_pass sai); test propose đọc best.json thật.
- Đánh giá 5 loại còn lại (40 ảnh/loại): xỉ nhỏ ~8 lần, gọn; rỗ khí cụm quá đậm; chuỗi quá nhạt; kéo dài nằm ngang (thật ~60°);
  lẫn kim loại: thước mới không đo được (lỗi sáng, bộ dò tìm vùng tối; 3 ảnh thật).
- Người dùng: làm song song bằng subagent. Lead nối dây trước (knobs.py, mask_shaping dispatch EXTRA_SHAPERS,
  generator_hooks TYPE_KNOBS/FEATHER_RADIUS, loop_partial DARKEN_TYPE_KNOBS), mặc định = hành vi cũ, test đạt.
  Nhánh A độ sâu cụm/chuỗi; B xỉ; C rỗ khí kéo dài (góc); D không ngấu (ngắn/mảnh/đứt) + nứt (độ dày). Xếp hàng phiếu GPU.

## Kết quả 4 nhánh song song + đưa SX (7/10)
- A: clustered_post_depth 0,45–0,65 (KID 2,57→0,54; 5 mẫu thật), linear_post_depth 1,0 (tốt hơn mọi độ đo).
- B: xỉ slag_scale 10 / elongation 4 / irregularity 5 (KID tốt hơn có ý nghĩa; tách vùng 0,30→0,68, thật 1,0).
- C: ecav_tilt_max_deg 60 (góc 86°→64°, thật 60°).
- D: nứt crack_widen_px 2 (4 độ đo tốt hơn theo điểm; n chung 18). Không ngấu: 3 mức ngắn/mảnh/đứt đều TỆ HƠN → không đưa.
- Kiểm: porosity/LP/LF trùng từng điểm ảnh khi đổi 9 núm; chỉ 5 loại bị ảnh hưởng. Bảng ảnh trước/sau gửi người dùng.
- Lỗi cổng v2 tìm thấy: loại DÙNG LẠI bị chặn tách vùng (vòng 15 chỉ đổi nứt bị loại oan vì LF/LP) → sửa (loại dùng lại không
  chặn) + test; dọn bộ nhớ hướng vặn và núm thử; xét lại vòng 15 = neutral. best = vòng 15 (đặt tay, ghi chú), ĐÃ đưa SX.
- Test: test-realism-shaping-ecav.py chuyển pytest → unittest; 29 bộ test đạt. Báo cáo nhánh chuyển về reports/ của plan này.
- Vòng sau: độ sâu riêng xỉ + rỗ khí kéo dài (quá nhạt), núm modulation riêng rỗ khí chuỗi, LF mức nhẹ (≥0,85, đứt 1–2),
  xác nhận nứt dày 2 với 80–120 ca, lẫn kim loại cần bộ dò vùng sáng + thêm ảnh thật.

## Vòng 2 nhánh E/F/G + đưa SX (7/10 sáng)
- E: xỉ slag_post_depth 0,65–0,85; rỗ khí kéo dài ecav_post_depth 0,80–1,00; chuỗi linear_post_modulation 0 → ĐÃ đưa SX (đặt tay vào best, ghi chú).
- F: LF mức nhẹ 4 biến thể đều không tốt hơn (m4 KID xấu rõ) → bỏ hướng scale; cần sửa band_width_range/_thin.
  Nứt dày 2 ở 120 ca: KID xấu rõ. Vòng 17 (dày 0) bị cổng chặn tách vùng (kém thật 29 điểm). Dày 1 ở 120 ca: KID tốt hơn rõ so 2,
  so 0 không khác → người dùng duyệt dày 1, đặt tay, ĐÃ đưa SX; xoá crack_widen_px khỏi tuning-memory.
- G: lẫn kim loại thước không đo được (lỗi sáng, 3 ảnh thật) → loại khỏi cổng, chỉ tham khảo.
- Sửa thước: người dùng duyệt điểm 1 (độ đo đúng đối tượng) + 3 (chọn vùng cùng luật thật/sinh); KHÔNG sửa hiệu chỉnh báo động giả.
  Subagent làm sau cờ phiên bản thước, chưa bật.
- Thước theo loại (7/10 trưa): v2 (bỏ vùng dài chạm hai mép) cho mọi loại trừ nứt/không thấu (giữ v1); lẫn kim loại reference_only;
  độ đo đúng đối tượng (chỉ báo). RULER_SCHEME_ID đổi → vòng sinh lại hết + đặt mốc mới. Vòng 18 = mốc mới (240 ảnh, núm SX).
  Mốc: PO C2ST 0,52 (hoàn hảo 0,47) KID 0,02; LF C2ST 0,89 KID 0,74; CR tách vùng 0,45/0,74, đúng đối tượng 38%; LP KID 2,10 cov 0,38.

## Vòng 3 (7/10 chiều): nứt / không thấu / không ngấu
- Nứt: 22/40 ca sinh quá nhạt (tương phản ~1× nhiễu); nứt chưa có độ sâu riêng. Núm đề xuất crack_post_depth 0,70–0,90 (CPU replay:
  tách vùng 0,43→0,83, KID/coverage tốt hơn, C2ST xấu hơn). CHƯA nối dây, chờ thước v3.
- Không thấu: tham chiếu thật nhiễm, 12/16 LP thật + 12/32 CR thật đo nhầm dải sáng sát mép trên/dưới ô → đề xuất núm LP vô hiệu.
  Đã nối dây lop_length_scale, lop_post_depth_* (mặc định = cũ). Người dùng duyệt: thước v3 loại đường sát mép trên/dưới cho CR/LP.
- Không ngấu: núm lof_band_width_scale (co tại sinh) 0,8/0,6/0,4 đều bị chặn tách vùng (tụt thêm 12,5–20 điểm). Đóng hướng co bề rộng.
- Thước v3 (loại đường sát mép trên/dưới) cho CR/LP; LP chỉ tham khảo (6/19 ảnh thật). Vòng 19 = mốc mới.
- Vòng 20 nứt crack_post_depth 0,70–0,90: neutral; cả bộ tách vùng 0,38→0,70 (thật 0,67), đúng đối tượng 28→55%, cov 0,59→0,76,
  C2ST/KID nhích xấu không rõ. Người dùng duyệt → ĐÃ đưa SX. Không thấu theo mắt: độ sâu 0,25–0,35 + dài 1,3 → ĐÃ đưa SX.
  best → vòng 20 (đặt tay, ghi chú; số LP vòng 20 là trước khi đổi núm). Không ngấu tạm dừng.
