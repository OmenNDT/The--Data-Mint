# Phase 07 — Thông Lượng & Dọn Nợ Kỹ Thuật

**Ưu tiên**: P2 · **Trạng thái**: ⏳ Chưa bắt đầu · **Ước lượng**: 10h · **Phụ thuộc**: Phase 06

## Context Links

- [plan.md](./plan.md) · [Hiện trạng](../../docs/pipeline-generation-current.md) mục 7–8
- Bộ nhớ dự án: chạy batch dài phải qua `systemd-run` (Bash background bị SIGTERM); backend Gradio là `tdm-backend.service`

## Overview

Sau khi chất lượng đã đạt, mở thông lượng và dọn phần nợ đã tích. Vòng lặp hiện hoàn toàn tuần tự: GPU nằm không trong lúc upload, download, sinh mask và hậu xử lý — và Phase 05 còn nhân chi phí lên theo số khuyết tật/ảnh.

## Key Insights

- Vòng lặp hiện: sinh mask (CPU) → upload → queue → poll 1 s → download → post-process (CPU). GPU chỉ bận ở khoảng giữa. Ước tính GPU rảnh 40–55% thời gian.
- ComfyUI cho phép xếp nhiều prompt vào hàng đợi; giữ độ sâu hàng đợi 3–4 là đủ để GPU không đói.
- `poll_interval=1.0` cộng dồn đáng kể khi mỗi ảnh chỉ mất vài giây — nên dùng WebSocket của ComfyUI thay vì poll REST.
- Nợ cụ thể: hai bản `mask-prefetch-worker-pool.py` và `mask_prefetch_worker_pool.py` cùng tồn tại (bản gạch nối đã chết vì chuyển sang inline); 6 file `batch-config-*.yaml` rời rạc; `pipeline/gr` (17 MB) và `pipeline/re` (12 MB) là file PostScript do ImageMagick xuất nhầm, lọt vào cây thư mục; docs dừng ở 2026-03 trong khi code đã đi tới 2026-07.
- Có cluster 2 node (x99 + avocado) — avocado 1080Ti 11GB có thể gánh phần sinh ảnh SD1.5 512² song song.

## Requirements

**Chức năng**
- Kiến trúc 3 giai đoạn chạy chồng nhau: sinh mask (process pool) → gửi/nhận ComfyUI (async) → hậu xử lý (thread pool).
- Giữ độ sâu hàng đợi ComfyUI cấu hình được.
- Theo dõi hoàn tất qua WebSocket, có đường lùi về poll REST.
- Gộp module trùng, gộp config, dọn file rác.
- Cập nhật `docs/` theo quy trình tài liệu của dự án.

**Phi chức năng**
- Checkpoint/resume vẫn đúng khi có nhiều job bay cùng lúc.
- Thứ tự ghi file không phụ thuộc thứ tự hoàn tất.

## Architecture

```
pipeline/batch_manager/
├── async-generation-pipeline.py    # MỚI: 3 giai đoạn chồng nhau, hàng đợi có biên
├── comfyui-websocket-client.py     # MỚI: theo dõi qua WS, lùi về REST
├── mask_prefetch_worker_pool.py    # GIỮ (bản dùng thật)
└── mask-prefetch-worker-pool.py    # XOÁ (bản chết)

pipeline/config/
├── batch-config.yaml               # gộp, thêm khối profiles:
└── profiles/                       # gdxray / riawelc / pilot300 / benchmark
```

## Related Code Files

**Tạo**: `async-generation-pipeline.py`, `comfyui-websocket-client.py`, `pipeline/config/profiles/*.yaml`
**Sửa**: `batch-production-main.py` (dùng pipeline async), `comfyui-rest-api-client.py` (tách phần đồng bộ), `checkpoint-state-manager.py` (chốt theo job đã ghi xong, không theo chỉ số hàng đợi), `launcher/generation_process_manager.py`
**Xoá**: `pipeline/batch_manager/mask-prefetch-worker-pool.py`, `pipeline/gr`, `pipeline/re`, các `batch-config-*.yaml` rời sau khi gộp
**Cập nhật docs**: `docs/system-architecture.md`, `docs/codebase-summary.md`, `docs/project-roadmap.md`, `docs/pipeline-generation-current.md`, `README.md` (đường dẫn còn ghi `/mnt/e/...` trong khi thực tế là `/home/sontn/Projects/The Data Mint`)

