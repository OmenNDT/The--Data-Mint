// Applies one snapshot to the static P&ID: states, alarm colours, levels, bubbles.
import { GEOMETRY } from './plant-hmi-pid-diagram.js';

const SEVERITY_RANK = { HI: 2, LO: 1 };
const fmt = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('vi-VN'));

function worstAlarmByTag(alarms) {
  const out = {};
  for (const a of alarms || []) {
    if ((SEVERITY_RANK[a.severity] || 0) > (SEVERITY_RANK[out[a.tag]] || 0)) out[a.tag] = a.severity;
  }
  return out;
}

function comfyState(c) {
  if (c.ok === true) return ['running', 'ComfyUI · sẵn sàng'];
  if (c.ok === false) return ['down', (c.procs || []).length ? 'ComfyUI · không trả lời' : 'ComfyUI · chưa chạy'];
  return ['idle', 'ComfyUI · chưa rõ'];
}

function gpuState(g, lease) {
  const held = lease ? ` · giữ: ${lease.owner}` : '';
  if (g.ok !== true) return ['idle', `GPU · chưa rõ${held}`];
  return [g.util_pct > 5 ? 'running' : 'idle', `GPU ${fmt(g.temp_c)}°C · ${fmt(g.util_pct)}%${held}`];
}

// Apply one snapshot to the static diagram: states, alarm colours, levels, bubbles.
export function updateDiagram(svg, snap) {
  const worst = worstAlarmByTag(snap.alarms);
  const running = (snap.batches || []).length > 0;
  svg.classList.toggle('flowing', running);

  for (const g of svg.querySelectorAll('.eq')) {
    const tag = g.dataset.tag;
    const eq = snap.equipment[tag] || {};
    let state = eq.state || 'idle';
    if (tag === 'U-902' || tag === 'U-901') {
      const [s, sub] = tag === 'U-902' ? comfyState(snap.utilities.comfy || {})
        : gpuState(snap.utilities.gpu || {}, snap.gpu_lease);
      state = s;
      g.querySelector('[data-value]').textContent = sub;
    }
    g.dataset.state = state;
    g.dataset.alarm = worst[tag] || '';
    g.setAttribute('aria-label', `${tag} ${eq.label || ''}, ${fmt(eq.level)} ${eq.unit || ''}, ` +
      `${worst[tag] ? 'báo động ' + worst[tag] : state}`);

    const value = g.querySelector('text[data-value]');
    if (value && !tag.startsWith('U-')) value.textContent = fmt(eq.level);
    const fill = g.querySelector('[data-fill]');
    if (fill) {
      const s = GEOMETRY.equipment[tag];
      const bottom = s.kind === 'silo' ? s.y + s.h + 30 : s.y + s.h;
      const full = bottom - s.y;
      const ratio = eq.max && eq.level !== null && eq.level !== undefined
        ? Math.max(0, Math.min(1, eq.level / eq.max)) : 0;
      fill.setAttribute('y', bottom - full * ratio);
      fill.setAttribute('height', full * ratio);
    }
  }

  const failed = (snap.equipment['D-901'] || {}).level;
  svg.classList.toggle('draining', running && failed > 0);

  for (const g of svg.querySelectorAll('.inst')) {
    const v = snap.instruments[g.dataset.inst];
    g.querySelector('[data-value]').textContent = g.dataset.inst.startsWith('KI') && v !== null && v !== undefined
      ? Number(v).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) : fmt(v);
  }
}
