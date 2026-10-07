# SPEC — Nâng cấp Pipeline Sinh Ảnh để cải thiện QuantumRT (VQC)

**Cập nhật**: 2026-08-09 · **Trạng thái**: đề xuất (chờ duyệt) · **Tham chiếu hiện trạng**: `pipeline-generation-current.md`
**Mục tiêu**: sinh ảnh synthetic ĐỦ CHÂN THỰC để đóng domain-gap, nâng recall các lớp yếu của VQC **mà không** bơm artifact thủ công vào tập train.
**Chế độ chốt (2026-08-09)**: sinh **phim FULL-SIZE như W0003, nhiều khuyết tật/ảnh** (xem §7), thay cho crop vuông 512 1-lỗi/ảnh — để khớp chế độ e2e phim thật.

---

## 0. Vì sao phải sửa (chẩn đoán từ dữ liệu VQC thật)

Chẩn đoán trên eval image-level (chống rò rỉ) của QuantumRT cho thấy lỗi KHÔNG đồng nhất — phải sửa đúng trục:

| Lớp | Triệu chứng (image-level val) | Trục hỏng | Sinh ảnh cứu được? |
|---|---|---|---|
| **Gas_Pore** | recall 0.0 **dù nhiều mẫu nhất (101)**; nhầm thành Linear_Porosity (4/7) + Background (2/7) | KHÓ PHÂN BIỆT (không phải thiếu) | Chỉ nếu sinh **cặp tương phản**, không phải sinh thêm số lượng |
| **Gas vs Linear (branch_2_1)** | 0.56 — gần ngẫu nhiên | KHÓ PHÂN BIỆT | Như trên |
| **Background** | bị gọi nhầm thành defect → clean-recall e2e chỉ 0.17 | ÂM TÍNH KHÓ | Cần **hard-negative** (pipeline hiện KHÔNG sinh) |
| **Metallic (23), Elongate (28), Linear (28)** | ít mẫu train | THIẾU MẪU | Có — bù số lượng đa dạng |

**Kết luận**: pipeline hiện đáp ứng ~40% — kiểm soát HÌNH THÁI (mask thủ tục) thì tốt, nhưng CHẤT LƯỢNG ẢNH bị bước 7 phá, và KHÔNG sinh được hard-negative.

---

## 1. Nút thắt gốc: bước 7 `apply_dark_defect_convention()`

Hiện trạng (mục 6 của as-is): ảnh cuối ≈ `nền gốc + hình mask nhân hệ số tối`. Diffusion bị ghi đè → mọi kết cấu/gradient/nhiễu do SD sinh ra bị mất. Bước 7 tồn tại như **miếng vá** cho việc LoRA vẽ *halo* ở vành đai giữa annotation-mask và inpaint-mask.

→ Hướng sửa **KHÔNG phải "xoá bước 7"** (halo sẽ quay lại) mà là **sửa gốc để diffusion không vẽ halo**, rồi mới bỏ được bước 7.

---

## 2. Các thay đổi (theo thứ tự đòn bẩy)

### C1 — Bỏ halo tại gốc (BẮT BUỘC, ưu tiên cao nhất)
**Vấn đề**: chênh lệch annotation-mask (mảnh) vs inpaint-mask (dilate k=21) tạo vành đai LoRA vẽ quầng sáng.
**Sửa**:
- Thu hẹp dilate inpaint mask: `k=21 → k=9` (ellipse), blur `7 → 5`. Vành đai hẹp lại → halo nhỏ.
- Dùng **soft inpaint mask có gradient** thay nhị phân: `inpaint = clip(gaussian(annotation, sigma=4) * 1.4, 0, 1)` — biên chuyển mượt, SD blend tự nhiên vào nền, không tạo vành sáng cứng.
- Giảm `denoise` KSampler `0.85–0.90 → 0.55–0.65`: giữ nhiều nền gốc quanh biên, SD chỉ vẽ lõi khuyết tật → ít cơ hội sinh halo.
- ControlNet inpaint strength `0.8 → 0.6`: nới ràng buộc để SD hoà kết cấu thay vì bám cứng mask.
**Cổng kiểm**: đo cường độ vành đai (mean pixel ở annulus giữa 2 mask) trước/sau; mục tiêu giảm ≥70%.

