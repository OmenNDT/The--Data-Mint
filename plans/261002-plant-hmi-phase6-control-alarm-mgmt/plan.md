# Plant HMI phase 6: start/stop có interlock, xác nhận/tạm tắt báo động, đánh giá vòng kín

Trạng thái: ĐÃ TRIỂN KHAI 2026-10-02, đã chạy thật. 6C: không làm vòng kín (không đủ bằng chứng R9). Phase trước: `plans/260926-2151-plant-hmi-phase4-5-blackbox-setpoints/`.
Chặn CSRF dùng chung: `plant_hmi/plant_request_guards.py` → `require_trusted_request(request, x_plant_hmi)` cho MỌI route ghi.

## 6A. Start/stop batch có interlock — subagent A
- Khởi chạy bằng `systemd-run --user --unit=tdm-batch-<yymmdd-hhmmss>` (job nằm ngoài cgroup `tdm-backend`,
  restart backend không giết job, xử lý luôn rủi ro R8). Lệnh: `.venv/bin/python batch_manager/batch-production-main.py
  --config <cfg> [--pilot] [--resume]`, working dir `pipeline/`.
- Config chỉ được chọn từ whitelist: `pipeline/config/*.yaml` và `pipeline/config/_generated/*.yaml` (không nhận path tuỳ ý).
- Permissive (hàm thuần `evaluate_permissives(state) -> [{code, ok, message}]`), start bị chặn nếu bất kỳ cái nào false:
  `NO_LIVE_BATCH` (không có batch sống, bơm P-601 đơn), `COMFY_UP` (probe ok), `NO_TRAINING` (không có `train_network`),
  `MEM_OK` (không MEM_LOW/SWAP_THRASH), `CONFIG_VALID` (YAML đọc được, có paths/output_base_dir).
  Cảnh báo (không chặn): `MAIN_SILO` khi output_base_dir là silo chính `output/synthetic`.
- Stop: chỉ batch đang sống; unit `tdm-batch-*` → `systemctl --user stop <unit>`, còn lại → SIGTERM pid (pid phải là
  tiến trình batch thật theo `find_batch_processes`). Ghi chú: checkpoint ghi mỗi 100 ảnh, dừng có thể mất ≤ 99 ảnh tiến độ.
- API: `GET /plant-hmi/api/control/batch` → `{configs:[{name,path,output_dir,main_silo}], permissives:[...], live:[{pid,unit,config_name}]}`;
  `POST /plant-hmi/api/control/batch/start` body `{config, pilot:bool, resume:bool, reason}`; `POST /plant-hmi/api/control/batch/stop`
  body `{pid, reason}`. 409 khi permissive chặn (trả danh sách lý do). Audit JSONL `plant_hmi/control/batch-audit.jsonl`.
- UI `static/plant-hmi-batch-control.js` (`initBatchControl(container)`) + `.css`: chọn config, pilot/resume, danh sách permissive
  (xanh/đỏ), Start/Stop hai bước (Arm → Xác nhận/Huỷ), lý do, audit gần nhất.

## 6B. Quản lý báo động ISA-18.2 (ack/shelve) — subagent B
- Trạng thái: UNACK_ACTIVE, ACKED_ACTIVE, CLEARED_UNACK (đã hết nhưng chưa xác nhận, vẫn hiện tới khi ack), SHELVED (tới hạn).
- `plant_hmi/plant_alarm_state.py`: store JSON (`plant_hmi/control/alarm-state.json`, atomic) theo khoá `CODE|TAG|pid`;
  hàm thuần `annotate_alarms(active_alarms, store, now) -> {"alarms": [...+ack/shelved fields], "cleared_unacked": [...],
  "shelved": [...]}`; shelve có hạn (15 phút / 1 giờ / 8 giờ, tối đa 8 giờ) + lý do; hết hạn tự bỏ.
- Journal: ghi thêm dòng `acked` / `shelved` / `unshelved` vào `alarm_journal` (state là text tự do).
- API: `POST /plant-hmi/api/alarms/ack` `{key, reason?}`, `POST /plant-hmi/api/alarms/ack-all`, `POST /plant-hmi/api/alarms/shelve`
  `{key, minutes, reason}`, `POST /plant-hmi/api/alarms/unshelve` `{key}`; `GET /plant-hmi/api/alarms/state`.
- UI: sửa `renderAlarms` trong `static/plant-hmi-render-panels.js` (nút Xác nhận / Tạm tắt; chưa xác nhận có vạch sáng bên trái;
  cleared-unacked hiện mờ "đã hết · chờ xác nhận"; dòng "N báo động đang tạm tắt" mở được danh sách); nhãn mới trong
  `static/plant-hmi-alarm-journal.js`. Nếu render-panels vượt 200 dòng thì tách module alarm riêng.

