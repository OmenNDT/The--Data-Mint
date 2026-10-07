// P&ID of the image-generation area. GEOMETRY is the single source of coordinates:
// symbols, pipes, instrument bubbles and labels are all drawn from it, so moving one
// piece of equipment never desynchronises the rest (phase 2 particles reuse it too).

const NS = 'http://www.w3.org/2000/svg';

export const GEOMETRY = {
  view: { w: 1060, h: 450 },
  equipment: {
    'TK-102': { kind: 'tank', x: 40, y: 170, w: 100, h: 150, label: [90, 344] },
    'R-201': { kind: 'reactor', x: 200, y: 200, w: 110, h: 90, label: [255, 314] },
    'TK-101': { kind: 'tank', x: 330, y: 62, w: 100, h: 82, label: [380, 26] },
    'P-601': { kind: 'pump', cx: 560, cy: 245, r: 34, label: [546, 300], anchor: 'end' },
    'R-401': { kind: 'reactor', x: 650, y: 200, w: 120, h: 90, label: [710, 314] },
    'TK-801': { kind: 'silo', x: 880, y: 140, w: 130, h: 200, label: [945, 396] },
    'D-901': { kind: 'drain', x: 515, y: 350, w: 90, h: 50, label: [560, 422] },
    'U-902': { kind: 'utility', x: 575, y: 60, w: 170, h: 44, label: null, title: 'ComfyUI server' },
    'U-901': { kind: 'utility', x: 330, y: 372, w: 150, h: 44, label: null, title: 'GPU RTX 3090' },
  },
  pipes: [
    { id: 'p-queue', d: 'M140 245 H200', flow: true },
    { id: 'p-mask', d: 'M310 245 H526', flow: true },
    { id: 'p-bg', d: 'M380 144 V245', flow: true },
    { id: 'p-post', d: 'M594 245 H650', flow: true },
    { id: 'p-silo', d: 'M770 245 H880', flow: true },
    { id: 'p-drain', d: 'M560 279 V350', flow: false },
  ],
  signals: ['M640 104 L572 214', 'M480 380 L534 268'],  // U-902 and U-901 drive P-601
  instruments: {
    'LT-102': { cx: 90, cy: 118, to: [90, 170], unit: 'job chờ' },
    'XI-601': { cx: 470, cy: 175, to: [534, 223], unit: 'batch sống' },
    'SI-601': { cx: 825, cy: 180, to: [825, 245], unit: 'ảnh/giờ' },
    'LT-801': { cx: 945, cy: 96, to: [945, 140], unit: 'ảnh' },
    'KI-201': { cx: 225, cy: 150, to: [240, 200], unit: 's/mask' },
    'KI-601': { cx: 470, cy: 118, to: [545, 214], unit: 's/ảnh' },
    'KI-401': { cx: 695, cy: 150, to: [705, 200], unit: 's' },
  },
};

// Particle anchor of each unit (resident position); routes are orthogonal between anchors.
export function anchor(tag) {
  const s = GEOMETRY.equipment[tag];
  if (!s) return null;
  if (s.kind === 'pump') return [s.cx, s.cy];
  if (tag === 'TK-102' || tag === 'TK-801') return [s.x + s.w / 2, 245];
  return [s.x + s.w / 2, s.y + s.h / 2];
}

function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function text(parent, x, y, content, cls, anchor = 'middle') {
  const t = el('text', { x, y, class: cls, 'text-anchor': anchor }, parent);
  t.textContent = content;
  return t;
}

