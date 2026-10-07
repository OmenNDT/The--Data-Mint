# Pipeline Sinh Ảnh — Hiện Trạng (As-Is)

**Cập nhật**: 2026-08-09 · **Phạm vi**: Phase 6 (batch generation) · **Entry**: `pipeline/batch_manager/batch-production-main.py`

---

## 1. Luồng tổng thể

```
batch-config.yaml
      │
      ▼
BatchJobScheduler ──► job list (defect_type, seed, background_image) ──► shuffle
      │
      ▼   [vòng lặp tuần tự, 1 ảnh / lượt]
 ┌────────────────────────────────────────────────────────────────┐
 │ 1. Thermal check (nvidia-smi, pause ≥85°C, resume ≤75°C)       │
 │ 2. Sinh mask inline: _generate_mask_worker(type, seed, bg)      │
 │      ├─ _detect_weld_center_y(bg)  → hàng sáng nhất = tâm mối   │
 │      ├─ <Type>MaskGenerator.generate() → binary + feathered     │
 │      ├─ annotation mask (thin, binary)   → ground truth         │
 │      └─ inpaint mask = dilate(k=21,ellipse) + blur(7)           │
 │ 3. Upload background + inpaint mask lên ComfyUI (REST)          │
 │ 4. build_workflow(): patch node JSON theo defect                │
 │ 5. queue_prompt → poll_completion (1s, timeout 300s)            │
 │ 6. download ảnh kết quả                                         │
 │ 7. apply_dark_defect_convention()   ← post-process cưỡng bức    │
 │ 8. Lưu ảnh + annotation mask + metadata JSON                    │
 │ 9. Checkpoint mỗi 100 ảnh                                       │
 └────────────────────────────────────────────────────────────────┘
      │
      ▼
output/synthetic/{defect_type}/{defect}_{job_id:06d}.png (+ _mask.png, .json)
```

---

## 2. Thành phần

| Khối | File | Vai trò |
|------|------|---------|
| Orchestrator | `batch_manager/batch-production-main.py` (425 L) | Vòng lặp chính, retry, checkpoint, post-process |
| Scheduler | `batch_manager/batch-job-scheduler.py` (281 L) | Job list theo `defect_distribution`, patch workflow JSON |
| API client | `batch_manager/comfyui-rest-api-client.py` (197 L) | upload / queue / poll / download |
| Mask worker | `batch_manager/mask_prefetch_worker_pool.py` (258 L) | Sinh mask, dò tâm mối hàn, dilate |
| Mask generators | `mask_generator/*.py` (12 lớp, 1.809 L) | Mask thủ tục theo hình thái từng khuyết tật |
| Thermal | `batch_manager/gpu-thermal-monitor.py` | Ngưỡng nhiệt GPU |
| Checkpoint | `batch_manager/checkpoint-state-manager.py` | Resume sau gián đoạn |
| UI | `launcher/gradio_launcher_app.py` + panels (6.259 L) | One-click launcher, chạy như `tdm-backend.service` |

---

## 3. ComfyUI workflow (`sd15-lora-controlnet-inpaint-batch-api-workflow.json`)

```
[1] CheckpointLoaderSimple (sd-v1-5-pruned-emaonly)
      ↓
[2] LoraLoader (xray_{defect}_lora_r32, strength 0.7–1.0)
      ↓
[3] CLIPTextEncode positive     [4] CLIPTextEncode negative (per-class)
      ↓                               ↓
[5] LoadImage background   [6] LoadImage mask ──► [13] ImageToMask (red)
      ↓                               ↓
[8] InpaintModelConditioning (noise_mask=true)
      ↓
[9] ControlNetApplyAdvanced (control_v11p_sd15_inpaint, strength 0.8)
      ↓
[10] KSampler (euler/normal, steps 25, cfg 9.0, denoise 0.85–0.90)
      ↓
[11] VAEDecode → [12] SaveImage
```

---

## 4. Cấu hình đang dùng (`config/batch-config.yaml`)

