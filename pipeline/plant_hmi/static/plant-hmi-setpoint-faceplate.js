// Setpoint faceplate orchestration (phase 5): polls the setpoint list + audit log every
// 5 s (visiblePolling) and keeps one persistent row controller per key (plant-hmi-setpoint-
// row.js) so a poll refresh never rebuilds a card's DOM — see that module for why (rule H2).
import { visiblePolling } from './plant-hmi-visible-polling.js';
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';
import { fetchSetpoints, fetchAudit } from './plant-hmi-setpoint-api.js';
import { createSetpointRow } from './plant-hmi-setpoint-row.js';

export function initSetpointFaceplate(root) {
  const rowsEl = h('div', { class: 'sp-rows' });
  const auditEl = h('div', { class: 'sp-audit' });
  const status = h('div', { class: 'muted sp-status' }, 'đang tải…');
  root.replaceChildren(rowsEl, auditEl, status);

  const controllers = new Map();   // key -> { card, update } (never rebuilt while it exists)

  async function refreshAll() {
    await refresh();
    await refreshAudit();
  }

  async function refresh() {
    try {
      const rows = await fetchSetpoints();
      const seen = new Set();
      for (const row of rows) {
        seen.add(row.key);
        let ctrl = controllers.get(row.key);
        if (!ctrl) {
          ctrl = createSetpointRow(row.key, refreshAll);
          controllers.set(row.key, ctrl);
          rowsEl.append(ctrl.card);
        }
        ctrl.update(row);
      }
      for (const [key, ctrl] of controllers) {
        if (!seen.has(key)) { ctrl.card.remove(); controllers.delete(key); }
      }
      status.textContent = '';
    } catch (e) {
      status.textContent = `không đọc được setpoint: ${e.message}`;
    }
  }

  async function refreshAudit() {
    try {
      const rows = await fetchAudit(10);
      auditEl.replaceChildren(
        h('div', { class: 'sp-audit-title' }, 'audit'),
        ...rows.map((r) => h('div', { class: 'sp-audit-row' },
          `${fmtTime(r.ts)} ${r.who || '—'} ${r.key}: ${r.old ?? '—'} → ${r.new ?? 'RECIPE'}` +
          (r.reason ? ` "${r.reason}"` : ''))));
    } catch { /* audit is supplementary: leave the previous list on screen */ }
  }

  visiblePolling(async (isEnabled) => {
    await refresh();
    if (isEnabled()) await refreshAudit();
  }, 5000);

  return { refresh: refreshAll };
}
