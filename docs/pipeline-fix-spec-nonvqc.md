# YÊU CẦU SINH ẢNH SYNTHETIC — Phim Hàn Đầy Đủ Khớp W0003

**Ngày**: 2026-08-09 · **Thay cho**: `pipeline-fix-spec-nonvqc.md` (bản tile 512 đơn-khuyết-tật)
**Quyết định hướng (user)**: bỏ cách sinh tile 512 một-khuyết-tật; chuyển sang sinh **ẢNH PHIM
ĐẦY ĐỦ cùng kích thước và phong cách W0003**, mỗi ảnh có **một HOẶC nhiều** khuyết tật.
**Mục tiêu**: synthetic tốt tới mức đứng chung phân bố với phim thật → train non-VQC (và VQC)
không dính domain-gap, bù được trần dữ liệu 68 phim thật.

---

## 0. Vì sao đổi hướng (một câu)

Sinh tile 512 đơn-khuyết-tật cắt rời khuyết tật khỏi ngữ cảnh phim (đường hàn, vùng nền, nhiều
khuyết tật cùng tồn tại) → model học trên mảnh, lệch với lúc chạy thật trên phim đầy đủ. Sinh
**cả phim** giữ đúng ngữ cảnh, và tiling để train diễn ra SAU, y hệt đường đi của phim thật.

---

## 1. Đặc tả ĐẦU RA (khớp W0003)

| Thuộc tính | Yêu cầu | Nguồn chuẩn (đo từ 68 phim W0003 thật) |
|---|---|---|
| **Kích thước** | dải dài ngang, **rộng ~4980–5000 px, cao ~1200–2200 px** (biến thiên theo phim) | rộng phổ biến 4986–4998; cao 1234–2174 |
| **Tỉ lệ khung** | ngang dẹt (~3.5:1 đến ~4:1) | không sinh ảnh vuông |
| **Kênh** | grayscale 8-bit (hoặc 16-bit nếu giữ dải động phim) | RT là ảnh xám |
| **Tỉ lệ vật lý** | ~**0.0334 mm/px** — kích thước khuyết tật phải đúng tỉ lệ này | scale dự án |
| **Bố cục** | một **đường hàn nằm ngang** chạy suốt chiều dài; nền hai bên là kim loại cơ bản | đặc trưng phim hàn |
| **Số khuyết tật/ảnh** | **0..N** (có ảnh sạch, có ảnh 1, có ảnh nhiều loại) — KHÔNG ép đúng 1 | giống thật |

### 1.1 Phân bố số khuyết tật/ảnh (đề xuất, canh theo phim thật)
- ~15–20% ảnh **sạch** (không khuyết tật) → nuôi lớp Background.
- ~40% ảnh **1 khuyết tật**.
- ~40% ảnh **nhiều khuyết tật** (2–5), có thể **khác loại** trên cùng phim.
- Khi nhiều khuyết tật: đặt **dọc theo đường hàn**, khoảng cách thực tế, không chồng đè phi lý.

---

## 2. Nguyên tắc BẤT BIẾN (không được vi phạm)

1. **Test = phim W0003 THẬT giữ riêng.** Synthetic CHỈ vào train. Không byte synthetic nào ở test.
2. **Split theo PHIM (grouped-by-film), không theo tile/box.** Mỗi phim synthetic là **một group
   riêng**, gắn `source=synthetic`, chỉ nằm train. Tile cắt từ một phim đi trọn vào một ngăn.
   → chống đúng lỗi rò rỉ đã phát hiện (tile cùng phim lọt cả train/val).
3. **Nhãn đo từ khuyết tật THỰC SINH trên phim**, không copy mask ý đồ (SD có thể vẽ lệch).
4. **Đo hiệu quả trên grouped split sạch**, không trên số box-level cũ (đã chứng minh là rò rỉ, vô nghĩa).

---

## 3. CHẤT LƯỢNG ẢNH — khớp domain (nhóm chí mạng)

Giữ nguyên tinh thần 4 lỗi domain-gap đã ghi ở pipeline as-is §8, áp cho phim đầy đủ:

### 3.1 Diffusion là chính, post-process chỉ nudge
- Trả SD1.5+LoRA về vai vẽ kết cấu khuyết tật. Bỏ bước "thay cứng pixel ngoài mask = nền gốc".
- Hệ số tối cưỡng bức S: **0.15–0.25** (chỉ nudge quy ước tối), KHÔNG 0.92 như bản cũ.
- Điều kiện Done: lòng khuyết tật có kết cấu/nhiễu, không phẳng lì, không cạnh dán.

### 3.2 Đường hàn + nền phải THẬT như phim
- Nền kim loại cơ bản: cùng mức xám, gradient sáng-tối ngang qua mối hàn (vùng hàn thường sáng/tối
  hơn nền theo bề dày) như W0003.
- Có thể **inpaint khuyết tật lên chính phôi nền lấy từ vùng sạch của phim thật W0003** (giữ nền thật,
  chỉ sinh khuyết tật) — cách này khử domain-gap nền tốt nhất. Nhưng nền đó phải thuộc phim
  train-side, không lấy từ phim test.

### 3.3 Feather cạnh + film grain liên tục
- Biên khuyết tật có penumbra (gradient, mô phỏng MTF phim/detector), không nhị phân.
- Thêm nhiễu hạt phim vào toàn ảnh kể cả lòng khuyết tật, cùng thống kê var với nền W0003.

