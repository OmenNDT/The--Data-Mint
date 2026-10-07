# Plant HMI phase 1: P&ID tĩnh + poller mức 1 (không sửa pipeline)

Trạng thái: ĐÃ TRIỂN KHAI 2026-09-26 (chờ chạy batch thật khi ComfyUI bật lại). Skill: `software-plant-hmi`.

## 1. Inventory (khảo sát chỉ đọc, 2026-09-26)

**Công đoạn sinh ảnh (Phase 6, lõi nhà máy)**, `batch_manager/batch-production-main.py`, chạy TUẦN TỰ 1 job/lần:
`scheduler.get_next_job` → sinh mask inline (CPU) → upload nền + mask lên ComfyUI → `queue_prompt`
→ `poll_completion` (timeout 300 s) → download → dark-convention post-proc → lưu mask/metadata
→ `mark_complete`; lỗi thì retry 3 lần (delay 5 s) rồi `mark_failed`.

**Nguồn trạng thái sẵn có**
| Nguồn | Đọc được gì | Ghi chú |
|---|---|---|
| `checkpoints/batch_state.json` | current_index, completed_count, failed_jobs, jobs (tổng + defect) | chỉ ghi mỗi 100 ảnh + cuối run |
| thư mục `output_base_dir/<defect>/*.png` | số ảnh thực đã ra theo defect | nguồn level thật, realtime |
| stdout `[c/t] (p%) Job id \| defect \| ETA` | tiến độ từng job | chỉ Gradio đọc (pipe) hoặc journald khi chạy systemd-run |
| `/proc/*/cmdline` | `batch-production-main.py`, `accelerate…train_network` | tiến trình sống + start time |
| ComfyUI `GET /system_stats`, `/queue` | server sống, queue running/pending, VRAM máy ComfyUI | host 10.86.201.250:8188, HIỆN KHÔNG PHẢN HỒI |
| `nvidia-smi` cục bộ | RTX 3090 util/VRAM/nhiệt | dùng bởi kohya training |
| `/proc/meminfo`, `/proc/vmstat`, loadavg | RAM, swap in/out rate, load | |

**Đường khởi chạy**: Gradio tab Generation (Popen, con của `tdm-backend.service`), CLI
`run-batch-production.sh`, `systemd-run --user --unit=tdm-<name>`. Training: Gradio tab Training + CLI.

**Cảnh báo R8**: job sinh ảnh chạy từ Gradio là con trong cgroup `tdm-backend.service`;
restart service để nạp router mới sẽ GIẾT job đang chạy. Luôn kiểm tra job sống và hỏi trước.

## 2. Bảng tag

| Tag | Thiết bị | Đọc từ |
|---|---|---|
| TK-101 | Bồn nền X-ray sạch (backgrounds_dir) | đếm file |
| TK-102 | Bồn job chờ (jobs chưa làm) | checkpoint: total - current_index |
| R-201 | Lò sinh mask thủ tục (CPU, inline) | stdout/proc (phase 2 mới đo được) |
| P-601 | Bơm ComfyUI inpaint (N=1, tuần tự) | tiến trình batch sống + ComfyUI queue |
| R-401 | Lò hậu xử lý dark-convention | phase 2 |
| TK-801 | Silo ảnh tổng hợp (theo defect) | đếm PNG theo thư mục defect |
| D-901 | Bồn xả job lỗi | checkpoint.failed_jobs |
| U-901 | GPU cục bộ 3090 | nvidia-smi |
| U-902 | Máy chủ ComfyUI | /system_stats |
| U-903 | RAM / swap / load | /proc |
| (tách) R-501 | Lò train LoRA kohya | pgrep train_network |

Instrument phase 1: LT-102 (job chờ), LT-801 (ảnh/defect), SI-601 (ảnh/giờ từ delta đếm PNG 10 phút), XI-601 (job đang chạy).

## 3. Alarm phase 1

| Code | Điều kiện | Mức | On-delay |
|---|---|---|---|
| COMFY_DOWN | /system_stats lỗi/timeout | HI khi có batch sống, LO khi không | 15 s |
| PUMP_WEDGED | batch sống, số PNG không tăng > 10 phút | HI | 600 s |
| STALE_CHECKPOINT | batch_state.json chưa xong (current_index < total), không tiến trình batch | LO | 60 s |
| GPU_HOT | 3090 > 85°C | HI | 30 s |
| MEM_LOW / SWAP_THRASH | RAM avail < 10% / swap pages/s cao | HI | 0 / 10 s |

## 4. Kiến trúc (không thêm port)

- `pipeline/plant_hmi/` (mỗi file < 200 dòng): `plant_host_readers.py`, `plant_production_readers.py`,
  `plant_slow_probes.py`, `plant_alarm_rules.py` (thuần: `derive_alarms` + `AlarmOnDelay`),
  `plant_snapshot_builder.py`, `plant_hmi_routes.py`; `static/` (HTML, CSS, 2 module JS).
- Mount router + trang tĩnh vào app FastAPI mà Gradio đang chạy (port 7860): `/plant-hmi/` và
  `/plant-hmi/api/snapshot`. Không cần đăng ký port mới.
- UI: 1 trang HTML + SVG + JS thuần (dự án không có React), Dark Neumorphism, poll 3 s khi tab hiển thị.
- Link từ Gradio sang trang HMI.

## 5. Tiêu chí xong
- Snapshot < 300 ms, probe chậm (ComfyUI, nvidia-smi) cache + single-flight.
- Dừng ComfyUI (hoặc hiện trạng offline) → COMFY_DOWN hiện sau 15 s.
- Chạy 1 batch thật 20 ảnh: P-601 teal, LT-801 tăng, không báo động giả lúc start/finish.
- Unit test cho `derive_alarms` + `AlarmOnDelay`.

## Quyết định
- Phạm vi: chỉ khu sinh ảnh. HMI gắn vào Gradio 7860, không thêm port.
- Bỏ FAIL_RATE khỏi phase 1: số job lỗi chỉ có trong checkpoint (ghi mỗi 100 ảnh), chuyển sang phase 2 khi có telemetry.

## Kết quả kiểm tra
- 13/13 unit test (`pipeline/tests/test-plant-hmi-alarm-rules.py`).
- Snapshot 80-140 ms. COMFY_DOWN LO hiện sau 15 s khi ComfyUI tắt, tự nâng HI khi có batch sống (giữ nguyên `since`).
- Nhận diện tiến trình batch (pilot, target, config tương đối) đúng với tiến trình thử mang tên script.
- Chưa làm: chạy batch 20 ảnh thật (ComfyUI 10.86.201.250 đang tắt).

## Review (code-reviewer, 2026-09-26) và xử lý
- Đã sửa: H1 (silo không đọc được thì không báo PUMP_WEDGED), H2 (probe treo > 20 s trả về "chưa rõ"),
  M1 (YAML/checkpoint sai kiểu không làm hỏng snapshot), M3 (checkpoint chỉ parse lại khi mtime/size đổi, giới hạn 300 MB),
  M4 (cache single-flight theo key), M5 (reading "chưa rõ" giữ timer on-delay, không reset),
  L1 (swap dùng monotonic), L2 (bỏ tiến trình con fork), L3 (config tương đối + cwd không đọc được thì "chưa rõ"),
  L4 (500 không trả nội dung exception), L5 (config phải là file thường, tối đa 1 MB).
- Bổ sung: batch có config "chưa rõ" không còn rơi về config gốc.
- 17/17 unit test đạt.
- Còn mở: M2 (tiến độ/ETA sai khi resume từ checkpoint), L6 (silo idle không có thang mức), L7/L8 (không đáng kể).
