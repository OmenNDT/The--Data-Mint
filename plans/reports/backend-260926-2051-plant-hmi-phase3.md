# Plant HMI phase 3 backend: historian + history API

## Phạm vi
Historian SQLite + sampler daemon + history HTTP API theo hợp đồng cố định trong
`plans/260926-2051-plant-hmi-phase3-historian-replay/plan.md`.

## File tạo mới
- `pipeline/plant_hmi/plant_historian_store.py` (185 dòng): SQLite WAL tại
  `plant_hmi/historian/plant-historian.sqlite`, bảng `samples(ts, tag, value)` index
  (tag, ts), `alarm_journal(ts, code, tag, severity, pid, state, message)`. Bucket
  query tự chọn step (`_STEP_CANDIDATES`, ≤500 điểm/series). Prune 30 ngày, chunk 5000
  qua `rowid IN (SELECT ... LIMIT 5000)`. Kết nối riêng mỗi thread (`threading.local`),
  mọi write tự nuốt lỗi, log một lần theo loại lỗi (`_log_once`).
- `pipeline/plant_hmi/plant_historian_sampler.py` (182 dòng): `TAG_CATALOGUE` (18 tag,
  nhãn tiếng Việt), `extract_tag_values()` thuần (None bị bỏ qua, `comfy_up` chỉ 1/0 khi
  `ok` là bool), `start_sampler()` idempotent (lock + cờ `_started`), interval từ
  `PLANT_HISTORIAN_INTERVAL_S` (mặc định 10s, giá trị hỏng → warn + mặc định). Mỗi tick
  diff khoá alarm (`AlarmOnDelay.key`) với tick trước để ghi `raised`/`cleared`. Toàn bộ
  vòng lặp bọc try/except, không bao giờ thoát ra ngoài.
- `pipeline/plant_hmi/plant_history_routes.py` (160 dòng): router `/api/history` với
  `tags`, `samples`, `alarms`, `runs`, `events` đúng hình dạng hợp đồng. `runs`/`events`
  đọc thẳng file JSONL trong `TELEMETRY_DIR` (bỏ dòng hỏng/không phải dict, chỉ nhận
  kind enter/exit/job), cache theo (path, size, mtime). Validate `from <= to`, `limit`
  chặn trần (events ≤5000, alarms ≤2000); tên `run` qua `Path(...).name` chặn path
  traversal. Lỗi trả JSON 4xx/5xx, không lộ traceback.
- `pipeline/tests/test-plant-hmi-historian.py` (199 dòng): 17 test case (bucketing,
  auto-step, None không thành 0, prune chỉ xoá hàng cũ, write không bao giờ raise khi
  đĩa hỏng, extract_tag_values, journal raise/clear + không lặp khi alarm còn treo,
  events paging + next_from, dòng hỏng bị bỏ, chặn path traversal, from>to trả 400).

## File sửa (theo giới hạn cho phép)
- `pipeline/plant_hmi/plant_hmi_routes.py`: chỉ thêm import + 2 dòng trong
  `attach_plant_hmi()` (gắn `history_router` prefix `/plant-hmi`, gọi `start_sampler()`).
  Không đụng route/logic khác.

## Điểm cần main session lưu ý khi tích hợp
- GPU/ComfyUI field name không khớp tên tag phẳng: `gpu.vram_used_mib` → chia 1024 ra
  `gpu_vram_used_gib`; `comfy.queue_running` + `comfy.queue_pending` → tổng thành
  `comfy_queue`. Đã xử lý trong `extract_tag_values`, không cần sửa `plant_slow_probes.py`.
- `runs`/`events` không dùng `collector` (bộ nhớ phase 2): đọc file trực tiếp, nên vẫn
  replay được run đã kết thúc trước khi backend khởi động lại.
- Thư mục `plant_hmi/historian/` đã gitignore từ trước; đã xoá file `.sqlite` tạo ra khi
  smoke-test bằng TestClient (không phải qua service thật) để tránh dữ liệu rác.
