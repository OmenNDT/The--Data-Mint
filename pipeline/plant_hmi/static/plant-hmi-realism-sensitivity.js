// Mục "Độ nhạy núm" (bước 4, plan 261002-1430): nút chạy pilot / đầy đủ, tiến độ, bảng nhiệt
// núm (biến thể) × mục tiêu (nhãn issues.py) + cột C2ST từng cặp. Module độc lập (ES module,
// không phụ thuộc plant-hmi-realism-app.js ngoài sự kiện 'realism-refresh' nó phát mỗi 3 giây
// để đồng bộ nhịp poll, tránh mở hai bộ đếm giờ riêng). DOM dựng bằng `h` (addEventListener),
// không bao giờ dùng setAttribute('onclick', ...) trên chuỗi.
import { h } from './plant-hmi-setpoint-dom.js';

const $ = (id) => document.getElementById(id);
let armedBtn = null;
let armTimer = null;

function fmtNum(x, digits = 3) {
  return x === null || x === undefined || Number.isNaN(x)
    ? '—' : Number(x).toLocaleString('vi-VN', { maximumFractionDigits: digits });
}

function fmtSigned(x, digits = 3) {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  return Number(x).toLocaleString('vi-VN', { maximumFractionDigits: digits, signDisplay: 'always' });
}

function knobChangeLabel(changed) {
  return Object.entries(changed || {}).map(([k, pair]) => {
    const [a, b] = Array.isArray(pair) ? pair : [null, null];
    return `${k} ${fmtNum(a)}→${fmtNum(b)}`;
  }).join(', ');
}

// Mức màu theo cột (chuẩn hoá |delta| trong cùng cột để so sánh được các biến thể với nhau).
function colScale(values) {
  const mags = values.filter((v) => v !== null && v !== undefined && !Number.isNaN(v)).map((v) => Math.abs(v));
  const max = mags.length ? Math.max(...mags, 1e-9) : 1;
  return (v) => (v === null || v === undefined || Number.isNaN(v) ? 0 : Math.min(1, Math.abs(v) / max));
}

function cellClass(helps, delta) {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return 'sens-cell neutral';
  if (helps === true) return 'sens-cell helps';
  if (helps === false) return 'sens-cell hurts';
  return 'sens-cell neutral';
}

function targetLabels(sens) {
  const seen = new Set();
  for (const v of sens.variants || []) {
    for (const label of Object.keys((sens.effects?.[v.id] || {}).targets || {})) seen.add(label);
  }
  return [...seen];
}

function pairNames(sens) {
  const seen = new Set();
  for (const v of sens.variants || []) {
    for (const p of Object.keys((sens.effects?.[v.id] || {}).c2st || {})) seen.add(p);
  }
  return [...seen];
}

function renderHeat(container, sens) {
  container.replaceChildren();
  if (!sens || !Array.isArray(sens.variants) || !sens.variants.length) {
    container.append(h('p', { class: 'msg' }, 'Chưa có kết quả đo.'));
    return;
  }
  const labels = targetLabels(sens);
  const pairs = pairNames(sens);
  const scales = labels.map((label) => colScale(sens.variants.map(
    (v) => (sens.effects?.[v.id]?.targets || {})[label]?.delta)));

  const head = h('tr', {}, h('th', {}, 'Biến thể'),
    ...labels.map((l) => h('th', { title: l }, l.length > 24 ? l.slice(0, 22) + '…' : l)),
    ...pairs.map((p) => h('th', { title: 'C2ST ' + p }, 'C2ST ' + p)));

  const rows = sens.variants.map((v) => {
    const eff = sens.effects?.[v.id] || {};
    const targetCells = labels.map((label, i) => {
      const t = (eff.targets || {})[label];
      const delta = t ? t.delta : null;
      const scale = scales[i](delta);
      const style = delta === null || delta === undefined ? '' : `--mag:${scale.toFixed(2)}`;
      const cls = cellClass(t ? t.helps : null, delta) + (t && t.significant ? ' sig' : '');
      const title = t
        ? `Δ ghép cặp ${fmtNum(t.delta)} trên ${t.n_common} ca chung`
          + ` · cả bộ: trước ${fmtNum(t.prev)} → sau ${fmtNum(t.new)}`
          + (t.ci_low !== undefined && t.ci_low !== null ? ` · CI 95% [${fmtNum(t.ci_low)}, ${fmtNum(t.ci_high)}]` : '')
        : 'không đo ở biến thể này';
      return h('td', { class: cls, style, title }, fmtSigned(delta));
    });
    const c2stCells = pairs.map((p) => {
      const c = (eff.c2st || {})[p];
      const title = c ? `gốc ${fmtNum(c.base)} → sau ${fmtNum(c.new)}` : 'không đo';
      return h('td', { class: 'sens-c2st', title }, c ? fmtSigned(c.delta) : '—');
    });
    return h('tr', {},
      h('td', { class: 'vid', title: `${v.group} ${v.sign > 0 ? '+' : '−'}` },
        h('b', {}, v.id), h('div', { class: 'msg' }, knobChangeLabel(v.changed))),
      ...targetCells, ...c2stCells);
  });

  container.append(h('table', { class: 'sens-heat' }, h('thead', {}, head), h('tbody', {}, ...rows)));
}

