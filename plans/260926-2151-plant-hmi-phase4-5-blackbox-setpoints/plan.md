# Plant HMI phase 4 + 5: mở hộp đen ComfyUI, setpoint điều khiển ngược

Trạng thái: ĐÃ TRIỂN KHAI 2026-09-26, đã chạy thật. Phase trước: `plans/260926-2051-plant-hmi-phase3-historian-replay/`.

## Phase 4: hộp đen P-601 (ComfyUI) — subagent A
Pipeline gửi prompt KHÔNG kèm client_id → ComfyUI chỉ broadcast `status`, `progress`, `progress_state` tới mọi
client `/ws` (spec ban đầu đoán cả `executing/execution_*`; ghi thực tế cho thấy không có). Backend chỉ
lắng nghe (read-only), không sửa pipeline hay ComfyUI.
- `plant_hmi/plant_comfyui_progress_observer.py`: luồng nền, `ws://{host}:{port}/ws?clientId=plant-hmi-observer-<uuid>`
  (host/port từ `batch-config.yaml`, section `comfyui`), reconnect backoff 5→60 s, bỏ qua frame nhị phân (preview).
  Tên node lấy từ file workflow trong config (`comfyui.workflow_path`: id → `_meta.title` / `class_type`).
  API: `start_observer()` (idempotent), `current_progress() -> dict`.
- Hàm thuần `compute_comfy_progress(state, now)` → `{connected, phase: idle|executing, prompt_id, node, node_title,
  step, steps, it_s, elapsed_s, last_event_ts, last_prompt_s, prompts_1h}`; chưa biết thì `None` (không bịa %).
- `plant_hmi/plant_comfyui_progress_routes.py`: `GET /plant-hmi/api/comfyui/progress` → dict trên.
- `static/plant-hmi-comfyui-progress-panel.js`: `initComfyProgressPanel(container)` tự poll 1 s (visiblePolling),
  hiện node, thanh bước value/max, it/s, thời gian; mất kết nối → "không quan sát được". CSS riêng
  `static/plant-hmi-comfyui-progress.css`.
- Test `pipeline/tests/test-plant-hmi-comfyui-progress.py` dựa trên mẫu message THẬT ghi từ ComfyUI đang chạy.
- Phụ thuộc mới: `websocket-client` (thêm vào `pipeline/requirements.txt`).

## Phase 5: setpoint — subagent B
Knob đầu tiên: `sampler_steps` (SP-601), bước sampler KSampler, recipe từ `sampler.steps` trong YAML.
- `plant_hmi/plant_setpoints.py`: REGISTRY `{sampler_steps: env PLANT_SP_SAMPLER_STEPS, min 10, max 40,
  unit "bước", applies "next_batch", config ("sampler","steps")}`. `resolve(key, recipe_value, environ)` →
  `(value, source)`: env (LOCAL) > store (REMOTE) > recipe (giá trị YAML). Không bao giờ raise.
  Store `plant_hmi/setpoints/setpoints.json` (tmp + os.replace, có lock), audit `setpoints-audit.jsonl`.
- Emitter: `emit_config(record)` ghi `kind=config`, `tag=SP-601`.
- `batch-production-main.py` (file CRLF, giữ nguyên CRLF): resolve ngay sau `load_config`, trước scheduler;
  sau khi scheduler dựng xong emit giá trị scheduler THỰC SỰ dùng + source.
- Collector: giữ bản ghi config mới nhất theo run (ngoài buffer); `config_for(pid, start_ts)` (chống tái dùng pid).
- `plant_hmi/plant_setpoint_routes.py`: `GET /plant-hmi/api/control/setpoints` →
  `[{key,label,unit,sp,pv,pv_pid,pv_source,min,max,recipe,updated_at,updated_by,applies}]`;
  `PUT /plant-hmi/api/control/setpoints/{key}` body `{value:int strict, reason ≤200}` → 422 ngoài khoảng/không phải int,
  bắt buộc header `X-Plant-HMI: 1` (chặn request từ origin khác); `GET /plant-hmi/api/control/audit?limit=`.
  Không có đăng nhập (người dùng đã quyết), `updated_by` = IP client.
- `static/plant-hmi-setpoint-faceplate.js`: `initSetpointFaceplate(container)` poll 5 s: SP và PV cạnh nhau,
  badge nguồn PV (LOCAL/REMOTE/RECIPE), giới hạn, lần đổi cuối, stepper + lý do, Arm → Xác nhận/Huỷ,
  "áp dụng từ batch sau", cảnh báo SP ≠ PV, danh sách audit. CSS riêng `static/plant-hmi-setpoint-faceplate.css`.
