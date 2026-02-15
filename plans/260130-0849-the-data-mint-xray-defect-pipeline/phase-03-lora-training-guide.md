# Phase 03: LoRA Training Guide / Hướng Dẫn Huấn Luyện LoRA

## Table of Contents / Mục Lục
1. [Prerequisites / Yêu Cầu Tiên Quyết](#prerequisites)
2. [Environment Setup / Thiết Lập Môi Trường](#environment-setup)
3. [Pilot Training / Huấn Luyện Thử Nghiệm](#pilot-training)
4. [Full Training / Huấn Luyện Đầy Đủ](#full-training)
5. [Validation / Kiểm Tra Kết Quả](#validation)
6. [Troubleshooting / Xử Lý Lỗi](#troubleshooting)

---

## Prerequisites / Yêu Cầu Tiên Quyết {#prerequisites}

### Hardware Requirements / Yêu Cầu Phần Cứng
- **GPU**: NVIDIA RTX 3090 24GB (confirmed available)
- **RAM**: 64GB (confirmed available)
- **Storage**: ~50GB free space for training data, outputs, logs

### Software Requirements / Yêu Cầu Phần Mềm
- **Windows 10/11** with PowerShell 5.1+
- **Python 3.10.6** (kohya-ss compatibility)
- **CUDA 11.8** (matching PyTorch version)
- **Git** for cloning repositories
- **kohya-ss** repository cloned at `E:\The Data Mint\kohya-ss\`

### Data Requirements / Yêu Cầu Dữ Liệu
Phase 2 must be completed with training data at:
```
E:\The Data Mint\dataset\processed\patches_512\
├── crack\          (228 images + 228 .txt captions)
├── porosity\       (510 images + 510 .txt captions)
├── inclusion\      (114 images + 114 .txt captions)
├── lack_of_fusion\ (269 images + 269 .txt captions)
├── undercut\       (86 images + 86 .txt captions)
└── clean\          (3524 images + 3524 .txt captions - regularization)
```

### Checklist / Danh Sách Kiểm Tra
- [ ] RTX 3090 GPU available with latest drivers
- [ ] kohya-ss repo cloned: `git clone https://github.com/bmaltais/kohya_ss.git "E:\The Data Mint\kohya-ss"`
- [ ] SD 1.5 checkpoint exists: `E:\ComfyUI_windows_portable\ComfyUI\models\checkpoints\sd-v1-5-pruned-emaonly.safetensors`
- [ ] Training data from Phase 2 exists
- [ ] At least 50GB free disk space

**Vietnamese:**
- [ ] GPU RTX 3090 có driver mới nhất
- [ ] Đã clone kohya-ss repo
- [ ] File checkpoint SD 1.5 tồn tại
- [ ] Dữ liệu từ Phase 2 đã sẵn sàng
- [ ] Ít nhất 50GB ổ đĩa trống

---

## Environment Setup / Thiết Lập Môi Trường {#environment-setup}

### Step 1: Create Virtual Environment / Tạo Môi Trường Ảo

**English:**
Run the setup script to create Python venv with all dependencies:

```powershell
cd "E:\The Data Mint\kohya-ss"
.\setup-kohya-venv.ps1
```

This script will:
- Create `venv\` directory with Python 3.10.6
- Install PyTorch 2.0.1+cu118
- Install xformers, bitsandbytes, accelerate
- Install kohya-ss sd-scripts dependencies

**Vietnamese:**
Chạy script thiết lập để tạo môi trường Python với đầy đủ thư viện:

Script sẽ:
- Tạo thư mục `venv\` với Python 3.10.6
- Cài PyTorch 2.0.1+cu118
- Cài xformers, bitsandbytes, accelerate
- Cài các thư viện cần thiết cho kohya-ss

**Expected output:**
```
=== kohya-ss venv setup complete ===
Python: 3.10.6
PyTorch: 2.0.1+cu118
xformers: 0.0.20
Activate: venv\Scripts\Activate.ps1
```

### Step 2: Configure Accelerate / Cấu Hình Accelerate

**English:**
Activate venv and configure accelerate for single GPU training:

```powershell
.\venv\Scripts\Activate.ps1
accelerate config
```

**Answer prompts EXACTLY as shown:**

```
? In which compute environment are you running?
→ This machine

? Which type of machine are you using?
→ No distributed training

? Do you want to run your training on CPU only (even if a GPU is available)?
→ NO

? Do you wish to optimize your script with torch dynamo?
→ NO

? Do you want to use DeepSpeed?
→ NO

? What GPU(s) (by id) should be used for training on this machine as a comma-separated list?
→ 0

? Do you wish to use FP16 or BF16 (mixed precision)?
→ fp16
```

**Vietnamese:**
Kích hoạt venv và cấu hình accelerate cho huấn luyện GPU đơn:

**Trả lời đúng như sau:**
- Môi trường: This machine (máy này)
- Loại máy: No distributed training (không huấn luyện phân tán)
- Chỉ dùng CPU: NO (không)
- Tối ưu torch dynamo: NO (không)
- Dùng DeepSpeed: NO (không)
- GPU ID: 0
- Mixed precision: fp16

**Expected output:**
```
accelerate configuration saved at C:\Users\<user>\.cache\huggingface\accelerate\default_config.yaml
```

### Step 3: Verify GPU Access / Kiểm Tra GPU

**English:**
Test GPU is accessible from venv:

```powershell
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

**Expected output:**
```
CUDA: True
GPU: NVIDIA GeForce RTX 3090
```

**Vietnamese:**
Kiểm tra GPU có thể truy cập từ venv:

**Kết quả mong đợi:**
```
CUDA: True
GPU: NVIDIA GeForce RTX 3090
```

---

## Pilot Training / Huấn Luyện Thử Nghiệm {#pilot-training}

### Why Pilot First? / Tại Sao Chạy Thử Trước?

**English:**
Train crack LoRA first (smallest dataset, 228 images) to:
- Verify pipeline works end-to-end
- Catch config errors early
- Estimate training time for remaining LoRAs
- Validate output quality before committing 10+ hours

**Vietnamese:**
Huấn luyện LoRA crack trước tiên (dataset nhỏ nhất, 228 ảnh) để:
- Xác minh quy trình hoạt động đầu cuối
- Phát hiện lỗi cấu hình sớm
- Ước tính thời gian huấn luyện cho các LoRA còn lại
- Kiểm tra chất lượng đầu ra trước khi dành 10+ giờ

### Run Pilot Training / Chạy Huấn Luyện Thử

**English:**
From PowerShell in `E:\The Data Mint\kohya-ss\`:

```powershell
.\venv\Scripts\Activate.ps1
.\train-all-loras.ps1 -PilotOnly
```

**What happens:**
1. Activates venv
2. Creates output directory: `output\crack\`
3. Runs training for 20 epochs (~15-30 min on RTX 3090)
4. Saves checkpoints every 5 epochs:
   - `xray_crack_lora_r32-000005.safetensors` (epoch 5)
   - `xray_crack_lora_r32-000010.safetensors` (epoch 10)
   - `xray_crack_lora_r32-000015.safetensors` (epoch 15)
   - `xray_crack_lora_r32-000020.safetensors` (epoch 20)
5. Copies final LoRA to ComfyUI: `E:\ComfyUI_windows_portable\ComfyUI\models\loras\`

**Vietnamese:**
Từ PowerShell trong thư mục `E:\The Data Mint\kohya-ss\`:

**Quá trình:**
1. Kích hoạt venv
2. Tạo thư mục output: `output\crack\`
3. Chạy huấn luyện 20 epoch (~15-30 phút trên RTX 3090)
4. Lưu checkpoint mỗi 5 epoch
5. Copy LoRA cuối cùng vào ComfyUI

### Monitor Training / Theo Dõi Huấn Luyện

**English:**
Watch console output for:

```
epoch 1/20
steps: 100%|████████| 57/57 [00:45<00:00, 1.26it/s, loss=0.1234, lr=0.0001]

epoch 5/20 - saving checkpoint...
epoch 10/20 - saving checkpoint...
```

**Key metrics:**
- **loss**: Should decrease from ~0.15 to ~0.05
- **it/s**: Iterations per second (~1.2-1.5 on RTX 3090)
- **VRAM**: Monitor with `nvidia-smi` (should stay <16GB)

**Vietnamese:**
Theo dõi output console:

**Chỉ số quan trọng:**
- **loss**: Nên giảm từ ~0.15 xuống ~0.05
- **it/s**: Số vòng lặp mỗi giây (~1.2-1.5 trên RTX 3090)
- **VRAM**: Theo dõi bằng `nvidia-smi` (nên <16GB)

### TensorBoard Visualization / Trực Quan Hóa TensorBoard

**English:**
Open another PowerShell terminal:

```powershell
cd "E:\The Data Mint\kohya-ss"
.\venv\Scripts\Activate.ps1
tensorboard --logdir="logs"
```

Open browser: `http://localhost:6006`

**What to check:**
- Loss curve: smooth downward trend, no spikes
- Learning rate: cosine decay from 1e-4 to 0
- No NaN/Inf values

**Vietnamese:**
Mở terminal PowerShell khác:

**Kiểm tra:**
- Đường loss: xu hướng giảm mượt, không có đột biến
- Learning rate: giảm dần theo cosine từ 1e-4 về 0
- Không có giá trị NaN/Inf

---

## Full Training / Huấn Luyện Đầy Đủ {#full-training}

### After Pilot Success / Sau Khi Thử Nghiệm Thành Công

**English:**
If crack LoRA trains successfully and outputs look good in ComfyUI, train remaining 4 LoRAs:

```powershell
.\venv\Scripts\Activate.ps1
.\train-all-loras.ps1 -SkipCrack
```

**Training order:**
1. porosity (510 images, ~30-45 min)
2. inclusion (114 images, ~15-25 min)
3. lack_of_fusion (269 images, ~25-35 min)
4. undercut (86 images, ~10-20 min)

**Total estimated time:** 2-3 hours for all 4

**Vietnamese:**
Nếu LoRA crack huấn luyện thành công và kết quả tốt trong ComfyUI, huấn luyện 4 LoRA còn lại:

**Thứ tự huấn luyện:**
1. porosity (510 ảnh, ~30-45 phút)
2. inclusion (114 ảnh, ~15-25 phút)
3. lack_of_fusion (269 ảnh, ~25-35 phút)
4. undercut (86 ảnh, ~10-20 phút)

**Tổng thời gian ước tính:** 2-3 giờ cho cả 4

### Train All from Scratch / Huấn Luyện Tất Cả Từ Đầu

**English:**
To train all 5 LoRAs in one command (skip pilot):

```powershell
.\venv\Scripts\Activate.ps1
.\train-all-loras.ps1
```

**Warning:** This will take 3-4 hours total. Only do this if you're confident the pipeline is working.

**Vietnamese:**
Để huấn luyện cả 5 LoRA trong một lệnh (bỏ qua thử nghiệm):

**Cảnh báo:** Tổng thời gian 3-4 giờ. Chỉ làm nếu bạn chắc chắn quy trình hoạt động tốt.

### Expected Outputs / Kết Quả Mong Đợi

**Directory structure after training:**
```
E:\The Data Mint\kohya-ss\
├── output\
│   ├── crack\
│   │   ├── xray_crack_lora_r32-000005.safetensors
│   │   ├── xray_crack_lora_r32-000010.safetensors
│   │   ├── xray_crack_lora_r32-000015.safetensors
│   │   └── xray_crack_lora_r32-000020.safetensors (FINAL)
│   ├── porosity\
│   │   └── xray_porosity_lora_r32-000020.safetensors
│   ├── inclusion\
│   │   └── xray_inclusion_lora_r32-000020.safetensors
│   ├── lack_of_fusion\
│   │   └── xray_lack_of_fusion_lora_r32-000020.safetensors
│   └── undercut\
│       └── xray_undercut_lora_r32-000020.safetensors
└── logs\
    ├── crack\
    ├── porosity\
    ├── inclusion\
    ├── lack_of_fusion\
    └── undercut\
```

**File sizes (approximate):**
- Each LoRA: ~75-100 MB (.safetensors format)
- Logs: ~10-50 MB per LoRA

---

## Validation / Kiểm Tra Kết Quả {#validation}

### Step 1: Load LoRA in ComfyUI / Tải LoRA Vào ComfyUI

**English:**
1. Open ComfyUI: `E:\ComfyUI_windows_portable\run_nvidia_gpu.bat`
2. Load default workflow (Stable Diffusion 1.5)
3. Add node: `Loaders` → `Load LoRA`
4. Select LoRA: `xray_crack_lora_r32-000020.safetensors`
5. Set strength: `1.0` (full strength for testing)

**Vietnamese:**
1. Mở ComfyUI: `E:\ComfyUI_windows_portable\run_nvidia_gpu.bat`
2. Tải workflow mặc định (Stable Diffusion 1.5)
3. Thêm node: `Loaders` → `Load LoRA`
4. Chọn LoRA: `xray_crack_lora_r32-000020.safetensors`
5. Đặt strength: `1.0` (độ mạnh tối đa để kiểm tra)

### Step 2: Generate Test Images / Tạo Ảnh Kiểm Tra

**English:**
Test prompts for each LoRA:

**Crack LoRA:**
```
Positive: xray_crack, weld crack defect, radiographic image, high contrast
Negative: color, rgb, chromatic aberration, blurry
Seed: 42
Steps: 25
CFG: 7.0
Sampler: DPM++ 2M Karras
```

**Porosity LoRA:**
```
Positive: xray_porosity, weld porosity defect, radiographic image, high contrast
Negative: (same as above)
```

**Inclusion LoRA:**
```
Positive: xray_inclusion, weld inclusion defect, radiographic image, high contrast
Negative: (same as above)
```

**Lack of Fusion LoRA:**
```
Positive: xray_lack_of_fusion, weld lack of fusion defect, radiographic image, high contrast
Negative: (same as above)
```

**Undercut LoRA:**
```
Positive: xray_undercut, weld undercut defect, radiographic image, high contrast
Negative: (same as above)
```

**Vietnamese:**
Prompt kiểm tra cho từng LoRA (dùng prompts tiếng Anh như trên)

### Step 3: Quality Assessment / Đánh Giá Chất Lượng

**English:**
For each generated image, check:

**✓ Good quality indicators:**
- Pure grayscale (no color bleeding)
- Sharp X-ray texture (not blurry)
- Defect morphology matches real samples
- High contrast between defect and background
- Realistic noise/grain pattern

**✗ Bad quality indicators:**
- Color artifacts (pink, blue tints)
- Blurry or oversaturated
- Defect looks cartoonish or unrealistic
- Missing X-ray texture
- Overfitting (exact copies of training images)

**Vietnamese:**
Với mỗi ảnh được tạo ra, kiểm tra:

**✓ Chỉ báo chất lượng tốt:**
- Grayscale thuần túy (không lem màu)
- Kết cấu X-ray sắc nét (không mờ)
- Hình thái khuyết tật khớp với mẫu thật
- Độ tương phản cao giữa khuyết tật và nền
- Mẫu nhiễu/hạt thực tế

**✗ Chỉ báo chất lượng xấu:**
- Nhiễu màu (tông hồng, xanh)
- Mờ hoặc quá bão hòa
- Khuyết tật trông như phim hoạt hình
- Thiếu kết cấu X-ray
- Overfitting (bản sao chính xác ảnh huấn luyện)

### Step 4: Side-by-Side Comparison / So Sánh Trực Tiếp

**English:**
1. Open real defect patch from Phase 2: `E:\The Data Mint\dataset\processed\patches_512\crack\W0003_0001_crop_0_0.png`
2. Generate synthetic image with crack LoRA (same seed for consistency)
3. Place side-by-side in image viewer
4. Compare: texture, defect shape, contrast, noise

**Acceptance criteria:**
- Expert observer cannot easily distinguish synthetic from real
- Defect morphology preserves key characteristics
- No obvious artifacts or unnatural patterns

**Vietnamese:**
1. Mở patch khuyết tật thật từ Phase 2
2. Tạo ảnh tổng hợp với LoRA crack (cùng seed để nhất quán)
3. Đặt cạnh nhau trong trình xem ảnh
4. So sánh: kết cấu, hình dạng khuyết tật, độ tương phản, nhiễu

**Tiêu chí chấp nhận:**
- Chuyên gia khó phân biệt ảnh tổng hợp và ảnh thật
- Hình thái khuyết tật giữ nguyên đặc điểm chính
- Không có nhiễu rõ ràng hoặc mẫu không tự nhiên

---

## Troubleshooting / Xử Lý Lỗi {#troubleshooting}

### Common Errors / Lỗi Thường Gặp

#### 1. CUDA Out of Memory (OOM)

**Error message:**
```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; 24.00 GiB total capacity)
```

**English Solution:**
- Reduce batch size in TOML config: `train_batch_size = 2` (instead of 4)
- Enable aggressive gradient checkpointing (already enabled)
- Close other GPU applications (browsers, games)
- Reduce resolution: `resolution = 448` (instead of 512)

**Vietnamese Giải Pháp:**
- Giảm batch size trong config TOML: `train_batch_size = 2`
- Bật gradient checkpointing (đã bật sẵn)
- Đóng các ứng dụng dùng GPU khác (trình duyệt, game)
- Giảm độ phân giải: `resolution = 448`

#### 2. ModuleNotFoundError: No module named 'torch'

**Error message:**
```
ModuleNotFoundError: No module named 'torch'
```

**English Solution:**
- Ensure venv is activated: `.\venv\Scripts\Activate.ps1`
- Check prompt shows `(venv)` prefix
- Reinstall PyTorch: `pip install torch==2.0.1+cu118 --index-url https://download.pytorch.org/whl/cu118`

**Vietnamese Giải Pháp:**
- Đảm bảo venv được kích hoạt
- Kiểm tra prompt hiển thị `(venv)`
- Cài lại PyTorch nếu cần

#### 3. Training Loss Diverges (NaN/Inf)

**Error message:**
```
epoch 3/20
loss=nan
```

**English Solution:**
- Reduce learning rate: `learning_rate = 5e-5` (instead of 1e-4)
- Check training data quality (corrupt images?)
- Remove noise offset: `noise_offset = 0.0`
- Use gradient clipping: add `max_grad_norm = 1.0` to config

**Vietnamese Giải Pháp:**
- Giảm learning rate: `learning_rate = 5e-5`
- Kiểm tra chất lượng dữ liệu (ảnh bị lỗi?)
- Tắt noise offset: `noise_offset = 0.0`
- Dùng gradient clipping: thêm `max_grad_norm = 1.0`

#### 4. CUDA Version Mismatch

**Error message:**
```
RuntimeError: CUDA error: invalid device ordinal
CUDA kernel errors might be asynchronously reported
```

**English Solution:**
- Verify CUDA 11.8 installed: `nvcc --version`
- Update GPU drivers from NVIDIA website
- Reinstall PyTorch with correct CUDA version:
  ```powershell
  pip uninstall torch torchvision torchaudio
  pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 --index-url https://download.pytorch.org/whl/cu118
  ```

**Vietnamese Giải Pháp:**
- Xác minh CUDA 11.8 đã cài: `nvcc --version`
- Cập nhật driver GPU từ trang NVIDIA
- Cài lại PyTorch với CUDA đúng phiên bản

#### 5. Accelerate Config Missing

**Error message:**
```
ValueError: Could not find accelerate configuration
```

**English Solution:**
- Run `accelerate config` again (see Step 2 in Environment Setup)
- Or copy default config:
  ```powershell
  mkdir "$env:USERPROFILE\.cache\huggingface\accelerate"
  # Then run accelerate config
  ```

**Vietnamese Giải Pháp:**
- Chạy lại `accelerate config` (xem Bước 2 trong Thiết Lập Môi Trường)

#### 6. LoRA Produces Color Images (Not Grayscale)

**English Solution:**
This is a **generation problem**, not training problem:
- Add to negative prompt: `color, colored, rgb, chromatic aberration, vibrant`
- Increase CFG scale to 8-10
- Try different samplers (DPM++ 2M Karras usually best for X-ray)
- Post-process: convert to grayscale in ComfyUI with ColorCorrect node

**Vietnamese Giải Pháp:**
Đây là lỗi **tạo ảnh**, không phải lỗi huấn luyện:
- Thêm vào negative prompt: `color, colored, rgb, chromatic aberration, vibrant`
- Tăng CFG scale lên 8-10
- Thử sampler khác (DPM++ 2M Karras thường tốt nhất cho X-ray)
- Xử lý sau: chuyển sang grayscale trong ComfyUI

#### 7. Training Extremely Slow

**English Solution:**
- Enable xformers (already enabled in config)
- Cache latents (already enabled)
- Reduce num_cpu_threads_per_process to 4 (from 8)
- Close background applications (Discord, Chrome, etc.)
- Check GPU usage with `nvidia-smi` - should be 90-100%

**Vietnamese Giải Pháp:**
- Bật xformers (đã bật sẵn)
- Cache latents (đã bật sẵn)
- Giảm num_cpu_threads_per_process xuống 4
- Đóng ứng dụng nền (Discord, Chrome, v.v.)
- Kiểm tra GPU usage bằng `nvidia-smi` - nên 90-100%

---

## Advanced Tuning / Tinh Chỉnh Nâng Cao

### If Quality Insufficient / Nếu Chất Lượng Chưa Đủ

**English:**

**Option 1: Increase LoRA Rank**
- Edit TOML: `network_dim = 64` (double from 32)
- Edit TOML: `network_alpha = 32` (double from 16)
- Retrain - will capture more details but larger file size (~150 MB)

**Option 2: More Epochs**
- Edit TOML: `max_train_epochs = 30` (increase from 20)
- Watch for overfitting - if loss plateaus, stop early

**Option 3: Adjust Learning Rate**
- Higher LR (faster learning): `learning_rate = 2e-4`
- Lower LR (more stable): `learning_rate = 5e-5`

**Option 4: More Regularization**
- Increase clean image repeats in config
- Add dropout: `network_dropout = 0.1`

**Vietnamese:**

**Tùy chọn 1: Tăng Rank LoRA**
- Sửa TOML: `network_dim = 64` (gấp đôi từ 32)
- Sửa TOML: `network_alpha = 32` (gấp đôi từ 16)
- Huấn luyện lại - sẽ nắm bắt nhiều chi tiết hơn nhưng file lớn hơn (~150 MB)

**Tùy chọn 2: Thêm Epoch**
- Sửa TOML: `max_train_epochs = 30` (tăng từ 20)
- Theo dõi overfitting - nếu loss không giảm, dừng sớm

**Tùy chọn 3: Điều Chỉnh Learning Rate**
- LR cao hơn (học nhanh hơn): `learning_rate = 2e-4`
- LR thấp hơn (ổn định hơn): `learning_rate = 5e-5`

**Tùy chọn 4: Tăng Regularization**
- Tăng repeats của ảnh clean trong config
- Thêm dropout: `network_dropout = 0.1`

---

## Next Steps / Bước Tiếp Theo

**English:**
After all 5 LoRAs are trained and validated:

1. **Phase 4**: Integrate LoRAs into ComfyUI inpainting workflow
2. **Generate Synthetic Dataset**: Use LoRAs to create 10,000+ synthetic defect images
3. **Model Training**: Train YOLOv8 defect detector on synthetic + real data
4. **Evaluation**: Compare detection accuracy vs real-only training

**Vietnamese:**
Sau khi cả 5 LoRA được huấn luyện và kiểm tra:

1. **Phase 4**: Tích hợp LoRA vào workflow inpainting ComfyUI
2. **Tạo Dataset Tổng Hợp**: Dùng LoRA tạo 10,000+ ảnh khuyết tật tổng hợp
3. **Huấn Luyện Mô Hình**: Huấn luyện YOLOv8 phát hiện khuyết tật trên dữ liệu tổng hợp + thật
4. **Đánh Giá**: So sánh độ chính xác phát hiện vs chỉ huấn luyện trên dữ liệu thật

---

## Reference Files / Tài Liệu Tham Khảo

- Training configs: `E:\The Data Mint\kohya-ss\configs\*.toml`
- Batch script: `E:\The Data Mint\kohya-ss\train-all-loras.ps1`
- Phase plan: `/mnt/e/The Data Mint/plans/260130-0849-the-data-mint-xray-defect-pipeline/phase-03-lora-training.md`
- Research report: `/mnt/e/The Data Mint/plans/260130-0849-the-data-mint-xray-defect-pipeline/research/researcher-01-comfyui-lora-controlnet.md`

## Dataset Statistics / Thống Kê Dataset

| Defect Type | Images | Repeats | Steps/Epoch |
|-------------|--------|---------|-------------|
| crack | 228 | 10 | 2,280 |
| porosity | 510 | 5 | 2,550 |
| inclusion | 114 | 20 | 2,280 |
| lack_of_fusion | 269 | 8 | 2,152 |
| undercut | 86 | 25 | 2,150 |
| clean (reg) | 3,524 | 1 | 3,524 |

**Batch size = 4, so actual steps/epoch = above / 4**

---

**Training started:** [To be filled after execution]
**Training completed:** [To be filled after execution]
**Total time:** [To be filled after execution]
**All LoRAs validated:** [ ] Yes [ ] No