## 6C. Vòng điều khiển kín — main (đánh giá trước, R9)
- Chỉ làm nếu historian cho thấy quan hệ đo được và biến điều khiển có tác động. Ứng viên: giãn nhịp theo nhiệt GPU
  (thay dừng/chạy của thermal monitor). Kiểm tra max `gpu_temp_c` trong historian so với ngưỡng 85°C.

## Main
- Gắn router + container + init; snapshot dùng `annotate_alarms`; restart service (kiểm tra không có job); kiểm tra thật:
  interlock chặn start khi ComfyUI tắt, start pilot từ HMI, stop giữa chừng, restart backend không giết job do HMI khởi chạy,
  ack/shelve một báo động thật (COMFY_DOWN khi ComfyUI tắt) và journal ghi đủ.

## 6C. Kết luận đánh giá vòng kín (historian 130 giờ, 26/9 → 2/10)
- `gpu_temp_c` khi có batch: TB 65,7°C, max 75°C; max toàn kỳ 82°C (lúc không có batch). Ngưỡng thermal 85°C chưa lần nào chạm,
  telemetry không có lần `thermal_hold` nào. → Vòng giãn nhịp theo nhiệt KHÔNG có dữ liệu chứng minh tác động: không làm (R9).
- Swap thrash (11 lần) và MEM_LOW (3 lần) do tải khác trên máy; chỉ 2 mẫu swap > 1000 trang/s trùng lúc có batch.
  → Xử lý bằng interlock khởi chạy (`MEM_OK` ở 6A), không cần vòng kín.
- Ứng viên đáng đo tiếp: sắp job theo defect để giảm đổi LoRA (~2 s/ảnh ở pilot 12 defect). Đây là knob vòng hở; cần đo trước.

## Sự cố phát hiện nhờ HMI
- `batch-config.yaml` được người dùng sửa tay lúc 27/9 09:52 (chỉnh tỷ lệ 0,0833 + chú thích), mang theo `host: 10.86.201.250` cũ.
  COMFY_HOST_NOT_LOCAL bật từ lúc đó. Đã sửa riêng dòng host về `127.0.0.1` (người dùng xác nhận giữ), giữ nguyên phần chỉnh khác.

## Kết quả nghiệm thu (2/10)
- 154 unit test đạt (alarm 18, telemetry 16, historian 21, comfyui-progress 12, setpoints 38, batch-control 35, alarm-state 14).
- 6A: Start khi ComfyUI tắt → 409 (COMFY_UP); Start từ HMI → unit `tdm-batch-261002-075134` chạy; Start lần 2 → 409 (NO_LIVE_BATCH);
  restart `tdm-backend` giữa batch → batch vẫn sống (pid 968945, 3/12 ảnh) nhờ systemd-run ngoài cgroup (R8);
  Stop pid lạ → 409; Stop thật → unit inactive. Audit ghi cả lần bị từ chối.
- 6B: COMFY_DOWN thật: ack (403 khi thiếu header) → acked; shelve 5 phút → 422, 15 phút → 200; báo động rời danh sách chính,
  vẫn trong `alarms_all`, journal KHÔNG ghi cleared giả; journal có acked/shelved/unshelved/cleared.
- Main: snapshot thêm `alarms_all`/`alarms_cleared_unacked`/`alarms_shelved`; sampler journal dùng `alarms_all`.

## Lỗi phát hiện khi nghiệm thu và đã sửa
- `plant_realism_routes.py` (phiên khác tạo 30/9) import tên cũ `_require_trusted_request` → trang Realism không mount sau
  khi tách guard. Thêm bí danh tương thích trong `plant_setpoint_routes.py`.
- `NO_TRAINING` báo nhầm khi dòng lệnh shell chứa chữ "train_network" (vd `pgrep -af`). Chỉ đếm tiến trình python/accelerate
  có tham số `train_network.py`; thêm test bằng tiến trình thật.
- `MEM_OK` lần gọi đầu sau restart là "chưa đọc được" (tốc độ swap cần 2 lần đọc) → chặn an toàn, lần sau bình thường.

## Review phase 6 và xử lý (2/10, 08:20)
- Review: 2 Critical (C1 nút báo động chết vì `setAttribute('onclick', fn)`; C2 poll snapshot ghi đè mất ack), 5 High.
  Lần nghiệm thu trước gọi API trực tiếp nên không lộ C1 → lần này nghiệm thu bằng click thật trên trình duyệt.
- 6B sửa: C1 (+ kiểm tra node `tests/js/check-alarm-list-buttons.mjs`), C2 (`annotate_from_store` đọc-tính-ghi trong 1 khoá,
  không ghi khi không đổi), H5 (tạm tắt theo điểm `code|tag|pid`), M2, M4, ack-all, journal khi tạm tắt hết hạn.
