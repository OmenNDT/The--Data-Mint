# Undercut — Bản chất lỗi & đặc trưng hình thái (cho mask generator)

> Tài liệu tham chiếu để viết/sửa `pipeline/mask_generator/undercut-mask-generator.py`.
> Rút ra từ ảnh RT thật + sơ đồ hàn do người dùng cung cấp (2026-07-01).

## Bản chất lỗi

**Undercut** = rãnh/hõm bị **khoét vào kim loại nền** ngay tại **chân mối hàn (weld toe)** — nơi mép bead hàn gặp bề mặt tấm nền. Do dòng hàn quá cao / góc mỏ hàn sai / tốc độ nhanh làm nóng chảy mất một phần kim loại nền mà không được điền lại.

Vị trí: **dọc theo TOE (mép) của bead**, ở ranh giới bead ↔ kim loại nền. Có thể xuất hiện ở **một hoặc cả hai mép** (trên/dưới bead trong ảnh butt weld).

## Đặc trưng trong ảnh RT (radiograph)

- **Vệt TỐI** (void = ít kim loại → tia X xuyên nhiều → phim tối). Đúng quy ước RT.
- **DÀI, LIÊN TỤC** chạy dọc mép bead — thường gần hết chiều dài mối hàn trong khung ảnh.
- **MẢNH nhưng RÕ**: bề rộng nhỏ (rãnh hẹp), nhưng đậm và liền mạch (không đứt đoạn như crack/porosity).
- **BÁM SÁT MÉP bead** (weld toe), **song song** với đường mép — KHÔNG nằm giữa bead, KHÔNG lệch xa vào nền.
- Biên trong (phía bead) **sắc nét** (mép bead), biên ngoài (phía nền) **nhòe dần**.
- Thường **hơi cong nhẹ** theo đường mép bead (không thẳng tuyệt đối, không zigzag).

## Phân biệt với defect gần giống

| Defect | Vị trí | Hình dạng |
|--------|--------|-----------|
| **Undercut** | dọc TOE (mép bead) | rãnh dài liên tục, mảnh, bám mép, hơi cong theo mép |
| LOF (lack of fusion) | thành vách rãnh, off-center 13-20% | dải ngắn, đầy, 1 cạnh sắc |
| LOSWF | thành vách, off-center 18-28% | dải dài nghiêng theo bevel |
| LOP | tâm mối hàn (root) | đường thẳng mảnh dead-center |
| Crack | bất kỳ | zigzag random, hairline, có thể phân nhánh |

**Điểm nhấn:** undercut khác LOF/LOSWF ở chỗ nó **bám MÉP bead (toe)**, không phải thành vách; và **dài + liên tục** hơn, **theo đường cong của mép** bead.

## Yêu cầu cho mask generator (sửa script)

Script cũ ([undercut-mask-generator.py](../pipeline/mask_generator/undercut-mask-generator.py)) vẽ đường gần thẳng, offset cố định 5-15px, waviness ±1px — CHƯA phản ánh thực tế. Cần:

1. **Bám mép bead (toe)**, không phải offset tùy tiện — đặt tại ranh giới weld_zone (≈ mép bead), sát mép.
2. **DÀI hơn** (0.4-0.85 chiều rộng) và **LIÊN TỤC** (không gap).
3. **Đường cong nhẹ** theo mép bead (low-frequency wave), không thẳng cứng, không zigzag.
4. **Bề rộng nhỏ nhưng có thể thay đổi dọc theo** (rãnh chỗ sâu chỗ nông) — 2-6px, biến thiên mượt.
5. Tùy chọn xuất hiện **cả 2 mép** (trên + dưới) đôi khi, hoặc 1 mép.
6. Biên phía bead sắc, phía nền nhòe (feather không đối xứng nếu làm được, hoặc feather nhẹ 2-3px).