### C2 — Gỡ/thay bước 7 sau khi C1 đạt
- Nếu C1 khử được halo: **bỏ hẳn** darken cưỡng bức; thay bằng **blend mềm chỉ ở biên** để nối liền, giữ nguyên lõi do SD vẽ.
- Nếu vẫn cần quy ước void-tối RT: áp darken **rất nhẹ** `S ≤ 0.30` (thay 0.92) và **cộng lại nhiễu** vào lòng (mục C3) để không bị "mịn bất thường".
- **Sửa quy ước sai** (as-is 8.5): `lack_of_penetration` phải TỐI (đang ra sáng) — kiểm dấu; `metallic_inclusion` là vùng **sáng-đặc có hạt**, không phải đa giác trắng phẳng.

### C3 — Chân thực vật lý phim W0003 (đóng domain-gap — rủi ro số 1)
- **Penumbra hình học**: thêm bán dạ ở biên khuyết tật (gaussian trên alpha biên, sigma ~2–3 px @512) — mô phỏng nguồn tia không điểm + MTF detector. Gỡ 8.2.
- **Liên tục hạt nhiễu**: sau khi vẽ, **tái tạo nhiễu lượng tử** trong lòng khuyết tật khớp phương sai vùng lân cận (`add_poisson_gaussian(patch, match_local_var=True)`). Gỡ 8.3.
- **Gradient mật độ**: thay "nhân 1 hệ số phẳng" bằng **profile độ dày** (parabol/nêm theo loại lỗ) → độ tối biến thiên trong lòng. Gỡ 8.4.
- **Khớp thống kê toàn ảnh**: sau sinh, **histogram-match + grain-match** về phân bố phim W0003 thật (dùng 1 phim thật làm reference/lớp). Đây là bước quyết định để VQC không phân biệt thật/giả bằng artifact.

### C4 — Nhánh sinh HARD-NEGATIVE (mới — pipeline hiện thiếu hoàn toàn)
Mục 7 as-is: "Ảnh âm tính: Không có". Đây là lý do clean-recall e2e = 0.17.
- Thêm `defect_type = "hard_negative"`: sinh tile SẠCH nhưng có cấu trúc **dễ nhầm lỗi**: đường vân mối hàn, ranh giới vật liệu, hạt phim đậm, scratch/artifact phim.
- Nhãn = Background (âm tính). Trộn vào train theo tỉ lệ đề xuất **20–30%** tổng ảnh.
- Cơ chế: chạy inpaint với prompt "clean weld seam, film grain, no defect" trên nền + mask vùng-vân, KHÔNG darken.

### C5 — Cặp tương phản Gas ↔ Linear (gỡ nút khó-phân-biệt)
- Sinh **theo cặp cùng seed nền**: một ảnh Gas_Pore (đốm tròn RỜI RẠC, độ tròn cao) + một ảnh Linear_Porosity (chuỗi THẲNG HÀNG ≥3 lỗ, ISO 6520) trên **cùng patch nền**.
- Phóng đại đúng đặc trưng phân biệt: Gas = isolated blobs, aspect ~1.0; Linear = collinear, aspect chuỗi cao.
- Mục tiêu: dạy VQC RANH GIỚI, không phải thêm ví dụ. Ưu tiên cho branch_2 / branch_2_1.

### C6 — Nhãn đo từ ảnh thực sinh (gỡ 8.6)
- Sau sinh, **đo lại** bbox/mask từ khuyết tật THỰC xuất hiện (threshold + connected-components trên vùng đã darken), không lấy nguyên mask input.
- Loại ảnh mà khuyết tật thực lệch >30% diện tích so mask input (SD vẽ hỏng) — không đưa vào train với nhãn sai.

---

## 3. Ràng buộc bất biến (vi phạm = phản tác dụng)

1. **Kích thước thật**: Gas_Pore **0.5–1.2mm** (KHÔNG 2–5mm). Scale **0.0334 mm/px** → 15–36px. Sinh sai cỡ = tạo domain-gap ngược. **Khung ảnh** = full-size đa cỡ theo phân phối phim thật (~5000×1300, xem §7), KHÔNG cố định 512.
2. **Synthetic CHỈ vào train.** Test/val giữ **100% W0003 thật**. Trộn synthetic vào test = rò rỉ kiểu mới.
3. **Không thay đổi tập test** đã dùng cho báo cáo (giữ khả năng so sánh trước/sau).

