# Plant HMI phase 2: telemetry trong tiến trình, hạt trong ống, đồng hồ KI

Trạng thái: ĐÃ TRIỂN KHAI 2026-09-26, đã chạy thật. Skill: `software-plant-hmi`. Phase trước:
`plans/260926-1959-plant-hmi-phase1-static-pid-poller/`.

## Phát hiện đầu phase (mục 1 người dùng hỏi)
- ComfyUI chạy chung máy với pipeline. `10.86.201.250` là IP Wi-Fi cũ của chính máy này
  (DHCP đã đổi `wls1` sang `10.86.202.67`), nên mọi batch sẽ lỗi kết nối.
- Đã đổi `comfyui.host` sang `127.0.0.1` trong 7 file `pipeline/config/*.yaml` (+ `_generated/effective-run-config.yaml`).
- U-901 (RTX 3090) là GPU của bơm P-601: GPU_HOT đo đúng máy.
- ComfyUI chạy bằng `comfyui/.venv`; port 8188 đã đăng ký vào `start-servers.sh` (khởi động theo nhu cầu).

## Kiến trúc
```
batch-production-main.py ── instrument() ──> plant_hmi/telemetry/batch-<pid>-<start>.jsonl
  R-201 mask · P-601 upload/queue/infer/download · R-401 post · U-901 thermal_hold · job ok/retry/failed
backend: plant_telemetry_collector (tail, buffer 15 phút, bộ đếm theo run)
       └> plant_flow_metrics.compute_flows (thuần) ─> /api/snapshot (flows, KI, alarm)
       └> /api/events?since= ─> plant-hmi-particle-layer.js (1 hạt = 1 job, trễ 4 s)
```
Sửa pipeline: chỉ thêm ~25 dòng trong `batch-production-main.py` (wrap tại chỗ khởi tạo, `set_job`,
`job_outcome`). `PLANT_TELEMETRY=0` tắt hẳn.

## Alarm mới
| Code | Điều kiện | Mức |
|---|---|---|
| COMFY_DOWN | như phase 1, thông báo phân biệt "chưa chạy" / "đang chạy nhưng không trả lời" | LO/HI |
| COMFY_HOST_NOT_LOCAL | host trong config không phải địa chỉ của máy này | LO |
| JOB_ERRORS | retry + job hỏng >= 3 trong 15 phút (HI nếu có job hỏng) | LO/HI |
| THERMAL_HOLD | batch chờ GPU nguội; tạm chặn PUMP_WEDGED | LO |

Đồng hồ: KI-201 (s/mask), KI-601 (s/ảnh ComfyUI), KI-401 (s hậu xử lý), p50 trong 5 phút.
D-901 lấy số job hỏng trực tiếp từ telemetry (checkpoint chỉ là dự phòng). LT-102 trừ cả job hỏng.

## Kết quả kiểm tra
- 28 unit test đạt (11 test mới trong `test-plant-hmi-telemetry.py` + 17 test cũ).
- Pilot thật 12/12 ảnh: 12 bản ghi `ok` khớp log; KI-601 ≈ 6 s, KI-401 0,1 s; hạt đứng ở P-601 khi ComfyUI đang xử lý.
- Tắt ComfyUI giữa run 30 ảnh: COMFY_DOWN HI ("chưa chạy trên máy này") + JOB_ERRORS HI (15 retry, 4 hỏng),
  hạt đỏ ở bơm, D-901 = 4.
- SIGKILL batch giữa lúc retry: không còn lời gọi đang chạy, không còn hạt ma (đã sửa lỗi hạt ma của job đang ngủ chờ retry).
- Sau khi batch kết thúc: không có báo động giả.

## Còn mở
- Lỗi có sẵn trong `start-servers.sh` dòng 49-50: hàm `open_all_tabs() { }` rỗng, `bash -n` báo lỗi cú pháp. Chưa sửa (ngoài phạm vi).
- Ảnh thử nằm ở `output/plant-hmi-pilot/` (15 ảnh), config `pipeline/config/_generated/plant-hmi-pilot.yaml`.
- Phase 3 (historian + replay + trend) chưa làm.
