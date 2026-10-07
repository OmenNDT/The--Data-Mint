// Trend panel: tag picker grouped by equipment (from /api/history/tags), time windows
// 1h/6h/24h/run, one small SVG line chart per selected tag with a hover readout.
const BASE = '/plant-hmi/api/history';
const SVG_NS = 'http://www.w3.org/2000/svg';
const WINDOWS = [['1h', '1 giờ', 3600], ['6h', '6 giờ', 21600], ['24h', '24 giờ', 86400], ['run', 'run hiện tại', null]];
const COLORS = ['#5ec8d8', '#c9a15e', '#9a8cd0', '#7fbf7f', '#d0655f', '#8a8aa0'];

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style') node.style.cssText = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) node.append(c);
  return node;
}
function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
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

// Splits ascending [ts, value] points into runs with no internal gap wider than 2x the
// server's sample step, so the polyline never draws a misleading line across a data hole (L9).
function splitByGap(points, step) {
  if (!step) return [points];
  const groups = [];
  let cur = [points[0]];
  for (let i = 1; i < points.length; i += 1) {
    if (points[i][0] - points[i - 1][0] > 2 * step) { groups.push(cur); cur = []; }
    cur.push(points[i]);
  }
  groups.push(cur);
  return groups;
}

function renderChart(tag, meta, series, step, color) {
  const w = 560, hgt = 90, pad = 6;
  const svg = svgEl('svg', { viewBox: `0 0 ${w} ${hgt}`, class: 'trend-svg', style: `--c:${color}` });
  const readout = h('span', { class: 'trend-readout' }, '');
  const box = h('div', { class: 'trend-chart' },
    h('div', { class: 'trend-chart-title' }, `${meta.label || tag}${meta.unit ? ` (${meta.unit})` : ''}`),
    svg, readout);
  const points = (series || []).filter(([, v]) => v !== null && v !== undefined);
  if (points.length < 2) {
    svg.append(svgEl('text', { x: w / 2, y: hgt / 2, class: 'trend-empty', 'text-anchor': 'middle' }));
    svg.lastChild.textContent = 'chưa có dữ liệu';
    return box;
  }
  const [t0] = points[0], [t1] = points[points.length - 1];
  const values = points.map(([, v]) => v);
  const minV = Math.min(...values), maxV = Math.max(...values);
  const spanV = maxV - minV || 1;
  const x = (t) => pad + ((t - t0) / (t1 - t0 || 1)) * (w - 2 * pad);
  const y = (v) => hgt - pad - ((v - minV) / spanV) * (hgt - 2 * pad);
  for (const group of splitByGap(points, step)) {
    if (group.length < 2) continue;
    svg.append(svgEl('polyline', { points: group.map(([t, v]) => `${x(t)},${y(v)}`).join(' '), class: 'trend-line' }));
  }
  const dot = svgEl('circle', { r: 3, class: 'trend-dot', style: 'display:none' });
  svg.append(dot);
  // Map the mouse position through the SVG's own CTM so the readout stays correct no matter
  // how the viewport is scaled/stretched by CSS (M2), instead of assuming a proportional fit.
  svg.addEventListener('mousemove', (e) => {
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const loc = pt.matrixTransform(ctm.inverse());
    const t = t0 + ((loc.x - pad) / (w - 2 * pad)) * (t1 - t0);
    let nearest = points[0];
    for (const p of points) if (Math.abs(p[0] - t) < Math.abs(nearest[0] - t)) nearest = p;
    dot.setAttribute('cx', x(nearest[0])); dot.setAttribute('cy', y(nearest[1]));
    dot.style.display = '';
    readout.textContent = `${new Date(nearest[0] * 1000).toLocaleTimeString('vi-VN', { hour12: false })} · ` +
      `${Number(nearest[1]).toLocaleString('vi-VN', { maximumFractionDigits: 2 })}`;
  });
  svg.addEventListener('mouseleave', () => { dot.style.display = 'none'; readout.textContent = ''; });
  return box;
}

export function initTrendPanel(root, { getRunRange } = {}) {
  let tags = [];
  const selected = new Set();
  let windowKey = '1h';
  let seq = 0;                    // sequence token guards against out-of-order refresh (M3)
  const winWrap = h('div', { class: 'trend-windows' });
  const tagWrap = h('div', { class: 'trend-tags' });
  const chartWrap = h('div', { class: 'trend-charts' });
  const status = h('div', { class: 'muted' }, 'đang tải danh sách tag…');
  root.replaceChildren(winWrap, tagWrap, chartWrap, status);

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
    if (!selected.size) { chartWrap.replaceChildren(); status.textContent = 'chọn ít nhất một tag để xem xu hướng'; return; }
    const range = windowRange();
    if (!range) { chartWrap.replaceChildren(); status.textContent = 'chưa chọn run để xem cửa sổ "run"'; return; }
    status.textContent = 'đang tải dữ liệu…';
    try {
      const list = [...selected];
      const q = `tags=${list.join(',')}&from=${range[0]}&to=${range[1]}`;
      const body = await getJson(`${BASE}/samples?${q}`);
      if (mySeq !== seq) return;                  // a newer refresh finished first: drop this one
      chartWrap.replaceChildren(...list.map((tag, i) => {
        const meta = tags.find((t) => t.tag === tag) || {};
        return renderChart(tag, meta, (body.series || {})[tag] || [], body.step, COLORS[i % COLORS.length]);
      }));
      status.textContent = '';
    } catch {
      if (mySeq !== seq) return;
      chartWrap.replaceChildren();
      status.textContent = 'chưa có dữ liệu historian';
    }
  }

  async function loadTags() {
    try {
      tags = await getJson(`${BASE}/tags`);
      const groups = new Map();
      for (const t of tags) {
        const key = t.equipment || '—';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(t);
      }
      tagWrap.replaceChildren();
      for (const [equip, list] of groups) {
        const row = h('div', { class: 'trend-group' });
        for (const t of list) {
          const b = h('button', { class: 'trend-tag', type: 'button', 'aria-pressed': 'false' }, t.label || t.tag);
          b.addEventListener('click', () => {
            const isActive = b.getAttribute('aria-pressed') === 'true';
            b.setAttribute('aria-pressed', String(!isActive));
            if (isActive) selected.delete(t.tag); else selected.add(t.tag);
            refresh();
          });
          row.append(b);
        }
        tagWrap.append(h('div', { class: 'trend-group-label' }, equip), row);
      }
      status.textContent = tags.length ? 'chọn ít nhất một tag để xem xu hướng' : 'chưa có tag nào';
    } catch {
      status.textContent = 'chưa có dữ liệu historian';
    }
  }

  loadTags();
  return { refresh };
}
