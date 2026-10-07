# Vòng cải thiện độ thật: an toàn GPU, bộ đề thi cố định, cổng nghiệm thu

Trạng thái: BƯỚC 1–3 XONG, đã nghiệm thu thật 2/10. Còn bước 4, 5. Người dùng duyệt 2/10: làm bước 1–3 trước; bước 4 (độ nhạy) làm chậm, test kỹ; bước 5 chỉ 2 mục.
Plan gốc vòng lặp: `plans/260930-1402-realism-improvement-loop/`.

## Bước 1 — Phiếu thuê GPU + vòng lặp chạy qua systemd-run (subagent A)
- `pipeline/plant_hmi/plant_gpu_lease.py`: file `plant_hmi/control/gpu-lease.json` (flock + ghi nguyên tử).
  `acquire(owner, purpose, pid) -> (ok, holder)`, `release(owner)`, `current() -> dict|None`.
  Phiếu tự hết hiệu lực khi pid chủ đã chết (kiểm /proc + start time chống tái dùng pid). Không TTL thời gian.
- HMI Start: permissive chặn mới `GPU_FREE` (phiếu đang thuộc bên khác, message nêu ai giữ, mục đích, từ lúc nào).
  Batch do HMI khởi chạy tự xin phiếu bằng pid của batch (owner `hmi-batch:<unit>`), tự hết khi batch kết thúc.
- Vòng lặp realism: action `cycle`/`auto` xin phiếu bằng pid tiến trình vòng lặp, giữ SUỐT phiên, nhả khi thoát;
  không xin được → dừng ngay với lý do rõ. `evaluate`/`propose` (chỉ CPU) không cần phiếu.
- `plant_realism_routes.py` khởi chạy vòng lặp bằng `systemd-run --user --unit=tdm-realism-<ts>` (ngoài cgroup
  tdm-backend, R8); dừng: cờ stop.flag như cũ, quá hạn thì `systemctl --user stop <unit>`.
- Snapshot: trường `gpu_lease`; hộp U-901 trên P&ID ghi người giữ phiếu.

## Bước 2 — Bộ đề thi cố định + bootstrap (subagent B)
- Scheduler: khoá config `generation.fixed_jobs` (đường dẫn JSON danh sách {case_id, defect_type, seed, background_image});
  có khoá này thì dùng đúng danh sách, không random, không shuffle. Không có khoá → hành vi cũ y nguyên.
- `realism/exam_set.py`: tạo một lần `realism/state/exam-set.json`: 40 ca/loại cho 6 loại có ảnh thật (seed cố định
  để tạo lại được), ảnh nền chọn từ backgrounds_dir. Tên file ảnh mang case_id để ghép cặp giữa các vòng.
- Vòng lặp sinh lại trên bộ đề thi (n_per_type ≤ 40 lấy n ca đầu mỗi loại).
- `realism/stats.py`: bootstrap theo ca (ghép cặp theo case_id) cho trung vị từng tiêu chí, AUC, C2ST;
  `compare_paired(prev_result, new_result)` → delta + khoảng tin cậy 95% cho từng mục tiêu và điểm tổng.
- Kiểm chứng tất định: sinh lại cùng 1 ca hai lần → ảnh và mask giống nhau (đo sai khác điểm ảnh).

## Bước 3 — Cổng nghiệm thu, giữ bản tốt nhất, tự lùi (subagent B, sau bước 2)
- Điểm tổng mỗi vòng = số mục tiêu đạt + C2ST TB các loại đang nhắm (có CI).
- Nhận vòng nếu tốt hơn rõ (ngoài CI) hoặc không khác (ghi "không cải thiện"; 2 lần liên tiếp → dừng);
  loại vòng nếu tệ hơn rõ HOẶC một mục tiêu đang đạt ở bản tốt nhất bị trượt (điểm phải giữ tự động, thay vấn đề 5 cứng).
- Loại → núm thử về bản tốt nhất, lần sau giảm nửa bước / đổi chiều cho núm vừa đổi.
- "Đưa vào sản xuất" đưa bản tốt nhất. Lịch sử đánh dấu nhận/loại + đường tốt nhất.

