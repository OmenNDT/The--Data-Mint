// One setpoint faceplate card (phase 5, DCS style). Owns its DOM node once and its own
// draft/mode state in closures; `update(row)` (called on every poll AND after a local
// stepper click) only ever mutates existing elements (textContent/attributes) — it never
// calls `controlsEl.replaceChildren(...)`. That div is only rebuilt from the two explicit
// user actions (Arm / Về công thức / Huỷ), so a background poll or a keystroke in the
// reason box never tears down the <input> (rule H2): caret position and Vietnamese IME
// composition survive untouched. The SP box always reads `row.sp` (rule L1): the
// stepper's unsaved value only ever appears in its own small draft readout, never in `sp`.
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';
import { putSetpoint, clearSetpoint } from './plant-hmi-setpoint-api.js';

const SOURCE_LABEL = { LOCAL: 'LOCAL (env)', REMOTE: 'REMOTE (setpoint)', RECIPE: 'RECIPE (mặc định)' };

export function createSetpointRow(key, onChanged) {
  let row = null;
  let draftValue = null;   // null = no unsaved stepper change; SP box never reads this
  let reason = '';
  let mode = 'idle';       // idle | armed-set | armed-clear

  const titleEl = h('div', { class: 'sp-title' });
  const spVal = h('span', { class: 'sp-box-val' });
  const pvVal = h('span', { class: 'sp-box-val' });
  const badge = h('span', { class: 'sp-badge' });
  const warnEl = h('div', { class: 'sp-warn', style: 'display:none' });
  const limitsEl = h('div', { class: 'sp-limits' });
  const controlsEl = h('div', { class: 'sp-controls' });
  const errorEl = h('div', { class: 'sp-error', style: 'display:none' });
  const card = h('div', { class: 'sp-card' }, titleEl,
    h('div', { class: 'sp-values' },
      h('div', { class: 'sp-box' }, h('span', { class: 'sp-box-label' }, 'SP'), spVal),
      h('div', { class: 'sp-box sp-box-pv' }, h('span', { class: 'sp-box-label' }, 'PV'), pvVal),
      badge),
    warnEl, limitsEl, controlsEl, errorEl);

  const currentValue = () => (draftValue === null ? row.sp : draftValue);
  const showError = (msg) => { errorEl.textContent = msg; errorEl.style.display = ''; };

  function step(delta) {
    const next = Math.min(row.max, Math.max(row.min, currentValue() + delta));
    draftValue = next === row.sp ? null : next;
    // in-place update only: preserves focus/caret in the reason input (rule H2)
    if (controlsEl._draftSpan) controlsEl._draftSpan.textContent = String(currentValue());
    if (controlsEl._armBtn) {
      if (currentValue() === row.sp) controlsEl._armBtn.setAttribute('disabled', '');
      else controlsEl._armBtn.removeAttribute('disabled');
    }
  }

  function renderIdleControls() {
    const minus = h('button', { class: 'sp-btn', type: 'button', onclick: () => step(-1) }, '−');
    const draftSpan = h('span', { class: 'sp-draft-val' }, String(currentValue()));
    const plus = h('button', { class: 'sp-btn', type: 'button', onclick: () => step(1) }, '+');
    const reasonInput = h('input', {
      class: 'sp-reason', type: 'text', maxlength: '200', placeholder: 'lý do thay đổi…', value: reason,
      oninput: (e) => { reason = e.target.value; },   // L1: never touches draftValue/SP
    });
    const armBtn = h('button', {
      class: 'sp-btn sp-btn-arm', type: 'button', disabled: currentValue() === row.sp ? '' : null,
      onclick: () => { if (currentValue() !== row.sp) { mode = 'armed-set'; errorEl.style.display = 'none'; renderControls(); } },
    }, 'Arm');
    const clearBtn = h('button', {
      class: 'sp-btn sp-btn-clear', type: 'button', disabled: row.updated_at == null ? '' : null,
      onclick: () => { mode = 'armed-clear'; errorEl.style.display = 'none'; renderControls(); },
    }, 'Về công thức (RECIPE)');
    controlsEl.replaceChildren(minus, draftSpan, plus, reasonInput, armBtn, clearBtn);
    controlsEl._draftSpan = draftSpan;
    controlsEl._armBtn = armBtn;
    controlsEl._clearBtn = clearBtn;
  }

  function renderConfirm(targetText, onConfirm) {
    controlsEl.replaceChildren(
      h('span', {}, targetText),
      h('button', { class: 'sp-btn sp-btn-confirm', type: 'button', onclick: onConfirm }, 'Xác nhận'),
      h('button', {
        class: 'sp-btn sp-btn-cancel', type: 'button',
        onclick: () => { mode = 'idle'; renderControls(); },
      }, 'Huỷ'));
    delete controlsEl._draftSpan;
    delete controlsEl._armBtn;
  }

  async function runAction(action) {
    try {
      await action();
      draftValue = null; reason = ''; mode = 'idle';
      renderControls();
      await onChanged();
    } catch (e) {
      mode = 'idle';
      renderControls();
      showError(e.message);
    }
  }

  function renderControls() {
    if (mode === 'idle') { renderIdleControls(); return; }
    if (mode === 'armed-set') {
      renderConfirm(`→ Xác nhận ${row.sp} → ${currentValue()} ?`,
        () => runAction(() => putSetpoint(key, currentValue(), reason)));
      return;
    }
    renderConfirm(`→ Xác nhận xoá setpoint, quay về RECIPE (${row.recipe ?? '—'}) ?`,
      () => runAction(() => clearSetpoint(key, reason)));
  }

  function update(newRow) {
    row = newRow;
    titleEl.textContent = `${row.key} · ${row.label}`;
    spVal.textContent = String(row.sp);   // L1: SP box always mirrors the server, never a draft
    pvVal.textContent = row.pv === null || row.pv === undefined ? '—' : String(row.pv);
    badge.className = `sp-badge${row.pv_source ? ` sp-badge-${row.pv_source.toLowerCase()}` : ''}`;
    badge.textContent = row.pv_source ? (SOURCE_LABEL[row.pv_source] || row.pv_source) : 'không rõ';
    const warn = row.pv !== null && row.pv !== undefined && row.sp !== row.pv;
    warnEl.style.display = warn ? '' : 'none';
    if (warn) {
      warnEl.textContent = `⚠ SP ≠ PV: batch đang chạy giữ giá trị cũ, ` +
        `${row.applies === 'next_batch' ? 'áp dụng từ batch sau' : 'chưa áp dụng'}`;
    }
    limitsEl.textContent = `giới hạn ${row.min}..${row.max} ${row.unit} · công thức ${row.recipe ?? '—'} · ` +
      `lần đổi cuối: ${row.updated_by ? `${row.updated_by} ${fmtTime(row.updated_at)}` : 'chưa có'}`;
    if (mode !== 'idle') return;   // confirm view is static text, left alone until resolved (H2)
    if (!controlsEl._draftSpan) { renderIdleControls(); return; }
    controlsEl._draftSpan.textContent = String(currentValue());
    if (currentValue() === row.sp) controlsEl._armBtn.setAttribute('disabled', '');
    else controlsEl._armBtn.removeAttribute('disabled');
    if (row.updated_at == null) controlsEl._clearBtn.setAttribute('disabled', '');
    else controlsEl._clearBtn.removeAttribute('disabled');
  }

  return { card, update };
}
