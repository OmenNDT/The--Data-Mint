"""Playwright automation: test LoRA Training tab on Gradio UI.

Runs headless with screenshots at every step for visual review.
"""

import time
from playwright.sync_api import sync_playwright

LAUNCHER_URL = "http://localhost:7860"
TEST_EPOCHS = 2


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1500)
        page = browser.new_page(viewport={"width": 1400, "height": 1200})

        print("1. Mở launcher UI...")
        page.goto(LAUNCHER_URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        print("2. Chuyển sang tab Training LoRA...")
        page.get_by_role("tab", name="Training LoRA").click()
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/training-ui-01-initial.png", full_page=True)

        print("3. Kiểm tra trạng thái training...")
        page.get_by_role("button", name="Làm mới trạng thái").click()
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        if "Không có training nào đang chạy" in body:
            print("   ✅ Không có training đang chạy")
        elif "Training đang chạy" in body:
            print("   🔄 Có training đang chạy")
        page.screenshot(path="/tmp/training-ui-02-status.png", full_page=True)

        print("4. Kiểm tra Output paths...")
        if "Model cuối cùng" in body:
            print("   ✅ Output paths OK")

        print("5. Chọn defect = crack (trigger change event)...")
        # Gradio 6: find the visible dropdown near "Loại khuyết tật" label
        defect_input = page.locator("span:has-text('Loại khuyết tật')").locator("../..").locator("input[role='listbox']")
        print(f"   Giá trị hiện tại: '{defect_input.input_value()}'")
        defect_input.click()
        page.wait_for_timeout(500)
        page.locator("li:has-text('crack')").first.click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/training-ui-03-crack-selected.png", full_page=True)
        print("   ✅ Đã chọn crack")

        print("6. Kiểm tra dataset path...")
        ds = page.locator("span:has-text('Thư mục Training Data')").locator("../..").locator("textarea").first
        ds_val = ds.input_value()
        print(f"   Dataset: {ds_val}")
        if "training_data/crack" in ds_val:
            print("   ✅ Dataset path đúng")
        else:
            print(f"   ⚠️ Dataset path khác mong đợi")

        print("7. Mở Advanced params...")
        page.locator("button:has-text('Tham số chuyên sâu')").first.click()
        page.wait_for_timeout(1000)
        page.screenshot(path="/tmp/training-ui-04-advanced.png", full_page=True)

        # Verify params loaded from config
        body = page.locator("body").inner_text()
        for param in ["AdamW8bit", "cosine_with_restarts"]:
            status = "✅" if param in body else "⚠️"
            print(f"   {status} {param}")

        print(f"8. Đặt Epochs = {TEST_EPOCHS} (test nhanh)...")
        # Find Epochs number input
        epochs_el = page.locator("span:has-text('Epochs')").first.locator("..").locator("input")
        epochs_el.click(click_count=3)
        epochs_el.fill(str(TEST_EPOCHS))
        page.wait_for_timeout(300)
        page.screenshot(path="/tmp/training-ui-05-ready.png", full_page=True)

        print("9. Nhấn 'Bắt đầu Training'...")
        page.get_by_role("button", name="Bắt đầu Training").click()
        page.wait_for_timeout(5000)
        page.screenshot(path="/tmp/training-ui-06-started.png", full_page=True)

        # Check if cancel button appeared
        cancel_visible = page.get_by_role("button", name="Hủy Training").is_visible()
        print(f"   Cancel button visible: {cancel_visible}")

        print("10. Theo dõi training (tối đa 5 phút)...")
        max_wait = 300
        start = time.time()
        idx = 7

        while time.time() - start < max_wait:
            page.wait_for_timeout(10000)
            elapsed = int(time.time() - start)

            # Get log textarea - find by label "Log"
            log_el = page.locator("label:has-text('Log')").locator("..").locator("textarea").first
            log_text = log_el.input_value() if log_el.is_visible() else ""

            last_line = log_text.strip().split("\n")[-1] if log_text.strip() else "(trống)"
            print(f"    [{elapsed}s] {last_line[:120]}")

            if elapsed % 60 < 15:
                page.screenshot(path=f"/tmp/training-ui-{idx:02d}-{elapsed}s.png", full_page=True)
                idx += 1

            if "hoàn thành" in log_text:
                print("    ✅ Training hoàn thành!")
                break
            if "thất bại" in log_text or "❌ Lỗi" in log_text:
                print("    ❌ Training lỗi!")
                break
            if "đã hủy" in log_text:
                print("    ⏹️ Đã hủy")
                break

        page.screenshot(path="/tmp/training-ui-final.png", full_page=True)
        print(f"\nFinal: /tmp/training-ui-final.png")

        log_el = page.locator("label:has-text('Log')").locator("..").locator("textarea").first
        final_log = log_el.input_value() if log_el.is_visible() else "(empty)"
        print(f"\n{'='*50}\nFINAL LOG:\n{'='*50}\n{final_log[-1500:]}")

        page.wait_for_timeout(3000)
        browser.close()
        print("\nDone!")


if __name__ == "__main__":
    run()
