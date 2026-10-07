# Bước 4: đo độ nhạy từng núm, đề xuất núm theo dữ liệu

Trạng thái: XONG 3/10 (vòng 7 vào sản xuất). Người dùng duyệt 2/10: làm chậm, test kỹ. Plan cha: `plans/261002-1006-realism-loop-safety-paired-gate/`.

## Vấn đề
Luật vặn hiện tại (`issues._rule`) đoán hướng và cỡ bước bằng tay. Chưa ai đo núm nào thật sự đẩy mục tiêu nào,
đẩy bao nhiêu, và kéo hỏng mục tiêu nào khác. Ví dụ: rỗ khí dao động biên tụt 0,373→0,329 sau vòng 3, không biết do núm nào.

## Cách làm
- Điểm gốc = núm sản xuất hiện tại. Lệch từng NHÓM núm một bước (`realism/sensitivity_groups.py`, 13 nhóm, 19 biến thể),
  sinh trên bộ đề thi cố định 20 ca/loại, ghép cặp với lượt gốc → hiệu ứng từng mục tiêu + CI bootstrap + C2ST.
- Nhóm "replay" (độ sâu, độ thay đổi, cỡ vệt, độ nhoè): chỉ là hậu xử lý → lượt gốc lưu ảnh trước-làm-tối (.npz),
  tính lại bằng CPU. Nhóm "generate" (ControlNet, 8 núm tạo hình mặt nạ): sinh lại bằng GPU, chỉ loại bị ảnh hưởng.
- GPU: gốc 80 + ControlNet ±160 + loại riêng 180 = 420 ảnh ≈ 40 phút. Replay: 8 biến thể × 80 ảnh, CPU, vài phút.

## Pha 1: lưu ảnh trước-làm-tối + replay (subagent A)
- `batch-production-main.py` (CRLF): env `REALISM_SAVE_PREDARKEN=1` → trong `apply_dark_defect_convention`, ngay trước
  bước 2, lưu `<tên ảnh>_predarken.npz` (img float32 sau bước 1, bg, mask_arr, DARKEN_STRENGTH, key = tên ảnh).
  Không có env → không đổi gì. metallic_inclusion không làm tối → không lưu.
- `realism/predarken_replay.py`: `replay(src_dir, dst_dir, knobs, types)` → ảnh = clip(darken(...)) uint8, chép mask +
  json + fixed-jobs.json + PV núm. evaluate.run đo được thư mục đích như thư mục sinh thường.
- Test bắt buộc: replay với núm gốc ra ảnh TRÙNG từng điểm ảnh với ảnh lượt gốc đã sinh.

## Pha 2: chạy đo (subagent A)
- `python -m realism.sensitivity_screen --run-id sens-<ts> [--n-per-type 20] [--groups a,b] [--pilot]`.
- Xin phiếu GPU (owner `realism-sensitivity:<run>`) suốt phiên; tôn trọng `state/stop.flag`; RunLog tại
  `realism/state/runs/<run_id>/` (stage/item/variant/done/error).
- Thư mục ảnh: `output/realism-sensitivity/<run_id>/{base,<variant_id>}/`.
- Kết quả: `runs/<run_id>/sensitivity.json` + bản sao mới nhất `realism/state/sensitivity.json` (khi chạy đủ, không pilot).

### Lược đồ sensitivity.json
```
{"run_id", "finished", "n_per_type", "base_knobs": {tên: giá trị}, "base_eval_run",
 "variants": [{"id": "post_depth+", "group", "sign", "mode": "replay|generate", "types": [...],
               "knobs": {tên: giá trị đầy đủ}, "changed": {tên: [gốc, mới]}, "eval_run"}],
 "effects": {"<variant_id>": {"targets": {"<nhãn mục tiêu>": <mục của paired_stats.compare_paired>},
                              "c2st": {"<pair>": {"base", "new", "delta"}}}}}
```

## Pha 3: đề xuất theo dữ liệu (subagent B)
- `realism/sensitivity_propose.py`: `propose(result, current, sens)` → (núm mới, lý do, mode).
  Dùng khi `sens.base_knobs` khớp `current`; khác → "độ nhạy đã cũ", trả về luật cũ (`issues.propose`).
  Mỗi mục tiêu trượt: chọn biến thể có hiệu ứng CÓ Ý NGHĨA đúng chiều; bước λ = khoảng thiếu / hiệu ứng, kẹp [0,5; 2]
  (không ngoại suy quá 2 lần khoảng đã đo); núm mới = gốc + λ × (biến thể − gốc). Dự báo tuyến tính cộng dồn mọi mục tiêu;
  bỏ ứng viên làm một mục tiêu đang đạt thành trượt. Mục tiêu không có núm nào tác dụng → ghi rõ "chưa có núm đẩy được".
  Núm của vấn đề còn ở mặc định → giữ luật cũ (đặt giá trị sửa đề xuất).
