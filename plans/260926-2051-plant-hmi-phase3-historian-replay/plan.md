# Plant HMI phase 3: historian, replay, trend

Trạng thái: ĐÃ TRIỂN KHAI 2026-09-26, đã chạy thật (2 subagent song song + tích hợp). Phase trước: `plans/260926-2016-plant-hmi-phase2-telemetry-particles/`.

## Hợp đồng API (chốt, hai bên cùng tuân theo)
Tất cả dưới `/plant-hmi/api/history/`, JSON, thời gian là epoch giây (float).
- `GET tags` → `[{"tag","label","unit","equipment"}]`
- `GET samples?tags=a,b&from=&to=&step=` → `{"step": s, "series": {"tag": [[ts, value], ...]}}` (avg theo bucket; step mặc định tự chọn để mỗi series ≤ 500 điểm)
- `GET alarms?from=&to=&limit=200` → `[{"ts","code","tag","severity","pid","state":"raised|cleared","message"}]` mới nhất trước
- `GET runs` → `[{"run","pid","batch","first_ts","last_ts","jobs_ok","jobs_retry","jobs_failed","events"}]` mới nhất trước (đọc từ file telemetry)
- `GET events?run=<run>&cursor=<int>&limit=5000` → `{"events":[...], "next_cursor": int|null, "total": int}`
  (sửa theo review H4: cursor là chỉ số trong danh sách sự kiện của run đã sắp theo ts, loại trừ, không trùng/không lặp;
  chỉ kind enter/exit/job; `from`/`to` bỏ). Client tải tối đa 40 trang, vượt thì báo "đã cắt bớt" trên dòng trạng thái.

Tag historian (snake_case): tk102_pending, tk801_produced, xi601_batches, si601_img_h, ki201_s, ki601_s, ki401_s,
d901_failed, jobs_ok_1m, job_errors_15m, gpu_temp_c, gpu_util_pct, gpu_vram_used_gib, comfy_up, comfy_queue,
ram_avail_pct, swap_pages_s, load_pct.

## Phân công
- Backend (subagent A): `plant_hmi/plant_historian_store.py`, `plant_historian_sampler.py`, `plant_history_routes.py`, test `tests/test-plant-hmi-historian.py`, 1 dòng gắn router trong `plant_hmi_routes.py`.
- Frontend (subagent B): `static/plant-hmi-replay-*.js`, `static/plant-hmi-trend-panel.js`, `static/plant-hmi-alarm-journal.js`, chỉnh `plant-hmi-app.js`, `plant-hmi.html`, `plant-hmi.css`, `plant-hmi-particle-layer.js` (nguồn thời gian).
- Main: sửa theo review phase 2, restart service, kiểm tra thật (replay run pilot x60, journal có raise/clear).

## Kết quả
- 50 unit test đạt (18 historian, 15 telemetry, 17 alarm).
- Historian: sampler 10 s chạy trong `tdm-backend`, SQLite `plant_hmi/historian/plant-historian.sqlite`, giữ 30 ngày.
- Journal thật: COMFY_DOWN LO bật 21:05:01 (ComfyUI tắt), tắt 21:06:13 (bật ComfyUI). Đã sửa: dòng "cleared" nay giữ mức độ và nội dung.
- Batch thật 24/24 ảnh; samples truy vấn được (tk801_produced, ki601_s, gpu_util_pct).
- Replay: run 20:43 (3 ok / 5 lỗi) phát x10, hạt + level + D-901 khớp sự kiện thật.
- Review phase 2: backend tự sửa (truncated/cursor, owned filter, thermal exit, partial run, bỏ file nguội, ts cuối snapshot), client do subagent frontend sửa (6 điểm).

## Còn mở
- Replay chưa hiện báo động và utilities (GPU/RAM) từ historian.
- TK-801 khi replay không có thang mức (run không có target).
- M2: tiến độ khi batch resume từ checkpoint (pipeline báo 24/24 trong khi config 20).
- KI-201 hiện "0": sinh mask < 50 ms, làm tròn 0,1 s.

## Review phase 3 và xử lý (21:40)
- 2 subagent sửa song song: backend H4, H5, M4-M6, L1-L4, L7; frontend H1-H3, M1-M3, M7, L5, L6, L8, L9.
- Main tự sửa thêm sau kiểm tra thật: sau restart backend, nhật ký ghi "cleared" rồi "raised" giả cho báo động
  vẫn đang bật. Hai nguyên nhân: probe chưa trả lời (inputs "chưa rõ"), và bộ trễ on-delay đếm lại từ đầu.
  Cách sửa: snapshot trả `alarms_unknown`, sampler giữ báo động có inputs chưa rõ; `AlarmOnDelay.seed()` nạp
  `since` từ nhật ký khi khởi động.
- Kiểm tra thật: phân trang cursor (50/50/132, trang cuối next_cursor=null); tag sai trả 400; restart giữa lúc
  COMFY_DOWN bật không sinh dòng trùng; cleared ghi đúng khi bật lại ComfyUI; phát lại x60 tới hết, tự dừng
  với nhãn đúng; bấm chạy lại sau khi hết run có hạt; tua lùi có hạt; Trực tiếp → Phát lại giữ hạt;
  utilities hiện "không có dữ liệu khi phát lại".
- 54 unit test đạt (21 historian, 15 telemetry, 18 alarm).
- Lệch quy ước: `plant_historian_sampler.py` 202 dòng, `test-plant-hmi-historian.py` ~300 dòng.
