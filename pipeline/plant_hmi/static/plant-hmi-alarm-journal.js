// Alarm journal: table of historian alarm transitions (raised/cleared) with a time window,
// pulled from /api/history/alarms. Read-only, no polling (refresh on window change).
const BASE = '/plant-hmi/api/history';
const WINDOWS = [['1h', '1 giờ', 3600], ['6h', '6 giờ', 21600], ['24h', '24 giờ', 86400], ['run', 'run hiện tại', null]];

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style') node.style.cssText = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) node.append(c);
  return node;
}
async function getJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(url, { signal: ctrl.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally { clearTimeout(timer); }
}
const clockFmt = (ts) => (ts === null || ts === undefined ? '—'
  : new Date(ts * 1000).toLocaleString('vi-VN', { hour12: false }));
const STATE_LABEL = {
  raised: 'phát sinh', cleared: 'đã hết', acked: 'đã xác nhận',
  shelved: 'đã tạm tắt', unshelved: 'bỏ tạm tắt',
};

export function initAlarmJournal(root, { getRunRange } = {}) {
  let windowKey = '1h';
  let seq = 0;                    // sequence token guards against out-of-order refresh (M3)
  const winWrap = h('div', { class: 'trend-windows' });
  const tableWrap = h('div', { class: 'journal-table-wrap' });
  const status = h('div', { class: 'muted' }, 'đang tải…');
  root.replaceChildren(winWrap, tableWrap, status);

  for (const [key, label] of WINDOWS.map(([k, l]) => [k, l])) {
    const b = h('button', { class: `trend-win${key === windowKey ? ' active' : ''}`, type: 'button' }, label);
    b.addEventListener('click', () => {
      windowKey = key;
      for (const btn of winWrap.children) btn.classList.remove('active');
      b.classList.add('active');
      refresh();
    });
    winWrap.append(b);
  }

  function windowRange() {
    if (windowKey === 'run') {
      const r = getRunRange && getRunRange();
      return r || null;
    }
    const secs = WINDOWS.find(([k]) => k === windowKey)[2];
    const now = Date.now() / 1000;
    return [now - secs, now];
  }

  async function refresh() {
    const mySeq = ++seq;
    const range = windowRange();
    if (!range) { tableWrap.replaceChildren(); status.textContent = 'chưa chọn run để xem cửa sổ "run"'; return; }
    status.textContent = 'đang tải…';
    try {
      const q = `from=${range[0]}&to=${range[1]}&limit=200`;
      const rows = await getJson(`${BASE}/alarms?${q}`);
      if (mySeq !== seq) return;                  // a newer refresh finished first: drop this one
      if (!rows.length) { tableWrap.replaceChildren(); status.textContent = 'không có báo động trong khoảng này'; return; }
      const table = h('table', { class: 'journal-table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'thời gian'), h('th', {}, 'mã'), h('th', {}, 'tag'),
          h('th', {}, 'mức'), h('th', {}, 'trạng thái'))),
        h('tbody', {}, ...rows.map((r) => h('tr', { class: `${r.severity ? `sev-${r.severity} ` : ''}state-${r.state}` },
          h('td', {}, clockFmt(r.ts)), h('td', {}, r.code), h('td', {}, r.tag),
          h('td', {}, r.severity), h('td', {}, STATE_LABEL[r.state] || r.state)))));
      tableWrap.replaceChildren(table);
      status.textContent = '';
    } catch {
      if (mySeq !== seq) return;
      tableWrap.replaceChildren();
      status.textContent = 'chưa có dữ liệu historian';
    }
  }

  refresh();
  return { refresh };
}
