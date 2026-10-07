# Code review, bước 4 (đo độ nhạy núm), read-only

Ngày 2026-10-02. Phạm vi: realism/sensitivity_*.py, predarken_replay.py, loop.py (do_propose), paired_stats.py,
evaluate.compare(), hook REALISM_SAVE_PREDARKEN trong batch-production-main.py, plant_realism_sensitivity_routes.py,
plant_realism_routes.py (stop), plant-hmi-realism-sensitivity.js, 4 tệp test.

Test: test-realism-sensitivity-propose (14 OK), test-realism-sensitivity-screen (14 OK),
test-realism-paired-stats-consistency (5 OK), test-plant-hmi-realism-sensitivity (28 OK). Không test nào tạo run dir thật.
Đã chạy `sensitivity_propose.propose()` (chỉ đọc) trên dữ liệu pilot sens-20261002-170939 để kiểm hành vi thật.

## HIGH

### H1. `sens_job()` chọn nhầm run con `sens-...-eval-*`; trang báo "lỗi", nút Dừng trả 409 khi lượt đo đang chạy
- plant_hmi/plant_realism_sensitivity_routes.py:52-53, 79-83; gốc ở realism/runlog.py:61-64 (sắp theo mtime thư mục).
- `_sens_runs()` lọc `startswith("sens-")` nhưng KHÔNG loại `-eval-` (loop thì có: plant_realism_job_status.py:43).
  Run con đo (`<run_id>-eval-base`, `-eval-post_depthp`...) cũng bắt đầu bằng `sens-`. `list_runs()` sắp theo mtime thư mục;
  thư mục cha chỉ đổi mtime khi TẠO tệp mới (events.jsonl lúc đầu, generate-*.log, sensitivity.json cuối), append không đổi.
  Mỗi `evaluate.run` ghi result.json vào thư mục con → thư mục con thành `runs[-1]`.
- Đã thấy thật: `list_runs()` hiện cho thứ tự `...-eval-controlnet_strengthp, sens-20261002-170939` (thư mục cha chỉ lên cuối
  nhờ sensitivity.json lúc 17:36). Trong suốt 17:2x-17:36 run con đứng cuối.
- Hậu quả trong lượt đang chạy (sens-20261002-173715) sau khi đo xong lượt gốc, nhất là cả pha replay (không tạo tệp ở thư mục cha):
  - `_job_for("<rid>-eval-base")`: thư mục con (đi qua `_RunLogProxy`) không có events.jsonl → nhánh `not ev` →
    `is_unit_active("tdm-realism-<rid>-eval-base")` sai → state "failed", "lượt đo dừng khi khởi động".
  - `/api/stop` (plant_realism_routes.py:177-189): `sj.state != running` → 409 "Không có vòng lặp nào đang chạy". Người dùng
    KHÔNG dừng được lượt đo từ trang. Nếu thư mục con có events (sau `sensitivity_reassess`), state "running"/"dead" và leo
    thang `systemctl stop tdm-realism-<rid>-eval-x` vào unit không tồn tại.
  - `latest_pilot` đọc `read_json(runs[-1], "sensitivity.json")` của run con → None.
  - `/api/sensitivity/start` không thấy lượt đang chạy (chỉ còn chặn nhờ kiểm phiếu GPU).
- Sửa: `_sens_runs = [r for r in list_runs() if r.startswith("sens-") and "-eval-" not in r]`, tốt hơn nữa là sắp theo tên
  (run_id có dấu thời gian) thay vì mtime. Thêm test: tạo `sens-A`, rồi `sens-A-eval-base` mới hơn → `sens_job()` phải trả `sens-A`.
- Tạm thời cho lượt đang chạy: dừng bằng `touch realism/state/stop.flag` hoặc `systemctl --user stop tdm-realism-sens-20261002-173715`.

