// Batch start/stop control panel (phase 6A): polls GET /api/control/batch (and the
// audit log) every 5 s while visible, keeps one persistent start-controls card and one
// persistent stop-row controller per live pid (plant-hmi-batch-control-panel.js) so a
// poll refresh never rebuilds an <input>/<select> mid-edit (rule H2, same pattern as
// the setpoint faceplate).
import { visiblePolling } from './plant-hmi-visible-polling.js';
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';
import { fetchBatchState, fetchBatchAudit } from './plant-hmi-batch-control-api.js';
import { createStartControls, createLiveRow } from './plant-hmi-batch-control-panel.js';
import { createComposeForm } from './plant-hmi-batch-compose-panel.js';

export function initBatchControl(root) {
  const liveEl = h('div', { class: 'bc-live-rows' });
  const auditEl = h('div', { class: 'bc-audit' });
  const status = h('div', { class: 'muted bc-status' }, 'đang tải…');

  const startControls = createStartControls((configName) => refreshState(configName));
  const composeForm = createComposeForm((configName) => onComposed(configName));
  const composeToggle = h('button', {
    class: 'bc-btn bc-btn-compose-toggle', type: 'button',
    onclick: () => {
      if (composeForm.isVisible()) { composeForm.hide(); composeToggle.textContent = '＋ Tạo mẻ mới'; }
      else { composeForm.show(); composeToggle.textContent = '－ Đóng form tạo mẻ'; }
    },
  }, '＋ Tạo mẻ mới');
  root.replaceChildren(startControls.card, composeToggle, composeForm.card, liveEl, auditEl, status);

  const liveControllers = new Map(); // pid -> { card, update }

  // After a successful compose (phase 6B): refresh so the new config is in the
  // list, then force-select it in the start dropdown (`update()` alone would
  // keep the operator's previous selection, rule H2).
  async function onComposed(configName) {
    await refreshState(configName);
    startControls.forceSelectConfig(configName);
  }

  async function refreshState(configName) {
    try {
      const state = await fetchBatchState(configName ?? startControls.getSelectedConfig());
      startControls.update(state);
      composeForm.setConfigs(state.configs);

      const seen = new Set();
      for (const row of state.live) {
        seen.add(row.pid);
        let ctrl = liveControllers.get(row.pid);
        if (!ctrl) {
          ctrl = createLiveRow(row.pid, () => refreshAll());
          liveControllers.set(row.pid, ctrl);
          liveEl.append(ctrl.card);
        }
        ctrl.update(row);
      }
      for (const [pid, ctrl] of liveControllers) {
        if (!seen.has(pid)) { ctrl.card.remove(); liveControllers.delete(pid); }
      }
      status.textContent = '';
    } catch (e) {
      status.textContent = `không đọc được trạng thái batch: ${e.message}`;
    }
  }

  async function refreshAudit() {
    try {
      const rows = await fetchBatchAudit(10);
      auditEl.replaceChildren(
        h('div', { class: 'bc-audit-title' }, 'audit start/stop gần nhất'),
        ...rows.map((r) => h('div', { class: `bc-audit-row ${r.accepted ? '' : 'bc-audit-refused'}` },
          `${fmtTime(r.ts)} ${r.who || '—'} ${r.action} ${r.accepted ? 'OK' : 'TỪ CHỐI'}` +
          (r.unit ? ` [${r.unit}]` : '') + (r.pid ? ` pid ${r.pid}` : '') +
          (r.reason ? ` "${r.reason}"` : '') + (r.error ? ` — ${r.error}` : ''))));
    } catch { /* audit is supplementary: leave the previous list on screen */ }
  }

  async function refreshAll() {
    await refreshState();
    await refreshAudit();
  }

  visiblePolling(async (isEnabled) => {
    await refreshState();
    if (isEnabled()) await refreshAudit();
  }, 5000);

  return { refresh: refreshAll };
}