- `loop.do_propose` gọi bản này trước, bộ nhớ hướng vặn (`tuning_memory`) vẫn áp sau.

## Pha 4: trang Độ thật (subagent C)
- Nút "Đo độ nhạy" (spawn systemd-run `tdm-realism-sens-<ts>`), tiến độ, dừng (stop.flag).
- Bảng nhiệt núm × mục tiêu: Δ, CI, ý nghĩa, C2ST; đánh dấu "đã cũ" khi núm sản xuất khác `base_knobs`.

## Nghiệm thu (main, làm chậm)
1. Test đơn vị mọi pha. 2. Pilot: gốc + replay + ControlNet+ (kiểm replay trùng điểm ảnh). 3. Chạy đủ. 4. Đọc ma trận,
đối chiếu với luật tay. 5. Một vòng propose theo dữ liệu + cycle qua cổng, so với luật tay. Click thật trên trang.
Không chạy batch khi subagent còn sửa pipeline (bài học R9).

## Tiến độ (2/10)
- Pha 1–4 xong (3 subagent song song). Test: realism 5 bộ + plant HMI 12 bộ đều đạt.
- Pilot `sens-20261002-170939` (bấm trên trang): gốc 80 ảnh + 8 replay + ControlNet+. Replay trùng điểm ảnh 80/80 (lệch 0).
- Pilot lộ 2 lỗi CŨ trong thống kê ghép cặp (bước 2–3), đã sửa + test `tests/test-realism-paired-stats-consistency.py`:
  (1) delta = new − prev trên hai tập ca khác nhau, có lúc nằm ngoài chính CI (vd +0,008, CI −0,225…−0,071) → delta tính
  trên ca chung, giữ `delta_full`; (2) `cases` chỉ có ca chạm lỗi → tỉ lệ chạm lỗi bootstrap luôn 1, CI (0; 0) → `cases` có
  cả ca không chạm lỗi, cờ `used`. Thêm `realism/sensitivity_reassess.py` đo lại một lượt đã sinh bằng CPU.
- Sau sửa: 0 delta ngoài CI. Pilot thấy tác dụng phụ thật: `post_depth-` giảm độ dốc biên cả 3 loại nhưng làm tỉ lệ chạm lỗi
  không thấu tụt 0,2 (có ý nghĩa).
- Chạy khô đề xuất theo dữ liệu trên pilot: rỗ khí dao động biên → `post_depth-` λ 0,5 (dự báo 0,329→0,378); không thấu dao
  động biên → "chưa có núm nào đẩy được".
- Chạy đủ `sens-20261002-173715` đang chạy (17:37).

## Đo đủ `sens-20261002-173715` (17:37–18:23)
- 19/19 biến thể, replay trùng 80/80, 0 delta ngoài CI, 35/276 ô có ý nghĩa. `realism/state/sensitivity.json` đã ghi.
- Review (code-review-step4.md): sửa H1 (trang chọn nhầm lượt con -eval-), H2 (need tính từ dự báo), H3+M1 (chặn bước làm tệ
  thêm mục tiêu đang trượt / vượt khoảng), M3 (vòng lặp không chạy khi đang đo), M4 (n=0 không coi là đạt), màu ô between.
- Sau đo đủ: chặn H3 chỉ xét hiệu ứng CÓ Ý NGHĨA (nhiễu −0,04 từng chặn mọi núm cho rỗ khí). Test propose 18/18.
- Phát hiện: ControlNet ±0,1 không đẩy mục tiêu nào; crack_transverse_share +0,3 → nứt đứng +22% (có ý nghĩa);
  crack_widen_px +2 không giúp độ đặc/độ đầy, hại dao động biên; pore_aspect/lop_* có hướng đúng nhưng CI rộng ở 20 ca,
  lop_* làm C2ST không thấu tệ thêm 0,11–0,16; nhoè mép + là núm đa năng nhất (hạ độ dốc biên 3 loại, tăng độ đặc/độ đầy nứt,
  hạ góc không thấu).
- Chạy khô: rỗ khí dao động biên → post_depth− λ 0,5 (0,329→0,378); không thấu dao động biên: chưa núm nào đẩy được.
  Luật cũ "núm còn mặc định → giá trị sửa" vẫn bật cho vấn đề 2–4 (chưa dùng dữ liệu).