---

## 4. Cổng kiểm định (QA gate) — CHẶN trước khi đưa vào train

Chạy trên mỗi lô sinh, **fail lô nếu không đạt ngưỡng**:

| Cổng | Chỉ số | Ngưỡng đề xuất | Ý nghĩa |
|---|---|---|---|
| **G1 — Chân thực phân phối** | **FID** (synthetic vs W0003 thật, per-class) | **≤ 60** (khởi điểm; siết dần) | Ảnh giả gần phân bố thật |
| **G2 — Cấu trúc biên** | **SSIM** vùng biên (synthetic vs crop thật cùng lớp) | **0.4–0.8** (không quá thấp=khác hẳn, không quá cao=copy) | Biên có penumbra thật, không cứng |
| **G3 — Khử halo (C1)** | mean-intensity annulus giữa 2 mask | giảm **≥70%** so bản cũ | Halo đã hết |
| **G4 — Nhiễu liên tục** | tỉ số phương sai lòng-lỗ / vùng-lân-cận | **0.8–1.2** | Lòng không "mịn bất thường" |
| **G5 — Nhãn khớp ảnh (C6)** | IoU(mask-input, khuyết-tật-thực-đo) | **≥ 0.7** | Nhãn không lệch ảnh |
| **G6 — Đúng quy ước** | dấu độ tối theo lớp (LoP phải tối…) | pass/fail thủ công + rule | Gỡ 8.5 |

**Vòng lặp kiểm định trong pipeline** (as-is 7: hiện FID/SSIM chỉ chạy hậu kỳ) → chuyển thành **cổng trong vòng lặp batch**: mỗi checkpoint 100 ảnh chạy G1–G5, log, và cảnh báo nếu tụt ngưỡng.

**Cổng cuối cùng — bằng chứng thật**: sinh 1 lô nhỏ theo spec → retrain 1 nhánh VQC yếu (vd branch_2 Gas/Linear) → đo recall image-level **trước/sau**. Chỉ mở rộng sản xuất nếu recall nhánh đó **tăng thực** trên tập W0003 thật. Đây là cổng quan trọng nhất: FID/SSIM đẹp mà recall không tăng thì spec vẫn thất bại.

---

## 5. Thứ tự triển khai đề xuất

1. **C1 (khử halo)** + **C3 (chân thực phim)** — hai đòn bẩy domain-gap lớn nhất; làm cùng nhau, kiểm G1/G3.
2. **C6 (nhãn đúng)** — rẻ, chặn nhãn sai ngay.
3. **C5 (cặp Gas/Linear)** — gỡ nút recall 0.0; kiểm bằng cổng cuối (retrain branch_2).
4. **C4 (hard-negative)** — hạ clean-recall; kiểm e2e.
5. **C2 (bỏ/thay bước 7)** — chỉ sau khi C1 xác nhận hết halo.

Mỗi bước qua cổng QA tương ứng mới sang bước sau. KHÔNG sinh sản xuất hàng loạt trước khi cổng cuối (retrain 1 nhánh) xác nhận recall tăng trên W0003 thật.

---

## 6. Rủi ro & lưu ý

- **FID cần đủ ảnh thật/lớp** để ổn định — W0003 ít mẫu vài lớp; với lớp <20 ảnh thật, FID nhiễu → dựa thêm SSIM + kiểm mắt.
- **Sửa denoise/controlnet (C1) có thể làm SD vẽ khuyết tật lệch hình thái** → C6 chặn được ảnh hỏng, nhưng cần theo dõi tỉ lệ loại.
- **Không chạy nổi ComfyUI ở máy này** thì spec vẫn là tài liệu host-side; các cổng QA (FID/SSIM/G3-G6) chạy được offline trên ảnh đã sinh.


---

## 7. CHẾ ĐỘ SINH FULL-SIZE NHIỀU KHUYẾT TẬT (thay đổi triết lý — chốt 2026-08-09)