## Main
- Kiểm tra avocado-3 (1080Ti) có đáp ứng chạy ComfyUI SD1.5 + LoRA + ControlNet cho vòng lặp không.
- Tích hợp, restart (kiểm tra job bằng ps), nghiệm thu thật bằng click.

## Sau đó
- Bước 4 (độ nhạy từng núm, đề xuất theo dữ liệu): làm chậm, test kỹ.
- Bước 5: chỉ (a) 20 ảnh/loại trên bộ đề thi, (b) chỉ sinh loại bị ảnh hưởng (núm riêng → loại đó; núm mép chung → mọi loại).

## Kết quả bước 1–3 (2/10)
- Bước 1: phiếu GPU (`plant_gpu_lease.py`), GPU_FREE trên HMI, vòng lặp chạy `systemd-run --user --unit=tdm-realism-<run>`.
  Nghiệm thu: khi vòng lặp sinh ảnh, phiếu ghi `realism-loop:<run>`, HMI GPU_FREE ✗ "GPU đang được … giữ … từ 12:31:01";
  xong vòng thì phiếu tự nhả, GPU_FREE ✓.
- Bước 2: `generation.fixed_jobs` trong scheduler (CRLF giữ), bộ đề thi 240 ca (`realism/state/exam-set.json`), bootstrap ghép cặp
  (`realism/paired_stats.py`). Kiểm chứng tất định thật: sinh lại cùng ca 2 lần, sai khác điểm ảnh tối đa = 0.
- Bước 3: `realism/loop_gate.py` (cổng), `tuning_memory.py` (nửa bước / đổi hướng), loop.py tách còn 195 dòng.
- Nghiệm thu bằng click (LF, 20 ca bộ đề thi): vòng 2 (núm mặc định) = mốc, C2ST 0,958, độ dốc biên 2,71×, dao động AUC 0,07;
  đề xuất núm (vấn đề 1 → giá trị sửa, ControlNet 0,7); vòng 3: độ dốc biên 1,26× ✓, dao động AUC 0,43 ✓, vùng chạm lỗi 0,95 ✓,
  C2ST 0,675 → cổng "tốt hơn rõ", thành bản tốt nhất. Chưa đưa vào sản xuất (chờ người dùng).
- Lỗi main tự sửa khi nghiệm thu: (1) điểm cổng đếm theo VẤN ĐỀ thay vì MỤC TIÊU (vòng 2 ghi 0 dù có 1 mục tiêu đạt) → đếm theo mục tiêu;
  (2) test route realism ghi 22 thư mục rác vào realism/state/runs (trang hiện "job lỗi" giả) → test dùng thư mục tạm, đã xoá rác;
  (3) đề xuất sau vòng bị loại dùng số đo của bản tốt nhất; (4) bảng lịch sử thêm cột C2ST Không ngấu.
- Test: 11 bộ Plant HMI + 2 bộ realism (36 + 12) đều đạt.

## Kiểm chứng trước khi đưa vào sản xuất (2/10, 13:36–13:48)
- CR/PO/LP, 20 ca bộ đề thi mỗi loại, ghép cặp: núm mặc định (`output/realism-loop/verify-default`) vs núm vòng 3 (`verify-best`).
  Giữ phiếu GPU `verify-promote` suốt phiên, nhả khi xong.
- C2ST: nứt 0,982→0,810; rỗ khí 0,920→0,820; không thấu 0,999→0,655. Mục tiêu đạt (3 loại): 6→11.
- Độ dốc biên đạt ở cả 3 loại (CI ngoài 0). Không thấu: độ đầy hộp bao 0,95→0,65 ✓, độ đặc 0,97→0,80 ✓.
- Trượt duy nhất: rỗ khí dao động dọc biên AUC 0,373→0,329 (ngưỡng 0,35), không có ý nghĩa thống kê (CI −0,28…+0,15).
  Người dùng duyệt đưa vào sản xuất; theo dõi chỉ tiêu này ở các vòng sau.
- Đã đưa bản tốt nhất (vòng 3) vào sản xuất bằng click trên trang Độ thật; `realism/state/knobs.json` = núm vòng 3, nhật ký ghi lý do.