- Sampler chạy nền ngay khi `attach_plant_hmi()` được gọi (không cần bước khởi động
  riêng); double-attach (đã test) không tạo 2 thread.

## Kiểm thử
- `py_compile` toàn bộ file mới/sửa: OK.
- `.venv/bin/python tests/test-plant-hmi-historian.py`: 17/17 pass.
- `.venv/bin/python tests/test-plant-hmi-alarm-rules.py`: 17/17 pass (không ảnh hưởng).
- `.venv/bin/python tests/test-plant-hmi-telemetry.py`: 15/15 pass (không ảnh hưởng).
- Smoke test thủ công qua `TestClient` với `attach_plant_hmi()` gọi 2 lần: `tags`,
  `samples`, `alarms`, `runs`, `events` đều trả 200 đúng hình dạng; sampler chỉ có 1
  thread `plant-historian-sampler`.

## Chưa làm / không thuộc phạm vi
- Không đụng `plant_hmi_collector`/alarm/snapshot/static (thuộc agent khác hoặc main
  session).
- Không restart `tdm-backend.service`, không chạy batch/ComfyUI thật, không commit.

## Cập nhật 2026-09-26 21:30: sửa theo review code phase 3 (H4, H5, M4, M5, M6, L1-L4, L7)

Sửa cả 4 file thuộc quyền sở hữu, không đụng `static/*` hay file Python khác.

### Đổi hợp đồng (đã chốt trong plan.md trước khi sửa)
`GET events?run=&cursor=&limit=` (bỏ `from`/`to`) → `{"events", "next_cursor": int|null,
"total": int}`. `cursor` là chỉ số (index) trong danh sách sự kiện của run đã sort theo
ts, loại trừ, không trùng/không lặp ở biên trang.

### plant_historian_store.py (199 dòng)
- L2: bỏ cờ `_schema_ready` toàn tiến trình; `_create_schema()` chạy trên MỌI connection
  mới (an toàn nếu file DB bị xoá/tạo lại khi service đang chạy).
- L3: thêm index `ix_samples_ts` riêng (ngoài index ghép (tag, ts)) để `prune_old` không
  full-scan.
- L4: `_finite()` chặn NaN/Inf ở `insert_sample`/`insert_samples`; `query_samples` lọc
  thêm lần nữa (phòng hàng cũ lọt qua trước khi sửa).
- L1: `_log_once` giờ tự re-arm sau 10 phút (`LOG_ONCE_WINDOW_S`), đếm số lỗi bị nén và
  in kèm lần log kế tiếp.
- M6 (nửa store): `query_samples` clamp `step = max(step_yêu_cầu, auto_step)`.
- Hàm mới `latest_alarm_states()`: đọc journal, trả về key còn `raised` (chưa `cleared`)
  cho sampler seed lúc khởi động (M4).

### plant_historian_sampler.py (198 dòng)
- M5: `_journal_alarm_diff` ghi `raised` tại `a["since"]` (thời điểm on-delay thật sự bắt
  đầu), không phải giờ tick quan sát thấy.
- M4: hàm mới `_seed_previous_alarms()` gọi `store.latest_alarm_states()`, nạp vào
  `_previous_alarms` trước khi `start_sampler()` khởi thread; alarm đã hết ở tick đầu
  tiên sau restart tự động ghi `cleared` (tự nhiên từ cơ chế diff, không cần code riêng).
- L7: `job_errors_15m` = `None` khi `flows.has_telemetry` là `False` (trước đây luôn ra
  số, kể cả 0, khi không rõ trạng thái telemetry).

### plant_history_routes.py (198 dòng)
- H4: `/events` chuyển hẳn sang cursor kiểu index; `_sorted_events_for_run()` cache danh
  sách đã sort 1 lần, không sort lại mỗi trang.