- Test `pipeline/tests/test-plant-hmi-setpoints.py`.

## Main
- Đo R9: pilot 12 ảnh ở steps 15 và 25, so KI-601 (s/ảnh) để chứng minh knob có tác động đo được.
- Gắn router + `start_observer()` trong `attach_plant_hmi`; thêm container, link CSS, lời gọi init vào
  `plant-hmi.html`/`plant-hmi-app.js`; snapshot thêm `comfy_progress`; alarm `COMFY_STALLED`
  (đang executing, không có message tiến độ > 60 s).
- Restart service, kiểm tra thật theo checklist phase 4 + 5 (mọi đường khởi chạy: Gradio, CLI, systemd-run).

## Kết quả
- 86 unit test đạt (alarm 18, telemetry 16, historian 21, comfyui-progress 9, setpoints 22).
- Phase 4: ComfyUI chỉ broadcast `status`, `progress`, `progress_state` (không có `executing` khi prompt thiếu client_id);
  panel thật: SaveImage, 15/15 bước, ~10 it/s, prompt 2,3-2,6 s. Tên node = class_type (workflow không có `_meta.title`).
- Phase 5, bảo vệ API: thiếu header → 403; 99 → 422; 15.0 → 422; audit ghi IP + lý do.
- Phase 5, SP/PV trên 4 batch thật (CLI qua systemd-run, cấu hình chỉ crack, 12 ảnh):

| Lượt | Cách đặt | PV tiến trình báo | KI-601 p50 | Nhịp ổn định |
|---|---|---|---|---|
| 1 | SP 15 từ HMI | 15, setpoint (REMOTE) | 4,02 s | 5,63 s/ảnh |
| 2 | SP 25 từ HMI | 25, setpoint | 5,04 s | 6,94 s/ảnh |
| 3 | env PLANT_SP_SAMPLER_STEPS=15 (SP vẫn 25) | 15, env (LOCAL) | 4,05 s | 6,16 s/ảnh |
| 4 | SP 25 từ HMI | 25, setpoint | 5,03 s | 7,11 s/ảnh |

- Đổi SP giữa lượt 1 (15 → 25): faceplate hiện SP 25 / PV 15 + cảnh báo "áp dụng từ batch sau".
- R9: mỗi bước sampler tốn ~0,1 s ComfyUI; 25 → 15 bước giảm ~20% thời gian ComfyUI, ~13% nhịp mỗi ảnh.
  Lần đo đầu (pilot 12 defect) KI-601 6-7 s: thêm ~2 s mỗi ảnh khi đổi LoRA giữa các prompt.
- Sự cố trong lúc làm: 2 lượt R9 đầu lỗi import vì subagent phase 5 đang sửa `batch-production-main.py`.

## Còn mở
- Chưa kiểm đường khởi chạy Gradio (tab Generation) bằng batch thật: nó ghi ảnh vào silo chính `output/synthetic`.
  Resolve nằm trong tiến trình batch nên dùng chung đoạn code với CLI/systemd-run.
- Knob có tác động lớn hơn có thể là thứ tự job theo defect (giảm đổi LoRA), cần đo trước khi làm knob.

## Review phase 4 + 5 và xử lý (22:30)
- Sửa song song: phase 5 (H1 CSRF, H2 mất focus ô lý do, L1, M3 DELETE về RECIPE, M4 PV sau restart/24 h, L3, L4, L7);
  phase 4 (M1 prompt lạ → `busy_foreign`, `step_seen`/`node_class`, L5 kết nối lại 3 s, L6, L9); main (M2: COMFY_STALLED
  120 s, LO khi đang nạp model/chưa có bước, thông báo có hành động).
- Kiểm tra thật: Host LAN + Origin lạ → 403; Sec-Fetch-Site cross-site → 403; cùng origin → 200; DELETE → SP = recipe;
  gõ lý do tiếng Việt giữ focus qua lượt poll; batch 12/12 sau DELETE: PV 25, nguồn RECIPE.
- 105 unit test đạt (alarm 18, telemetry 16, historian 21, comfyui-progress 12, setpoints 38).
- Không làm: GET /queue qua HTTP để xác nhận prompt đang chạy (tuỳ chọn, M1 đã đủ bằng logic thuần).