## Nghiệm thu bước 5 (người dùng đồng ý 20:08)
- Đề xuất theo dữ liệu: luật cũ "núm còn mặc định → giá trị sửa" bỏ qua vấn đề có núm đã đo (để dữ liệu quyết). Test 19/19.
- Chạy khô: post_depth −0,05; nhoè mép 3,0→3,73; nứt đứng 0→0,31 (4 núm, đều có số đo).
- Thêm `--source` cho `realism.loop --action evaluate`; đo lượt gốc độ nhạy thành vòng 4 (4 loại), cổng nhận làm bản tốt nhất.
- LỖI MỚI tìm thấy: C2ST không ngấu vòng 4 (0,710) ≠ vòng 3 (0,675) dù cùng núm, cùng ca. SD trùng điểm ảnh, mặt nạ trùng;
  lệch do khoá ngẫu nhiên làm tối = TÊN TỆP (mang số thứ tự job): tính lại với tên tệp cũ khớp 100%. Sửa: khoá = loại + seed
  (`darken_key` trong batch-production-main.py, CRLF giữ). Ảnh hưởng đo cũ: 7 biến thể generate một loại (pore_*, lop_*) nhiễu thêm.
- Cổng: đếm mục tiêu và C2ST chỉ trên cặp loại có ở CẢ HAI vòng (lỗi "đạt 14 so 3"); không cặp chung → neutral.
- Biến thể generate cũng lưu ảnh trước-làm-tối. Test: 6 bộ realism + 12 bộ HMI đạt.
- Đo lại đủ `sens-20261002-201455` (20:15) với khoá mới.
- Ghi chú bước 5b ("chỉ sinh loại bị ảnh hưởng"): cổng nhận vòng ít loại sẽ thay bản tốt nhất nhiều loại, mất phủ; cần gộp kết quả theo loại.
- Đo lại `sens-20261002-201455`: 38 ô có ý nghĩa; pore_aspect, lop_tilt, lop_wave giờ có hiệu ứng đúng thiết kế (trước bị nhiễu
  khoá che); jitter = 0 đúng lý thuyết (lỗ tròn).
- Vòng 5 = lượt gốc mới (cùng núm sản xuất, khoá theo ca): cổng LOẠI so vòng 4 dù núm và ảnh SD giống hệt, chỉ khác rút ngẫu
  nhiên làm tối (PO C2ST 0,82→0,92; LP độ dốc 1,47→1,59 trượt). Đặt tay best = vòng 5 (ghi chú trong best.json).
- Vòng 6 (đề xuất theo dữ liệu, 5 núm: độ sâu 0,45→0,28, nhoè 3,0→3,52, thuôn lỗ khí 1,0→1,55): C2ST TB 0,754→0,620
  (CR 0,73→0,65; PO 0,92→0,66; LP 0,70→0,61; LF 0,67→0,57); 6 mục tiêu chuyển đạt; 2 trượt: LP độ đặc 0,823→0,861 (không ý nghĩa),
  nứt độ lệch tâm AUC 0,391→0,330 (có ý nghĩa) → cổng LOẠI. Bộ nhớ hướng vặn: 5 núm nửa bước. Đề xuất kế: độ sâu 0,37, nhoè 3,26, thuôn 1,28.
- Vòng 7 (nửa bước: độ sâu 0,37/0,57, nhoè 3,26, thuôn lỗ khí 1,28): cổng NHẬN, best = vòng 7. So vòng 5: 5 mục tiêu chuyển đạt
  (LP độ dốc 1,59→1,43; LP dao động 0,35→0,40; LF dao động 0,35→0,39; góc 89,46→88,71; LP độ đầy 0,74→0,69), 0 trượt;
  C2ST CR 0,730→0,718, PO 0,923→0,763, LP 0,696→0,543, LF 0,668→0,576 (TB 0,754→0,650). Chưa đưa vào sản xuất.
- Ma trận độ nhạy giờ "đã cũ" với núm thử (điểm gốc = vòng 5): đề xuất kế sẽ về luật tay cho tới khi đo lại quanh điểm mới.
- 3/10: kiểm bằng mắt 7 loại không có ảnh thật (LOSWF, undercut, slag, linear slag, elongated cavity, clustered/linear porosity),
  3 ca/loại, cùng seed + nền, núm SX cũ vs vòng 7 (`output/realism-loop/visual-check-iter07/`): lỗi nhạt + mềm mép hơn chút,
  vẫn thấy rõ, không hỏng; chênh TB ≤ 0,12 mức xám. Người dùng đồng ý → đã bấm "Đưa bản tốt nhất (vòng 7) vào sản xuất";
  knobs.json = vòng 7. Ma trận độ nhạy giờ "đã cũ" (trang báo stale).
- Trạng thái bước 4: XONG. Tiếp: bước 5 (20 ảnh/loại, chỉ sinh loại bị ảnh hưởng; cần gộp kết quả theo loại cho cổng).