## Implementation Steps

1. Đo mốc: dựng hồ sơ thời gian từng giai đoạn trên 200 ảnh, xác nhận tỉ lệ GPU rảnh.
2. `comfyui-websocket-client.py`: theo dõi `executing`/`executed` qua WS, lùi về poll REST khi WS lỗi.
3. `async-generation-pipeline.py`: 3 giai đoạn với hàng đợi có biên (`asyncio.Queue` maxsize) + `ProcessPoolExecutor` cho mask + `ThreadPoolExecutor` cho hậu xử lý.
4. Độ sâu hàng đợi ComfyUI cấu hình được (`performance.queue_depth`, mặc định 3).
5. Sửa checkpoint: chỉ chốt job đã ghi xong file; job bay dở khi ngắt thì sinh lại.
6. Nối vào `batch-production-main.py`, giữ cờ `--sequential` làm đường lùi.
7. Đo lại thông lượng, so mốc.
8. Xoá `mask-prefetch-worker-pool.py`, sửa `batch_manager/__init__.py`.
9. Gộp 6 `batch-config-*.yaml` thành `batch-config.yaml` + `profiles/`; cập nhật launcher và script.
10. Xoá `pipeline/gr`, `pipeline/re`; rà `.gitignore`.
11. Cập nhật 5 tài liệu trong `docs/` + sửa đường dẫn `/mnt/e/...` trong `README.md`.
12. (Tuỳ chọn) Thử phân tán sang avocado (`100.80.21.42`) — rsync code + model, chạy ComfyUI riêng, scheduler ghi ra hai endpoint.

## Todo List

- [ ] Hồ sơ thời gian từng giai đoạn (mốc)
- [ ] `comfyui-websocket-client.py` + đường lùi REST
- [ ] `async-generation-pipeline.py` 3 giai đoạn
- [ ] `performance.queue_depth` cấu hình được
- [ ] Checkpoint đúng khi chạy async
- [ ] Cờ `--sequential` đường lùi
- [ ] Đo lại thông lượng
- [ ] Xoá `mask-prefetch-worker-pool.py`, sửa `__init__.py`
- [ ] Gộp config thành `profiles/`
- [ ] Xoá `pipeline/gr`, `pipeline/re`, rà `.gitignore`
- [ ] Cập nhật 5 tài liệu + README
- [ ] (Tuỳ chọn) Thử node avocado

## Success Criteria

- Thông lượng **≥ 2.500 ảnh/giờ** ở chế độ một khuyết tật (từ ~1.097).
- GPU rảnh < 15% thời gian chạy.
- Ngắt giữa chừng rồi resume: không mất ảnh, không trùng ảnh (kiểm bằng đếm + băm tên).
- `--sequential` cho kết quả giống hệt đường async với cùng seed.
- Không còn module trùng; `pipeline/` không còn file rác > 1 MB không thuộc mã nguồn.
- 5 tài liệu trong `docs/` phản ánh đúng mã nguồn tại thời điểm chốt.

## Risk Assessment

| Rủi ro | Giảm thiểu |
|---|---|
| Async làm checkpoint sai, resume mất/trùng ảnh | Chỉ chốt job đã ghi file; thêm test ngắt–resume tự động |
| Hàng đợi sâu làm ComfyUI hết VRAM (nhất là khi có Phase 05) | Giới hạn `queue_depth`, giám sát VRAM, hạ tự động khi vượt ngưỡng |
| Gộp config phá script/launcher đang dùng | Giữ shim đọc file cũ trong một vòng phát hành, cảnh báo khi dùng |
| Xoá nhầm file người dùng cần | Kiểm nội dung `pipeline/gr` và `pipeline/re` trước khi xoá, hỏi lại nếu không rõ |
| Node avocado (1080Ti 11GB) không đủ VRAM | Coi là tuỳ chọn, chỉ bật nếu thử nghiệm 512² chạy ổn |

## Security Considerations

Không đẩy dotenv/khoá lên git. Khi rsync sang avocado chỉ chuyển mã nguồn và model, không chuyển dữ liệu định danh. Endpoint ComfyUI chỉ nghe trên Tailscale, không mở ra public.

## Next Steps

Chốt xong Phase 07 → chạy sản xuất lại toàn bộ dataset với cấu hình mới, rồi chạy Phase 9 (YOLOv8) để so mAP với dataset cũ.