### 3.4 Sửa quy ước sáng/tối
- Void (rỗ, nứt, thiếu ngấu, thiếu chảy): **TỐI** hơn nền.
- `lack_of_penetration`: đường **tối** liên tục giữa chân mối (bản cũ ra sáng — sai).
- `metallic_inclusion`: kim loại đặc → **SÁNG** mờ có kết cấu (không phải polygon trắng đặc).
  Đây là lớp duy nhất sáng-hơn-nền.

---

## 4. NỘI DUNG — hình thái đúng + phân biệt họ rỗ

Điều khiển được loại + hình thái (đã xác nhận pipeline làm được). Trên phim đầy đủ, rải khuyết tật
theo hình thái đặc trưng để dạy PHÂN BIỆT, nhất là họ rỗ:

| Lớp | Hình thái bắt buộc | Đặc trưng phân biệt |
|---|---|---|
| Gas_Pore | lỗ tròn (circularity ≥0.8) rời rạc, vị trí ngẫu nhiên dọc mối, Ø 0.5–1.2mm | tròn + rải + độc lập |
| Linear_Porosity | lỗ xếp **thẳng hàng** dọc trục hàn, khoảng cách đều | collinear |
| Clustered_localized_Porosity | lỗ **túm cụm** một vùng, mật độ cao cục bộ | cụm cục bộ |
| Crack | mảnh, ngoằn ngoèo, tương phản thấp, nhiều hướng | tuyến mảnh, contrast thấp |
| Lack_of_Penetration | đường tối liên tục giữa chân mối, đa dạng độ dài/đậm | tuyến tối ở gốc mối |

- Khi đặt nhiều khuyết tật/phim: được phép trộn loại, nhưng ghi nhãn+bbox từng cái theo vị trí thực.
- Lớp đã mạnh (Slag, LoSWF) không cần ưu tiên; ⚠ **Continuous_undercut** xác minh out-of-scope trước.
- (Lưu ý: ưu tiên sinh lớp nào theo SỐ LƯỢNG sẽ chốt lại SAU khi có baseline grouped-split sạch —
  KHÔNG dùng bảng per-class cũ vì nó tính trên eval rò rỉ.)

---

## 5. CỔNG KIỂM ĐỊNH trước khi vào train

| Cổng | Đo gì | Ngưỡng | Không đạt thì |
|---|---|---|---|
| **C1 Domain (FID)** | FID lô synthetic vs phim W0003 thật (theo lớp/họ) | FID ≤ 50 (calibrate sàn = W0003-aug vs W0003-gốc) | chỉnh §3, không dùng train |
| **C2 Nhãn** | IoU vùng defect thực-sinh vs mask ý đồ | IoU ≥ 0.5 | loại ảnh |
| **C3 Phân biệt** | confusion Gas↔Linear↔Clustered trên chính synthetic | lẫn thấp | chỉnh tham số hình thái §4 |
| **C4 Bố cục** | kích thước/tỉ lệ khung + vị trí khuyết tật trên đường hàn hợp lý | khớp §1 | loại ảnh |

---

## 6. NGHIỆM THU (đo hiệu quả)

Train lại non-VQC với (phim W0003 thật train-side + phim synthetic), tile hoá y hệt đường đi thật,
đo trên **grouped-split-by-film sạch** (test = phim thật giữ riêng):

1. macro-F1 tăng so với baseline grouped-split sạch (baseline này phải đo LẠI trước — số 0.585 cũ vô hiệu).
2. **3 F1 họ rỗ (Gas/Linear/Clustered) tách nhau ra** — bằng chứng dạy được phân biệt, không nhồi số.
3. critical_recall (Crack/LoP/LoSWF) không giảm.
4. Khoảng cách train↔test thu hẹp (bằng chứng domain-gap giảm).

---

## 7. THỨ TỰ THỰC THI

1. **Splitter grouped-by-film** cho dữ liệu thật (chặn rò rỉ) + đo lại baseline sạch. ← LÀM TRƯỚC
2. Sửa chất lượng ảnh §3 (diffusion về vai chính, feather, grain, quy ước) trên đường sinh phim đầy đủ.
3. Dựng cổng FID (C1) trước khi sinh hàng loạt.
4. Sinh phim đầy đủ theo §1 (kích thước W0003, 0..N khuyết tật/ảnh, hình thái §4).
5. Qua cổng C1–C4 → đưa vào train → nghiệm thu §6.
6. Chốt lại phân bố ưu tiên lớp theo baseline sạch.

---

## 8. RỦI RO / LƯU Ý

- Sinh phim đầy đủ ~5000×1300 nặng hơn tile 512 nhiều lần (VRAM, thời gian). Cân nhắc sinh theo
  panel rồi ghép, HOẶC inpaint khuyết tật lên phôi nền thật (§3.2) — rẻ hơn sinh cả phim từ nhiễu.
- Trần dữ liệu gốc vẫn còn: 68 phim thật, lớp hiếm dồn 1–2 phim. Synthetic bù được đa dạng khuyết tật
  nhưng KHÔNG thay được phim thật cho test → test luôn mỏng ở lớp hiếm; ghi thẳng giới hạn này vào báo cáo.
- Nếu inpaint lên nền thật: tuyệt đối chỉ dùng nền từ phim train-side, tránh rò rỉ nền test.
