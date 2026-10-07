// Two operator buttons under batch control: "Nơi lưu output" (per-run folders, open/copy)
// and "Tắt/bật ComfyUI" (U-902 unit, stop refused while a batch runs, two-step stop).
// Controls are built once and updated in place, so a poll never steals a click or focus.
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';
import { visiblePolling } from './plant-hmi-visible-polling.js';
import { evaluationBlock } from './plant-hmi-run-evaluation.js';

const BASE = '/plant-hmi/api/control/tools';
const TIP_OUTPUT = 'Bước 10 · Nơi lưu output: mỗi lần Start ghi vào thư mục riêng '
  + 'output/synthetic/<ngày_giờ>_<tên config>/ (ảnh theo defect, checkpoints/, logs/). '
  + 'Bấm để xem các lần chạy gần nhất, mở thư mục hoặc sao chép đường dẫn.';
const TIP_COMFY = 'Bước 11 · Tắt/bật ComfyUI (U-902): máy sinh ảnh chạy trên GPU RTX 3090. '
  + 'Bật trước khi Start batch; tắt khi không dùng để giải phóng VRAM. '
  + 'Không tắt được khi đang có batch chạy.';

async function call(path, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
  };
  const res = await fetch(`${BASE}${path}`, { ...opts, cache: 'no-store' });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
  return data;
}

export function initOperatorTools(root) {
  const note = h('div', { class: 'ot-note' });
  const say = (text, bad = false) => { note.textContent = text; note.classList.toggle('bad', bad); };

  // ---- Bước 10: output folders ----
  const runsList = h('div', { class: 'ot-runs', hidden: '' });
  const outBtn = h('button', { class: 'ot-btn', 'data-tip': TIP_OUTPUT, 'aria-label': TIP_OUTPUT,
    onclick: () => { runsList.hidden = !runsList.hidden; if (!runsList.hidden) loadRuns(); } },
  '📁 Nơi lưu output');

  function runRow(run) {
    const open = h('button', { class: 'ot-mini', title: 'Mở thư mục này trên màn hình máy chạy HMI',
      onclick: async () => {
        try { await call('/open', { name: run.name }); say(`Đã mở ${run.path}`); }
        catch (e) { say(`Không mở được: ${e.message}`, true); }
      } }, 'Mở thư mục');
    const copy = h('button', { class: 'ot-mini', title: 'Sao chép đường dẫn để dán vào terminal/post-processing',
      onclick: async () => {
        try { await navigator.clipboard.writeText(run.path); say('Đã sao chép đường dẫn'); }
        catch { say(run.path); }   // clipboard needs https/localhost: show the path instead
      } }, 'Sao chép');
    const ev = evaluationBlock(run, call, say);
    return h('div', { class: 'ot-run' },
      h('div', { class: 'ot-run-name' }, run.name),
      h('div', { class: 'ot-run-meta' }, `${run.images} ảnh · ${fmtTime(run.modified)}`),
      h('div', { class: 'ot-run-actions' }, open, copy, ev.button),
      ev.panel);
  }

  async function loadRuns() {
    try {
      const data = await call('/runs');
      runsList.replaceChildren(
        h('div', { class: 'ot-root' }, `Gốc: ${data.root}/`),
        ...(data.runs.length ? data.runs.map(runRow)
          : [h('div', { class: 'ot-empty' }, 'Chưa có lần chạy nào từ HMI')]));
    } catch (e) { say(`Không tải được danh sách: ${e.message}`, true); }
  }

  // ---- Bước 11: ComfyUI on/off ----
  const dot = h('span', { class: 'ot-dot' });
  const comfyLabel = h('span', {}, 'ComfyUI');
  const comfyBtn = h('button', { class: 'ot-btn', 'data-tip': TIP_COMFY, 'aria-label': TIP_COMFY }, dot, comfyLabel);
  const confirmBox = h('span', { class: 'ot-confirm', hidden: '' });
  let state = null;
  let busy = false;

  async function toggle(action) {
    busy = true; comfyBtn.disabled = true; confirmBox.hidden = true;
    say(action === 'start' ? 'Đang bật ComfyUI (~15 s)…' : 'Đang tắt ComfyUI…');
    try { await call('/comfyui', { action, reason: 'nút Bước 11 trên HMI' }); }
    catch (e) { say(`Không ${action === 'start' ? 'bật' : 'tắt'} được: ${e.message}`, true); }
    busy = false; refreshComfy();
  }

  comfyBtn.addEventListener('click', () => {
    if (!state || busy) return;
    if (!state.unit_active) { toggle('start'); return; }
    confirmBox.replaceChildren(
      'Tắt ComfyUI? ',
      h('button', { class: 'ot-mini danger', onclick: () => toggle('stop') }, 'Xác nhận tắt'),
      h('button', { class: 'ot-mini', onclick: () => { confirmBox.hidden = true; } }, 'Huỷ'));
    confirmBox.hidden = false;
  });

  async function refreshComfy() {
    try { state = await call('/comfyui'); } catch { return; }
    const on = !!state.unit_active;
    const ready = state.http_ok === true;
    dot.className = `ot-dot ${on ? (ready ? 'on' : 'warm') : 'off'}`;
    comfyLabel.textContent = on ? (ready ? 'ComfyUI đang chạy · Tắt' : 'ComfyUI đang khởi động…') : 'Bật ComfyUI';
    const lockStop = on && state.batch_running;
    comfyBtn.disabled = busy || lockStop;
    const tip = lockStop ? 'Đang có batch chạy: dừng batch trước rồi mới tắt ComfyUI' : TIP_COMFY;
    comfyBtn.dataset.tip = tip;
    comfyBtn.setAttribute('aria-label', tip);
    if (!busy && note.textContent.startsWith('Đang bật') && ready) say('ComfyUI đã sẵn sàng');
  }

  root.replaceChildren(h('div', { class: 'ot-bar' }, outBtn, comfyBtn, confirmBox), runsList, note);
  visiblePolling(refreshComfy, 3000);
}