- 6A sửa: H2 (khoá file khi start + chặn bấm 2 lần), H3 (SIGINT, `KillSignal=SIGINT`), M1, M5, M6 (gợi ý resume), M7
  (`--service-type=exec --collect --expand-environment=no`), chặn ký tự điều khiển, so start_ts khi stop.
- Main sửa: H1 (seed journal bỏ qua dòng acked/shelved), H4 (Host allowlist chống DNS rebinding, `PLANT_HMI_ALLOWED_HOSTS`),
  `batch-production-main.py` lưu checkpoint khi KeyboardInterrupt (CRLF giữ nguyên), câu xác nhận stop.
- Nghiệm thu bằng click thật: Xác nhận → acked; Tạm tắt 15 phút + lý do tiếng Việt (giữ focus qua poll) → shelved;
  restart backend → vẫn shelved, không có raised trùng; Start bằng UI → unit Type=exec, KillSignal=2; Stop bằng UI ở ảnh 11 →
  "Checkpoint saved: 11 images complete", checkpoint 11/30 = 11 PNG; Start resume → "Auto-resumed", 30/30, 30 PNG.
- 179 unit test + kiểm tra node đạt.

## Còn mở
- Nút chạy trong tab Generation của Gradio chưa đi qua khoá + permissive của HMI (có thể chạy song song với batch do HMI start).
- 3 file hơi vượt 200 dòng: `plant_historian_sampler.py` 203, `plant_historian_store.py` 201, `plant-hmi-batch-control-panel.js` 229.

## Thư mục riêng cho mỗi lần chạy (2/10, yêu cầu người dùng)
- Start từ HMI không còn ghi thẳng vào output_base_dir của config: `plant_batch_run_dirs.new_run` chép config sang
  `config/_generated/runs/<YYYY-MM-DD_HHMMSS>_<config>.yaml`, mọi path trỏ vào `output/synthetic/<YYYY-MM-DD_HHMMSS>_<config>/`
  (ảnh theo defect, checkpoints/, logs/). Resume dùng lần chạy dở mới nhất của config đó; không có → 409.
- Permissive MAIN_SILO (cảnh báo) thay bằng RUN_DIR (thông tin). Silo TK-801 lúc nghỉ đếm cả `<run>/<defect>/`.
- Post-processing chạy theo từng lần: `--synthetic-dir output/synthetic/<thư mục lần chạy>`.
- 178 unit test đạt; chưa chạy batch thật với cấu trúc mới (lần chạy LF 100 của người dùng sẽ là lần đầu).

## Hai nút thao tác (2/10, yêu cầu người dùng)
- "📁 Nơi lưu output" (Bước 10): danh sách lần chạy mới nhất trong `output/synthetic/20*`, số ảnh, nút Mở thư mục
  (`gio open` trên màn hình máy chạy HMI) và Sao chép đường dẫn. Chỉ mở được thư mục con trực tiếp của silo.
- "Tắt/bật ComfyUI" (Bước 11): unit `tdm-comfyui` dùng `comfyui/.venv`; tắt cần xác nhận 2 bước, bị chặn (409) khi có batch.
- Tooltip `data-tip` (hiện khi rê chuột và khi focus bàn phím). API `/plant-hmi/api/control/tools/{runs,open,comfyui}`, có guard
  CSRF + audit.
- Nghiệm thu bằng click thật: danh sách hiện lần chạy LF 100 của người dùng (100 ảnh, 638 ảnh/giờ, 0 lỗi); Mở thư mục → cửa sổ
  hiện trên màn hình (xdotool xác nhận); Tắt → inactive; Bật → active + HTTP ok. 184 unit test đạt.

## Form tạo mẻ mới, nút đánh giá, gỡ tab Tạo Ảnh (2/10)
- "＋ Tạo mẻ mới" (subagent): config gốc, tên, tổng ảnh, tỷ lệ 13 defect (số ảnh từng loại cộng đúng tổng), thư mục nền;
  ghi `config/_generated/<tên>.yaml`, không đụng config gốc; permissive mới LORA_PRESENT. Click thật: mẻ 2 ảnh → đúng thư mục
  riêng, 1 crack + 1 LF (đã xoá dấu vết thử).
- Nút "Đánh giá độ thật" mỗi lần chạy (plant_run_evaluation.py, chạy realism.evaluate tách tiến trình).
- Gỡ tab "🖼️ Tạo Ảnh" khỏi launcher (người dùng duyệt); giữ file ui_generation_panel/generation_* vì có thay đổi chưa commit.
- 208 unit test Plant HMI + 20 test realism đạt.