- **ComfyUI**: `10.86.201.250:8188`
- **12 lớp khuyết tật**, phân bố đều 0.1 (tổng > 1.0 — số ảnh thực = `total × ratio` mỗi lớp)
- **Backgrounds**: `dataset/processed/patches_512_Confimed/clean` — 827 patch 512×512
- **Sampler**: euler / normal / 25 steps / cfg 9.0
- **Reliability**: 3 retry, checkpoint mỗi 100 ảnh, timeout 300 s
- **LoRA**: 12 file `xray_*_lora_r32.safetensors` (+ biến thể `_riawelc_`, `_medxray_`, `_absreal_`… cho benchmark)

---

## 5. Hai đường mask song song

| Mask | Sinh ra sao | Dùng để |
|------|-------------|---------|
| **Annotation** | binary mảnh, gốc | Ground truth → COCO/YOLO, và làm mask darken ở bước 7 |
| **Inpaint** | dilate ellipse k=21 + blur 7 | Đưa vào ComfyUI để SD có đủ diện tích vẽ |

Chênh lệch giữa hai mask tạo một vành đai nơi LoRA vẽ ra quầng sáng (halo) — đây chính là lý do tồn tại của bước 7.

---

## 6. Bước post-process quyết định diện mạo ảnh

`apply_dark_defect_convention()` — `batch-production-main.py:56-118`

```python
# Bước 1: thay CỨNG mọi pixel ngoài annotation mask bằng background gốc
keep = gaussian(mask, sigma=1.5) / 255
img = img * keep + bg * (1 - keep)

# Bước 2: làm tối lòng khuyết tật theo quy ước RT (void = đen)
darken = gaussian(mask, sigma=2.0) / 255
img = img * (1 - darken * S)        # S = 0.92 mặc định
                                     # 0.85 lack_of_fusion · 0.78 lack_of_penetration
                                     # 0.65 elongated_cavity · bỏ qua metallic_inclusion
```

**Hệ quả**: ảnh cuối ≈ `background gốc` + `hình dạng mask nhân hệ số tối`. Phần lớn nội dung do SD1.5 + LoRA sinh ra bị ghi đè. Diện mạo khuyết tật do **mask thủ tục** quyết định, không phải do diffusion.

---

## 7. Đặc tính vận hành

| Chỉ số | Giá trị |
|--------|---------|
| Thông lượng | ~1.097 ảnh/giờ (tuần tự, 1 prompt/lượt) |
| Song song | Không — GPU rảnh trong lúc upload/download/post-process |
| Khuyết tật / ảnh | Đúng 1 |
| Ảnh âm tính (no-defect) | Không có |
| Độ phân giải | Cố định 512×512 grayscale |
| Kiểm định trong vòng lặp | Không (FID/SSIM chỉ chạy hậu kỳ ở `qa/` và `benchmark/`) |

---

## 8. Hạn chế đã quan sát được

Từ mã nguồn và ảnh mẫu `output/10class.png`:

1. **Diffusion bị vô hiệu hoá** — bước 7 ghi đè output của SD (mục 6).
2. **Cạnh cứng, không có penumbra** — mask nhị phân → biên khuyết tật sắc nét, thiếu bán dạ hình học và MTF của phim/detector.
3. **Không liên tục hạt nhiễu** — lòng khuyết tật mịn hơn vùng xung quanh vì bị nhân hệ số thay vì tái tạo nhiễu lượng tử.
4. **Mật độ phẳng** — nhân một hệ số cố định → không có gradient độ dày như khuyết tật thật.
5. **Sai quy ước ở vài lớp** — `lack_of_penetration` trong ảnh mẫu hiện thành dải **sáng**; `metallic_inclusion` là đa giác trắng đặc.
6. **Nhãn không khớp ảnh thực sinh** — nhãn lấy từ mask đầu vào, không đo từ khuyết tật thực tế xuất hiện.
7. **Nợ kỹ thuật** — hai bản `mask-prefetch-worker-pool.py` / `mask_prefetch_worker_pool.py` cùng tồn tại; prefetch pool đã bị bỏ qua (chuyển sang inline); 6 file `batch-config-*.yaml` rời rạc; docs dừng ở 2026-03.

---

## 9. Tài liệu liên quan

- [System Architecture](./system-architecture.md) · [Codebase Summary](./codebase-summary.md) · [Roadmap](./project-roadmap.md) · [Benchmark](./benchmark.md)
- Sơ đồ dữ liệu: `docs/batch-pipeline-dataflow.html`
