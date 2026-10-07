#!/usr/bin/env node
/**
 * record-demo-video.mjs
 * Quay video demo giao dien van hanh The Data Mint (Gradio, cong 7860).
 *
 * Cach chay:
 *   node Report/record-demo-video.mjs [thu-muc-khung-hinh]
 *
 * Dau ra:
 *   <thu-muc>/frame-000000.png ...   khung hinh PNG, 5 hinh moi giay
 *   <thu-muc>/captions.json          moc thoi gian tung phu de
 *
 * Luu y: giao dien co nhieu nut trung ten o cac tab khac nhau, phan lon bi an.
 * Moi thao tac deu loc theo phan tu DANG HIEN va xac nhan ket qua truoc khi di tiep.
 * Rieng nut chay pipeline chi bam sau khi da xac nhan che do Pilot duoc bat,
 * de khong lo khoi dong mot lo san xuat lon tren may nguoi dung.
 */

import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';

// Dung lai puppeteer da cai san trong skill chrome-devtools, khong cai them goi moi
const require = createRequire('/home/sontn/.claude/skills/chrome-devtools/scripts/');
const puppeteer = require('puppeteer');

const OUT = process.argv[2] || '/tmp/claude-1000/demo-frames';
const URL = 'http://127.0.0.1:7860';
const FPS = 5;
const WIDTH = 1600;
const HEIGHT = 900;

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

let frameIndex = 0;
let recording = true;
const captions = [];
let t0 = 0;