**Quyết định**: chuyển từ sinh crop vuông 512×512 (1 lỗi/ảnh) sang sinh **phim dải dài như W0003, nhiều khuyết tật/ảnh** — để ảnh synthetic khớp ĐÚNG chế độ e2e (phim thật full-size) thay vì chỉ khớp chế độ tile.

### 7.1 Vì sao đổi
Pipeline cũ sinh 512×512, 1 lỗi/ảnh → chỉ hợp train tile-classifier, KHÔNG hợp e2e. Model học trên crop-1-lỗi gặp phim thật (nhiều lỗi + nhiều vùng nền + biên phim) thì lệch phân bố. Sinh full-size đóng khoảng cách này.

### 7.2 Kích thước & hình học thật (đo từ W0003 gốc — `data/raw/bam-w0003/images`)
- **Khung ảnh**: ~**4990 × 1300 px** (median), tỉ lệ ~3.8:1 ngang. **Biến thiên thật**: rộng 3512–4998, cao 1147–2174. → sinh theo **phân phối kích thước thật**, KHÔNG cố định một cỡ; lấy mẫu ngẫu nhiên từ tập kích thước phim thật.
- **Dải mối hàn**: nằm ngang, tâm y ≈ **0.53** (giữa ảnh), lệch chuẩn ±0.28. `_detect_weld_center_y` đã có — giữ, nhưng khuyết tật phải gieo **DỌC theo dải hàn**, không rải toàn khung.
- **Scale vật lý**: **0.0334 mm/px**. Suy ra kích thước px BẮT BUỘC theo ISO 6520:
  - Gas_Pore 0.5–1.2 mm → **15–36 px**
  - Linear_Porosity: chuỗi ≥3 lỗ, mỗi lỗ 15–36 px, khoảng cách gần
  - Crack: dài mảnh, rộng 1–3 px, dài tới vài trăm px
  - (các lớp khác quy đổi tương tự từ ngưỡng ISO 6520 mm)

### 7.3 Mật độ khuyết tật / ảnh (đo từ 876 nhãn thật)
- Thật: **1–24 lỗi/phim**, median 1, mean 1.3 → phân phối **lệch phải nặng** (đa số ít lỗi, ít phim nhiều lỗi).
- Sinh theo phân phối tương tự: **~60% ảnh 1–2 lỗi, ~30% ảnh 3–6 lỗi, ~10% ảnh 7–15 lỗi**. KHÔNG rải đều số lỗi (sai phân bố thật).
- Cho phép **trộn nhiều LOẠI lỗi trên cùng phim** (thật có) — nhưng gieo theo cụm hợp lý (rỗ khí thường theo đám; nứt thường đơn lẻ theo đường hàn).

### 7.4 Ground-truth cho ảnh full-size
- Mỗi khuyết tật gieo → ghi **bbox + class + mask** ở tọa độ phim full-size (định dạng YOLO như `data/processed/yolo-stage1-v2`).
- Sau sinh, tile hóa **giống hệt pipeline eval** (tile 512, overlap 25%, stride 384) để tạo tập train tile — nhưng giờ tile được cắt từ **phim synthetic full-size**, mang đúng thống kê nền/biên như phim thật.
- Nhãn tile theo `build_tile_gt` (overlap ≥30% diện tích box) — DÙNG CHUNG code eval để nhãn nhất quán.

### 7.5 Điều chỉnh cổng QA cho full-size
- **G1 FID**: tính trên **tile cắt từ phim synthetic** vs **tile phim W0003 thật** (không so nguyên phim — FID cần nhiều mẫu).
- **Thêm G7 — mật độ & vị trí**: phân phối (số lỗi/phim, tâm y lỗi, kích thước px theo lớp) của synthetic phải khớp phân phối thật (KS-test p>0.05 hoặc so histogram). Chặn ảnh đặt lỗi sai chỗ (ngoài dải hàn) hoặc sai cỡ.

### 7.6 Ràng buộc bổ sung
- **Không phóng to crop 512 cũ lên full-size** — phải sinh trực tiếp ở khung lớn (phóng to = mất chi tiết + sai grain).
- Nếu ComfyUI giới hạn cạnh (thường ≤1024–2048) → sinh theo **cửa sổ trượt dọc dải hàn** rồi ghép, đảm bảo liền mạch grain ở đường ghép (blend + match nhiễu tại seam).