### H2. propose "data" cộng dồn bước cho mục tiêu mà dự báo đã đạt nhờ biến thể đã nhận trước đó (sửa quá tay)
- realism/sensitivity_propose.py:159 (`need = _need(t)` lấy theo `t["measured"]`), 115-129, 162.
- `need` và λ của mỗi mục tiêu tính từ giá trị ĐO, không tính từ dự báo sau các bước đã nhận (`accepted`). Hiệu ứng có tương
  quan (pilot: `post_edge_blur_sigma+` hạ bien_doc của CR, PO, LF cùng lúc). Khi đã nhận biến thể A cho CR bien_doc, vòng lặp
  vẫn tìm thêm biến thể B cho PO bien_doc dù `predict(accepted)` đã cho PO đạt → hai nhóm núm cùng đẩy một hướng, vượt đích,
  dễ làm hỏng mục tiêu khác mà kiểm "đang đạt → trượt" không bắt được vì nó chỉ xét mục tiêu đang đạt.
- Sửa: trước khi chọn ứng viên, `pred = predict(result, sens, accepted)`; bỏ qua nếu `issues.passes(pred[label], t)`; tính
  `need` từ `pred[label]` (viết `_need(t, v)` nhận giá trị). Thêm test hai mục tiêu cùng bị một biến thể đẩy.

### H3. Không có lưới chặn làm tệ thêm mục tiêu ĐANG TRƯỢT (luật tay có guard "hit thấp", bản data bỏ mất)
- realism/sensitivity_propose.py:137-138; so với issues.py:100,111-113.
- Kiểm hỏng chỉ xét `t2["pass"] is True`. Luật tay chặn hạ độ sâu làm tối khi tỉ lệ chạm lỗi đang thấp. Pilot đo
  `post_depth-` làm LP hit giảm 0,2 (có ý nghĩa). Nếu LP hit đang trượt (<0,7), mode data vẫn chọn `post_depth-` cho bien_doc /
  dao động biên và kéo hit xuống tiếp. Cổng nghiệm thu cũng không bắt vì mục tiêu đó không nằm trong "phải giữ".
- Sửa: loại ứng viên khi dự báo đưa một mục tiêu đang trượt xa đích hơn (|need| tăng) quá một ngưỡng, hoặc ít nhất port guard
  `low_hit` cho mục tiêu bien_doc.

## MEDIUM

### M1. `between`: sàn λ = 0,5 cho phép vượt sang phía bên kia khoảng, không kiểm chính mục tiêu đó
- sensitivity_propose.py:125-126, 136-140.
- λ kẹp dưới 0,5 nên khi |Δ| ≫ need thì bước thực tế 0,5·Δ có thể vượt `hi`. Ví dụ PO lệch tâm [0,72; 0,90], đo 0,70, need
  0,029, Δ = 0,5 → dự báo 0,95, vẫn trượt (phía trên). `frac = min(1, …)` = 1 nên ứng viên này còn xếp hạng cao nhất.
- Sửa: với `between`, nhận ứng viên chỉ khi dự báo của chính mục tiêu nằm trong [lo, hi]; hoặc bỏ sàn λ khi dự báo vượt
  (cho λ < 0,5 với `between`, vẫn giữ trần 2). Plan có ghi kẹp [0,5; 2] nên cần người dùng chốt.