const JOB_LABEL = { idle: 'rảnh', running: 'đang chạy', done: 'xong', failed: 'lỗi', stopped: 'đã dừng', dead: 'tiến trình đã chết' };

function renderProgress(j) {
  if (!j || j.state === 'idle') return 'Chưa chạy lượt nào';
  if (j.state === 'running') {
    let s = j.variant ? `biến thể ${j.variant} (${j.variant_index ?? '?'}/${j.variant_total ?? '?'})` : (j.stage || 'đang chạy');
    if (j.gen_total) s += `: ${j.gen_done ?? 0}/${j.gen_total} ảnh`;
    return s;
  }
  return `Lượt ${j.run_id}: ${JOB_LABEL[j.state] || j.state}` + (j.error ? ' · ' + j.error : '');
}

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
    body: JSON.stringify(body || {}),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || ('lỗi ' + r.status));
  return d;
}

function arm(btn, run) {
  if (armedBtn !== btn) {
    if (armedBtn) { armedBtn.classList.remove('armed'); armedBtn.textContent = armedBtn.dataset.label; }
    armedBtn = btn;
    btn.dataset.label = btn.dataset.label || btn.textContent;
    btn.classList.add('armed');
    btn.textContent = btn.dataset.arm + ' Bấm lần nữa';
    clearTimeout(armTimer);
    armTimer = setTimeout(() => { btn.classList.remove('armed'); btn.textContent = btn.dataset.label; armedBtn = null; }, 6000);
    return;
  }
  clearTimeout(armTimer);
  btn.classList.remove('armed');
  btn.textContent = btn.dataset.label;
  armedBtn = null;
  run();
}

async function start(pilot) {
  const n = parseInt($('sens-n').value, 10);
  try {
    await post('/plant-hmi/realism/api/sensitivity/start', { pilot, n_per_type: n });
    $('sens-source').className = 'msg';
    $('sens-source').textContent = 'Đã gửi lệnh chạy.';
  } catch (e) {
    $('sens-source').className = 'err';
    $('sens-source').textContent = e.message;
  }
  setTimeout(refresh, 800);
}

export async function refresh() {
  try {
    const data = await getJSON('/plant-hmi/realism/api/sensitivity');
    if (data.error) throw new Error(data.error);
    const running = data.job && data.job.state === 'running';
    $('sens-btn-pilot').disabled = running;
    $('sens-btn-full').disabled = running;
    $('sens-progress').textContent = renderProgress(data.job);
    $('sens-stale').style.display = data.stale ? '' : 'none';
    const sens = data.latest_pilot || data.latest;
    if (!running) {
      $('sens-source').className = 'msg';
      $('sens-source').textContent = data.latest_pilot ? 'Đang xem: kết quả chạy thử (pilot), chưa phải bản đủ.'
        : (data.latest ? `Đang xem: bản đủ, lượt ${data.latest.run_id || '—'}.` : 'Chưa đo lần nào.');
    }
    renderHeat($('sens-heat'), sens);
  } catch (e) {
    $('sens-source').className = 'err';
    $('sens-source').textContent = 'Không đọc được độ nhạy: ' + e.message;
  }
}

$('sens-btn-pilot').onclick = (e) => arm(e.currentTarget, () => start(true));
$('sens-btn-full').onclick = (e) => arm(e.currentTarget, () => start(false));
window.addEventListener('realism-refresh', refresh);
refresh();