- H5: tách 2 cache. `_runs_cache` chỉ giữ aggregate nhỏ (không giữ list sự kiện), khoá
  theo (path, size, mtime), tự xoá key khi file đã mất (`runs()` diff với danh sách file
  còn tồn tại). `_events_lru` (OrderedDict, tối đa 2 run) giữ list sự kiện đầy đủ đã sort;
  khoá `_events_lock` vừa bảo vệ dict vừa single-flight (chỉ 1 luồng parse+sort 1 file
  tại một thời điểm).
- L4: `_has_non_finite()` loại bỏ dòng có field NaN/Inf ngay lúc parse JSONL.
- M6 (nửa route): `/samples` lọc `tags` còn nằm trong `TAG_NAMES`, khử trùng lặp, tối đa
  12 tag (`MAX_SAMPLE_TAGS`), vượt trả 422; tags rỗng/không hợp lệ trả 400.

### tests/test-plant-hmi-historian.py (294 dòng, 20 test case)
Test mới/sửa cho từng phát hiện: step clamp (M6), None/NaN/Inf không bao giờ lưu hay trả
về (L4), `latest_alarm_states` chỉ giữ `raised` (M4), log-once re-arm sau 10 phút + đếm
nén (L1), schema tạo trên connection mới + index `ix_samples_ts` tồn tại (L2, L3), raise
ghi tại `since` còn clear ghi tại giờ tick (M5), seed alarm còn treo không ghi `raised`
lại + ghi `cleared` đúng 1 lần khi hết (M4), cursor paging không trùng/không lặp + ổn
định khi nhiều bản ghi cùng ts + `next_cursor` null khi hết (H4), dòng NaN/hỏng/non-flow
bị bỏ khi parse events (L4), `_runs_cache` xoá key khi xoá file (H5), `_events_lru`
evict run cũ nhất khi vượt `EVENTS_LRU_MAX=2` (H5), chặn path traversal, validate
`tags`/dedupe/cap 12 → 422 (M6).

### Kiểm thử sau sửa
- `py_compile` cả 4 file: OK.
- `tests/test-plant-hmi-historian.py`: 20/20 pass.
- `tests/test-plant-hmi-telemetry.py`: 15/15 pass (không hồi quy).
- `tests/test-plant-hmi-alarm-rules.py`: 17/17 pass (không hồi quy).
- Smoke test `TestClient` qua `attach_plant_hmi()` thật: `events` (contract mới đúng
  hình dạng `next_cursor`/`total`), `samples` (step tự chọn), sampler chỉ 1 thread.
- Không còn file `.sqlite` rác trong `plant_hmi/historian/` sau khi chạy test (đã dọn).

### Line count
`plant_historian_store.py` 199, `plant_historian_sampler.py` 198,
`plant_history_routes.py` 198 (đều <200 theo yêu cầu). `tests/test-plant-hmi-historian.py`
294 dòng: đã nén tối đa (gộp test case, bỏ comment thừa, gộp assertion) nhưng KHÔNG đạt
<200 vì 12 nhóm hành vi mới (H4/H5/M4/M5/M6/L1-L4/L7) đều cần test riêng để không hồi quy
thầm lặng; ưu tiên giữ độ phủ test thay vì cắt bớt case để ép dòng. Nêu rõ ở đây làm sai
lệch so với yêu cầu ban đầu.

Status: DONE
Summary: sửa đủ 9 phát hiện review (H4, H5, M4, M5, M6, L1, L2, L3, L4, L7 — 10 mục) trên
đúng 4 file được giao, không đụng static/service khác; 52 test (20+15+17) đều pass.
Concerns: file test 294 dòng vượt trần 200 do khối lượng case mới đòi hỏi bởi review,
đã nêu rõ trade-off ở trên; chưa live-test qua service thật (nằm ngoài quyền của agent
này, cần main session restart + kiểm tra alarm journal thật sau restart để xác nhận M4
hoạt động đúng với dữ liệu batch thật).