### M2. Nhiều phép so sánh: chọn "có ý nghĩa" ở mức 95% trên ~19 biến thể × ~22 mục tiêu
- paired_stats.compare_paired (dòng 157-193), sensitivity_propose._candidates.
- ~400 phép thử, kỳ vọng ~20 ô "có ý nghĩa" giả. `_candidates` xếp theo hiệu ứng lớn → thiên về ô nhiễu lớn (winner's curse).
  Pilot đã thấy `post_modulation_sigma-` "có ý nghĩa" với bien_doc LF (+0,116) và góc nghiêng rỗ khí đổi dấu có ý nghĩa ở 3
  biến thể làm tối, khó tin về vật lý.
- Sửa (chọn một): CI 99%/BH-FDR cho bước chọn núm; với nhóm hai phía đòi hai biến thể +/− ngược dấu nhau; hoặc đòi
  |Δ| > ngưỡng tối thiểu theo mục tiêu. Bảng nhiệt nên ghi rõ mức.

### M3. `/api/run` của vòng lặp không kiểm lượt đo độ nhạy; tiến trình loop xoá stop.flag chung
- plant_realism_routes.py:131-136; realism/loop.py:160 và 192; tương tự sensitivity_screen.py:183, 195.
- `/api/run` chỉ kiểm `job_status.job()` và `batch_running()`. Trong pha replay/đo của lượt độ nhạy không có batch nào →
  bấm Đánh giá/Đề xuất/cycle vẫn mở loop. Loop `STOP.unlink` lúc vào và trong finally → nuốt lệnh dừng đang chờ của lượt đo.
  Sau đó `job()` trả loop là "running", `/api/stop` nhắm vào loop chứ không phải lượt đo. cycle/auto sẽ GpuBusy nhưng vẫn
  chạy finally xoá cờ.
- Sửa: trong `/api/run` thêm `if sens_job().get("state") == "running": 409` (sau khi sửa H1) và kiểm `gpu_lease.current()`
  cho cycle/auto. Trong `sensitivity_screen.main` chỉ xoá STOP sau khi xin được phiếu GPU (chuyển vào do_screen sau acquire).

### M4. Tự kiểm replay qua được khi không có ảnh nào (n = 0)
- sensitivity_screen.py:47-63, 126-129.
- Nếu hook không lưu .npz (lỗi bị `except Exception: pass` nuốt ở batch-production-main.py ~132, đĩa đầy, env không truyền),
  `_self_check_replay` trả `{"n": 0, "max_diff": 0}` → qua. Biến thể replay ra thư mục rỗng, evaluate 0 ảnh, mọi hiệu ứng
  `n_common = 0`, không ý nghĩa; lượt vẫn `finished: True` và (không pilot) ghi đè realism/state/sensitivity.json.
  Tức ma trận "không núm làm tối nào có tác dụng" sai, ghi vào sản xuất.
- Sửa: đòi `n == số ảnh gốc của các loại` (hoặc ≥ 0,9×), không thì RuntimeError. Cũng nên đếm và ghi số .npz.

### M5. Mode data không quay về luật tay cho mục tiêu thiếu ứng viên; auto có thể dừng sớm
- sensitivity_propose.py:162-165; loop.py:140.
- Mục tiêu "chưa có núm đẩy được" chỉ ghi lý do. Nếu mọi mục tiêu trượt đều không có ứng viên (và không có vấn đề ở mặc định),
  `changes` rỗng → do_auto kết thúc "không còn núm nào để đổi", dù `issues._rule` vẫn có bước. Pilot: LP dao động biên
  không có ứng viên.
- Sửa: với mục tiêu không có ứng viên, gọi `issues._rule(t, current)` như cũ (đánh dấu "luật tay") nếu núm chưa bị đụng.
  Cần người dùng quyết vì plan chỉ nói "ghi rõ".

## LOW

- L1. `_helps` (routes:89-106) dùng `prev/new` cả bộ cho `between` nhưng `delta` ca chung cho `>=`/`<=`; nay delta và
  new−prev có thể khác dấu → màu ô "giúp/hại" mâu thuẫn số hiển thị. Dùng thống nhất `delta` (between: so prev và prev+delta).
- L2. `has_cases` (loop_gate.py:50-51): nay `cases` gồm cả ca không dùng được → vòng mà mọi ca trượt chạm lỗi vẫn thành
  "mốc mới: bộ đề thi". Trước đây trả rỗng → neutral. Cân nhắc `any(c.get("used", True) for c in cases)`.
- L3. Kết quả cũ (trước đổi evaluate) chỉ có ca "ok" nên hit trong cases luôn 1; `compare_paired` giữa result cũ và mới cho Δhit
  lệch. Hiện không ai so chéo (gate dùng pairs, sens dùng hai lượt mới) nhưng nên ghi chú/đánh phiên bản lược đồ cases.
- L4. Hook predarken lưu `strength=np.float32(...)`; replay dùng `float(...)` = 0,9200000166893005. Hiện trùng điểm ảnh vì `m`
  là float32 nên Python float bị ép về float32 trong cả hai đường. Phụ thuộc quy tắc ép kiểu của numpy; lưu float64 cho chắc.
- L5. `run_batch_subprocess` (gen.py:89-100): ngoại lệ khác Stopped trong vòng poll (vd glob OSError) để lại tiến trình con
  ngoài session riêng. Bọc try/except giết `killpg` trước khi ném lại. Khi chạy dưới systemd, `systemctl stop` vẫn dọn cgroup.
- L6. `_START` chỉ khoá trong một worker; nhiều worker uvicorn → hai lượt có thể cùng spawn (lượt sau GpuBusy nhưng thành
  `runs[-1]`, che lượt đang chạy). Ổn nếu launcher một worker.
- L7. C2ST trong ma trận chỉ là điểm (không CI) trên ~20 ảnh/loại, rất nhiễu; bảng nên ghi "không kiểm ý nghĩa".
- L8. Tên tệp cấu hình `sens-{run_id}-…` thành `sens-sens-…` (gen.py:65, 71). Thẩm mỹ.
- L9. `gen_done/gen_total` trong `_job_for` lấy bản gen_progress cuối, vẫn hiện "80/80 ảnh" trong pha replay sau đó.
- L10. Tệp test 261-295 dòng (>200). Mã chính đều ≤200 (sensitivity_screen 199, routes 193, paired_stats 193).

## Đã kiểm, không có lỗi
- Thay đổi evaluate/paired_stats: `loop_gate._mean_c2st_delta` và `bootstrap_criteria` dùng `_cases_by_pair` mặc định
  `used_only=True` → hàng không dùng được (thiếu sáu tiêu chí) không tới chỗ index `c[k]`. `_target_case_values` có `if col in c`.
  Mục tiêu hit dùng `used_only=False` đúng mẫu số. Không còn consumer nào khác của `result["cases"]` ngoài test.
- compare_paired: delta và CI cùng tập ca chung, cùng chỉ số mẫu lại cho hai vòng; `significant` khi CI không chứa 0. Đúng.
- Dấu của need cho `between` (lấy cận gần, có biên 5%), ứng viên hai phía (`-` cho `changed` âm), núm mới = gốc + λ·(mới−gốc),
  kẹp sổ đăng ký + đổi chỗ cặp min/max: đúng.
- POST /api/sensitivity/start: có `_require_trusted_request`, n kiểm int 5..40, run_id do server sinh, argv dạng list,
  `--expand-environment=no`. Không có path traversal (run_id không nhận từ client; reassess chỉ là CLI cục bộ).
- JS dựng DOM bằng `h()`, không innerHTML từ dữ liệu.
- Phiếu GPU: acquire bằng pid tiến trình chính, release trong finally; pid chết thì phiếu tự hết hạn. Stop: kiểm giữa lượt và
  trong poll sinh (killpg TERM → 60 s → KILL); `except Stopped: raise` trong vòng biến thể.
- Bản PV sensitivity.json ghi atomic, chỉ khi không pilot và mọi biến thể OK.

## Thứ tự sửa đề xuất
1. H1 (ảnh hưởng ngay lượt đang chạy: không dừng được từ trang). 2. H2, H3, M1 trước khi dùng mode data cho một vòng thật
(bước nghiệm thu 5). 3. M3, M4. 4. M2, M5 cần người dùng chốt. 5. LOW.

## Câu hỏi còn mở
- Giữ sàn λ 0,5 cho `between` hay cho phép λ nhỏ hơn (M1)?
- Mức ý nghĩa cho bước chọn núm: 95% như cổng, hay chặt hơn (M2)?
- Mục tiêu không có ứng viên data: quay về luật tay hay chỉ ghi lý do (M5)?

**Status:** DONE_WITH_CONCERNS
**Summary:** Thống kê ghép cặp và thay đổi cases an toàn với consumer hiện có. Còn 3 lỗi HIGH: HMI chọn nhầm run con
`-eval-` nên trạng thái sai và không dừng được lượt đo đang chạy; propose data cộng dồn bước cho mục tiêu đã được dự báo đạt;
không chặn làm tệ thêm mục tiêu đang trượt.