/** Doi phu de va ghi moc thoi gian. */
function say(text) {
  const at = (Date.now() - t0) / 1000;
  if (captions.length) captions[captions.length - 1].end = at;
  captions.push({ start: at, end: at + 999, text });
  console.log(`[${at.toFixed(1)}s] ${text}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Ban Chrome trong cache cua puppeteer khong khop phien ban, dung Chrome he thong
const CHROME = process.env.CHROME_PATH || '/usr/bin/google-chrome';

const browser = await puppeteer.launch({
  executablePath: fs.existsSync(CHROME) ? CHROME : undefined,
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
         `--window-size=${WIDTH},${HEIGHT}`],
});
const page = await browser.newPage();
await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 1 });

/** Vong lap chup khung hinh, chay song song voi kich ban thao tac. */
async function captureLoop() {
  const interval = 1000 / FPS;
  while (recording) {
    const started = Date.now();
    try {
      await page.screenshot({
        path: path.join(OUT, `frame-${String(frameIndex).padStart(6, '0')}.png`),
        optimizeForSpeed: true,
      });
      frameIndex += 1;
    } catch { /* trang dang dieu huong, bo qua khung hinh nay */ }
    const spent = Date.now() - started;
    if (spent < interval) await sleep(interval - spent);
  }
}

/**
 * Bam phan tu DANG HIEN co chuoi chu cho truoc.
 * Gradio dung ban sao trong `.visually-hidden` cho trinh doc man hinh; ban sao nay
 * van co kich thuoc khac khong nen phai loai truc tiep, khong the dua vao rect.
 */
async function clickVisibleWithText(selector, text) {
  return page.evaluate((sel, txt) => {
    const usable = (el) => {
      if (el.closest('.visually-hidden')) return false;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      const st = getComputedStyle(el);
      return st.visibility !== 'hidden' && st.display !== 'none';
    };
    const el = [...document.querySelectorAll(sel)]
      .find((e) => usable(e) && (e.textContent || '').includes(txt));
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.click();
    return true;
  }, selector, text);
}

/** Chuyen tab roi cho toi khi chinh nut tab do duoc danh dau la dang chon. */
async function openTab(tabLabel) {
  const clicked = await clickVisibleWithText('button[role="tab"]', tabLabel);
  if (!clicked) throw new Error(`Khong bam duoc tab: ${tabLabel}`);
  for (let i = 0; i < 20; i += 1) {
    await sleep(400);
    const ok = await page.evaluate((t) => {
      const b = [...document.querySelectorAll('button[role="tab"]')]
        .find((x) => (x.textContent || '').includes(t));
      return !!b && (b.className.includes('selected') || b.getAttribute('aria-selected') === 'true');
    }, tabLabel);
    if (ok) return;
  }
  throw new Error(`Tab ${tabLabel} khong chuyen duoc`);
}

/** Cuon muot toi vi tri y de video khong bi giat. */
async function smoothScrollTo(y, ms = 1200) {
  await page.evaluate(async (targetY, duration) => {
    const startY = window.scrollY;
    const delta = targetY - startY;
    const start = performance.now();
    await new Promise((resolve) => {
      function step(now) {
        const p = Math.min(1, (now - start) / duration);
        const ease = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        window.scrollTo(0, startY + delta * ease);
        if (p < 1) requestAnimationFrame(step); else resolve();
      }
      requestAnimationFrame(step);
    });
  }, y, ms);
}

console.log(`Mo ${URL} ...`);
await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 });
await sleep(2500);

t0 = Date.now();
captureLoop();

// --- Canh 1: trang chu, trang thai he thong -------------------------------
say('The Data Mint — giao diện vận hành một nút bấm');
await sleep(3500);
say('Thanh trạng thái: GPU sẵn sàng, ComfyUI đã kết nối');
await sleep(3500);

// --- Canh 2: tab Thiet lap -------------------------------------------------
say('Tab Thiết lập: chọn trong mười hai lớp khuyết tật theo ISO 6520-1');
await smoothScrollTo(300);
await sleep(4000);
say('Ảnh nền sạch cắt từ phim thật GDXray W0003');
await smoothScrollTo(680);
await sleep(3000);
say('Ba cấu hình sẵn: thử 500 ảnh, chuẩn 20.000 ảnh, đầy đủ 100.000 ảnh');
await smoothScrollTo(1020);
await sleep(3500);
say('Bốn giai đoạn: sinh ảnh, hậu xử lý, kiểm định chất lượng, đánh giá');
await smoothScrollTo(1380);
await sleep(3500);

// --- Canh 3: tab Tao Anh ---------------------------------------------------
await smoothScrollTo(0, 800);
await openTab('Tạo Ảnh');
say('Tab Tạo Ảnh: chọn mô hình nền và các mô hình LoRA đã huấn luyện');
await sleep(3500);
await smoothScrollTo(420);
say('Mỗi lớp khuyết tật một mô hình LoRA riêng, mỗi tệp khoảng 37 MB');
await sleep(4000);
await smoothScrollTo(900);
say('Phân bổ tỷ lệ sinh ảnh theo từng lớp');
await sleep(3500);

// --- Canh 4: bat pilot mode, xac nhan roi moi chay ------------------------
const pilotOn = await page.evaluate(() => {
  const cb = [...document.querySelectorAll('input[type=checkbox]')].find((c) => {
    const label = c.closest('label');
    return label && (label.textContent || '').includes('Pilot mode');
  });
  if (!cb) return { found: false, checked: false };
  cb.scrollIntoView({ block: 'center' });
  if (!cb.checked) cb.click();
  return { found: true, checked: cb.checked };
});
console.log('  Pilot mode:', JSON.stringify(pilotOn));
if (!pilotOn.found || !pilotOn.checked) {
  recording = false;
  await browser.close();
  throw new Error('Khong bat duoc che do Pilot — dung lai, khong bam chay de tranh lo lon');
}
say('Bật chế độ Pilot: sinh thử 5 ảnh, chạy hết toàn tuyến');
await sleep(3500);

say('Bấm chạy: sinh mặt nạ, gọi ComfyUI, tải ảnh về rồi hậu xử lý');
const ran = await clickVisibleWithText('button', 'Chạy Pipeline');
if (!ran) throw new Error('Khong bam duoc nut Chay Pipeline dang hien');
await sleep(2500);

// --- Canh 5: theo doi tien trinh that -------------------------------------
say('Nhật ký chạy theo thời gian thực, từng ảnh một');
const runStart = Date.now();
const MAX_RUN_MS = 180000;
let done = false;
const marks = [
  [18, 'Mỗi ảnh lưu kèm hạt giống và đường dẫn ảnh nền nên tái lập được'],
  [42, 'Thông lượng đo trên lô 500 ảnh: 1.097 ảnh mỗi giờ'],
  [70, 'Bộ điều phối tự thử lại tối đa 3 lần và giám sát nhiệt GPU'],
];
let markIndex = 0;
while (Date.now() - runStart < MAX_RUN_MS && !done) {
  await sleep(2500);
  const txt = await page.evaluate(() => document.body.innerText || '');
  if (/hoàn tất|hoàn thành|completed|✅|Done/i.test(txt)) done = true;
  const elapsed = (Date.now() - runStart) / 1000;
  if (markIndex < marks.length && elapsed > marks[markIndex][0]) {
    say(marks[markIndex][1]);
    markIndex += 1;
  }
}
say(done ? 'Lô sinh ảnh chạy xong' : 'Lô sinh ảnh vẫn đang chạy');
await sleep(4000);

// --- Canh 6: ket qua -------------------------------------------------------
try {
  await smoothScrollTo(0, 800);
  await openTab('Kết quả');
  say('Tab Kết quả: bảng chỉ số QA và mAP, điền sau khi chạy đủ các giai đoạn');
  await sleep(4500);
  await smoothScrollTo(500);
  await sleep(3500);
} catch (e) {
  console.log('Bo qua tab Ket qua:', e.message);
}

say('Mã nguồn, báo cáo và bộ dữ liệu nộp kèm');
await sleep(3500);

captions[captions.length - 1].end = (Date.now() - t0) / 1000;
recording = false;
await sleep(500);
fs.writeFileSync(path.join(OUT, 'captions.json'), JSON.stringify(captions, null, 1), 'utf8');
console.log(`\nDa ghi ${frameIndex} khung hinh vao ${OUT}`);
console.log(`Thoi luong: ${((Date.now() - t0) / 1000).toFixed(1)} giay`);
await browser.close();
