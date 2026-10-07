// Side-panel renderers (alarms, live batches, utilities, equipment detail) shared by Live and
// Replay: both feed the same snapshot shape, so these functions do not care which mode is active.
import { renderAlarmList } from './plant-hmi-alarm-list.js';

export const $ = (id) => document.getElementById(id);
export const fmt = (v, d = 0) => (v === null || v === undefined ? '—'
  : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d }));
export const clock = (ts) => new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour12: false });

export function duration(s) {
  if (s === null || s === undefined) return '—';
  s = Math.max(0, Math.round(s));
  const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60);
  return hh ? `${hh} giờ ${mm} phút` : mm ? `${mm} phút ${s % 60} s` : `${s} s`;
}

// Tiny DOM builder: children are nodes or strings (always set as text, never HTML).
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style') node.style.cssText = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) node.append(c);
  return node;
}

function kv(pairs) {
  return h('dl', { class: 'kv' }, pairs.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, String(v ?? '—'))]));
}

function bar(ratio, color) {
  const pct = ratio === null || ratio === undefined || Number.isNaN(ratio)
    ? 0 : Math.max(0, Math.min(1, ratio)) * 100;
  return h('div', { class: 'bar' }, h('i', { style: `width:${pct}%;--c:${color || 'var(--product)'}` }));
}

export function setConn(ok, msg) {
  $('conn').dataset.ok = ok ? '1' : '0';
  $('conn-text').textContent = msg;
}

// Ack/shelve mutate state server-side; this refetches the snapshot right away so the alarm
// card reflects the change without waiting for the next regular 3 s poll (which also
// re-renders through the same persistent-row path, so there is no double-render bug).
async function refreshAlarmsNow() {
  try {
    const res = await fetch('/plant-hmi/api/snapshot', { cache: 'no-store' });
    if (!res.ok) return;
    const fresh = await res.json();
    renderAlarmList($('alarms'), fresh, refreshAlarmsNow);
  } catch { /* the regular poll loop will pick up the change next tick */ }
}

export function renderAlarms(snap) {
  renderAlarmList($('alarms'), snap, refreshAlarmsNow);
}

export function renderBatches(snap) {
  const box = $('batches');
  box.replaceChildren();
  if (!snap.batches.length) return box.append(h('div', { class: 'empty' }, 'Không có batch nào đang chạy'));
  for (const b of snap.batches) {
    const ratio = b.target ? b.produced / b.target : null;
    box.append(h('div', { class: 'batch' },
      h('div', { class: 'util-row' },
        h('div', { class: 'line' }, h('span', {}, `pid ${b.pid}${b.pilot ? ' · pilot' : ''}`),
          h('b', {}, `${fmt(b.produced)} / ${fmt(b.target)} ảnh`)),
        bar(ratio, 'var(--run)')),
      kv([['config', b.config_name], ['đã chạy', duration(b.uptime_s)],
        ['tốc độ 10 phút', b.rate_img_h === null ? '—' : `${fmt(b.rate_img_h)} ảnh/giờ`],
        ['còn lại (ước tính)', duration(b.eta_s)], ['job hỏng (run này)', fmt(b.failed)],
        ['thử lại / hỏng 15 phút', snap.flows.has_telemetry
          ? `${fmt(snap.flows.jobs.retry_15m)} / ${fmt(snap.flows.jobs.failed_15m)}` : '— (chưa có telemetry)'],
        ['ảnh mới nhất', b.newest_image_ts ? clock(b.newest_image_ts) : '—']])));
  }
}

function utilRow(label, value, ratio, warn) {
  const color = warn === 'HI' ? 'var(--hi)' : warn === 'LO' ? 'var(--lo)' : 'var(--product)';
  return h('div', { class: 'util-row' },
    h('div', { class: 'line' }, h('span', { class: 'muted' }, label), h('b', {}, value)),
    ratio === undefined ? null : bar(ratio, color));
}