function drawSymbol(g, tag, s) {
  if (s.kind === 'tank' || s.kind === 'drain') {
    const r = s.kind === 'drain' ? 8 : 16;
    el('clipPath', { id: `clip-${tag}` }, g).appendChild(
      el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: r }));
    el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: r, class: 'body', filter: 'url(#neu)' }, g);
    el('rect', { x: s.x, y: s.y + s.h, width: s.w, height: 0, class: 'fill',
      'clip-path': `url(#clip-${tag})`, 'data-fill': '' }, g);
    text(g, s.x + s.w / 2, s.y + s.h / 2 + 6, '—', 'value', 'middle').dataset.value = '';
  } else if (s.kind === 'silo') {
    const cone = s.y + s.h + 30;
    el('clipPath', { id: `clip-${tag}` }, g).appendChild(el('path', { d: siloPath(s, cone) }));
    el('path', { d: siloPath(s, cone), class: 'body', filter: 'url(#neu)' }, g);
    el('rect', { x: s.x, y: cone, width: s.w, height: 0, class: 'fill',
      'clip-path': `url(#clip-${tag})`, 'data-fill': '' }, g);
    text(g, s.x + s.w / 2, s.y + s.h / 2, '—', 'value').dataset.value = '';
  } else if (s.kind === 'reactor') {
    el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: s.h / 2.4, class: 'body', filter: 'url(#neu)' }, g);
    const cx = s.x + s.w / 2;
    el('path', { d: `M${cx} ${s.y + 14} V${s.y + s.h - 26} M${cx - 18} ${s.y + s.h - 26} H${cx + 18}`,
      class: 'agitator' }, g);
  } else if (s.kind === 'pump') {
    el('circle', { cx: s.cx, cy: s.cy, r: s.r, class: 'body', filter: 'url(#neu)' }, g);
    el('path', { d: `M${s.cx - 14} ${s.cy - 18} L${s.cx + 20} ${s.cy} L${s.cx - 14} ${s.cy + 18} Z`,
      class: 'impeller' }, g);
  } else if (s.kind === 'utility') {
    el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: 12, class: 'body util', filter: 'url(#neu)' }, g);
    text(g, s.x + s.w / 2, s.y + 19, tag, 'tag');
    text(g, s.x + s.w / 2, s.y + 35, s.title, 'sub').dataset.value = '';
  }
}

function siloPath(s, cone) {
  return `M${s.x} ${s.y + 14} Q${s.x} ${s.y} ${s.x + 14} ${s.y} H${s.x + s.w - 14} Q${s.x + s.w} ${s.y} ` +
    `${s.x + s.w} ${s.y + 14} V${s.y + s.h} L${s.x + s.w / 2 + 14} ${cone} H${s.x + s.w / 2 - 14} L${s.x} ${s.y + s.h} Z`;
}

export function buildDiagram(svg, equipmentLabels, onSelect) {
  const { view, equipment, pipes, signals, instruments } = GEOMETRY;
  svg.setAttribute('viewBox', `0 0 ${view.w} ${view.h}`);
  const defs = el('defs', {}, svg);
  const neu = el('filter', { id: 'neu', x: '-30%', y: '-30%', width: '160%', height: '160%' }, defs);
  el('feDropShadow', { dx: 5, dy: 5, stdDeviation: 5, 'flood-color': '#030305', 'flood-opacity': 0.9 }, neu);
  el('feDropShadow', { dx: -3, dy: -3, stdDeviation: 4, 'flood-color': '#2a2a3a', 'flood-opacity': 0.55 }, neu);

  for (const p of pipes) {
    el('path', { d: p.d, class: 'pipe' }, svg);
    if (p.flow) el('path', { d: p.d, class: 'pipe-flow', 'data-flow': '' }, svg);
    else el('path', { d: p.d, class: 'pipe-drain', 'data-drain': '' }, svg);
  }
  for (const d of signals) el('path', { d, class: 'signal' }, svg);

  for (const [tag, s] of Object.entries(equipment)) {
    const g = el('g', { class: 'eq', 'data-tag': tag, tabindex: 0, role: 'button' }, svg);
    drawSymbol(g, tag, s);
    if (s.label) {
      const [lx, ly] = s.label;
      const anchor = s.anchor || 'middle';
      text(g, lx, ly, tag, 'tag', anchor);
      text(g, lx, ly + 15, equipmentLabels[tag] || '', 'sub', anchor);
    }
    const pick = () => onSelect(tag);
    g.addEventListener('click', pick);
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') pick(); });
  }

  for (const [tag, b] of Object.entries(instruments)) {
    const g = el('g', { class: 'inst', 'data-inst': tag }, svg);
    el('path', { d: `M${b.cx} ${b.cy + (b.to[1] > b.cy ? 17 : -17)} L${b.to[0]} ${b.to[1]}`, class: 'signal' }, g);
    el('circle', { cx: b.cx, cy: b.cy, r: 17, class: 'bubble' }, g);
    el('path', { d: `M${b.cx - 17} ${b.cy} H${b.cx + 17}`, class: 'bubble-div' }, g);
    const [fn, loop] = tag.split('-');
    text(g, b.cx, b.cy - 4, fn, 'bubble-fn');
    text(g, b.cx, b.cy + 12, loop, 'bubble-loop');
    text(g, b.cx + 24, b.cy + 5, '—', 'inst-value', 'start').dataset.value = '';
    text(g, b.cx + 24, b.cy + 19, b.unit, 'inst-unit', 'start');
  }
}