export function renderUtilities(snap) {
  const { gpu, comfy, host } = snap.utilities;
  const alarmOf = (tag) => (snap.alarms.find((a) => a.tag === tag) || {}).severity;
  const NO_REPLAY_DATA = 'không có dữ liệu khi phát lại';
  const rows = [
    h('div', { class: 'util-group' }, `U-901 · GPU cục bộ ${gpu.name ? `(${gpu.name.replace('NVIDIA GeForce ', '')})` : ''}`),
    gpu.unavailable ? utilRow('trạng thái', NO_REPLAY_DATA)
      : gpu.ok === false || gpu.ok === undefined ? utilRow('trạng thái', gpu.ok === false ? 'không đọc được' : 'chưa rõ') : [
        utilRow('nhiệt độ', `${fmt(gpu.temp_c)} °C`, gpu.temp_c / 90, alarmOf('U-901')),
        utilRow('tải', `${fmt(gpu.util_pct)} %`, gpu.util_pct / 100),
        utilRow('VRAM', `${fmt(gpu.vram_used_mib / 1024, 1)} / ${fmt(gpu.vram_total_mib / 1024, 0)} GiB`,
          gpu.vram_used_mib / gpu.vram_total_mib),
      ],
    h('div', { class: 'util-group' }, 'U-902 · ComfyUI'),
    comfy.unavailable ? utilRow('trạng thái', NO_REPLAY_DATA) : [
      utilRow('máy chủ', comfy.url || '—'),
      utilRow('trạng thái', comfy.ok === true ? 'sẵn sàng' : comfy.ok === false ? 'mất kết nối' : 'chưa rõ'),
      comfy.ok ? utilRow('hàng đợi chạy / chờ', `${fmt(comfy.queue_running)} / ${fmt(comfy.queue_pending)}`) : null,
      comfy.ok && comfy.vram_total_mib ? utilRow('VRAM trống', `${fmt(comfy.vram_free_mib / 1024, 1)} GiB`,
        1 - comfy.vram_free_mib / comfy.vram_total_mib) : null,
    ],
    h('div', { class: 'util-group' }, 'U-903 · Máy chủ'),
    host.unavailable ? utilRow('trạng thái', NO_REPLAY_DATA) : [
      utilRow('RAM trống', `${fmt(host.mem_avail_gib, 1)} / ${fmt(host.mem_total_gib, 0)} GiB`,
        1 - (host.mem_avail_pct ?? 0) / 100, alarmOf('U-903')),
      utilRow('swap', `${fmt(host.swap_pages_s)} trang/s · ${fmt(host.swap_used_gib, 1)} GiB`),
      utilRow('tải CPU (1 phút)', `${fmt(host.load1, 1)} / ${fmt(host.ncpu)} luồng`, (host.load_pct ?? 0) / 100),
    ],
  ];
  $('utilities').replaceChildren(...rows.flat().filter(Boolean));
}

export function renderDetail(snap, selected) {
  const box = $('detail');
  if (!selected) {
    $('detail-title').textContent = 'Chi tiết thiết bị';
    return box.replaceChildren(h('div', { class: 'empty' }, 'Bấm vào một thiết bị trên sơ đồ'));
  }
  const eq = snap.equipment[selected] || {};
  $('detail-title').textContent = `${selected} · ${eq.label || 'ComfyUI server'}`;
  const st = (snap.flows.stages || {})[selected];
  if (selected === 'U-902') {
    const c = snap.utilities.comfy;
    const p = (c.procs || [])[0];
    return box.replaceChildren(kv([['URL (config)', c.url], ['trạng thái', c.ok === true ? 'sẵn sàng' : c.ok === false ? 'mất kết nối' : 'chưa rõ'],
      ['host là máy này', c.host_local === true ? 'có' : c.host_local === false ? 'KHÔNG' : '—'],
      ['tiến trình', p ? `pid ${p.pid} · nghe ${p.listen}:${p.port}` : 'không chạy'],
      ['lỗi', c.error], ['thiết bị', c.device], ['đo lúc', c.probed_ts ? clock(c.probed_ts) : '—']]));
  }
  if (selected === 'U-901') {
    const g = snap.utilities.gpu;
    $('detail-title').textContent = 'U-901 · GPU (chung cho ComfyUI và train)';
    return box.replaceChildren(kv([['GPU', g.name], ['nhiệt độ', `${fmt(g.temp_c)} °C`], ['tải', `${fmt(g.util_pct)} %`],
      ['VRAM', `${fmt(g.vram_used_mib)} / ${fmt(g.vram_total_mib)} MiB`], ['công suất', `${fmt(g.power_w)} W`],
      ['chờ nguội', snap.flows.thermal_hold ? 'đang chờ' : 'không']]));
  }
  const alarms = snap.alarms.filter((a) => a.tag === selected).map((a) => [`báo động ${a.severity}`, a.code]);
  box.replaceChildren(kv([['trạng thái', eq.state === 'running' ? 'đang chạy' : 'nghỉ'],
    ['mức', eq.level === undefined ? '—' : `${fmt(eq.level)} ${eq.unit || ''}${eq.max ? ` / ${fmt(eq.max)}` : ''}`],
    ...(st ? [['đang xử lý', st.running], ['lỗi 5 phút', st.errors_5m],
      ...Object.entries(st.p50_ms).map(([k, v]) => [`p50 ${k}`, `${fmt(v)} ms`])] : []),
    ...alarms, ...Object.entries(eq.details || {})]));
}
