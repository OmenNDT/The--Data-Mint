// Persistent DOM controllers for the batch control panel (phase 6A): start controls
// (config picker + pilot/resume + permissives + two-step Start) and one stop row per
// live batch. Mirrors the setpoint faceplate pattern (plant-hmi-setpoint-row.js): every
// `update(...)` call only mutates existing nodes, never replaces the <select>/<input>,
// so a background poll never drops focus or a half-typed reason (rule H2).
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';
import { startBatch, stopBatch } from './plant-hmi-batch-control-api.js';

function permissiveRow(p) {
  const cls = p.ok ? 'bc-perm-ok' : (p.blocking ? 'bc-perm-blocked' : 'bc-perm-warn');
  const mark = p.ok ? '✓' : (p.blocking ? '✗' : '⚠');
  return h('div', { class: `bc-perm ${cls}` },
    h('span', { class: 'bc-perm-mark' }, mark),
    h('span', { class: 'bc-perm-code' }, p.code),
    h('span', { class: 'bc-perm-msg' }, p.message));
}

export function createStartControls(onChanged) {
  let state = { configs: [], permissives: [], live: [], checkpoint: null };
  let selectedConfig = null;
  let resumeDefaultAppliedFor = null; // M6: apply the checkpoint-present default once per config
  let pilot = false;
  let resume = false;
  let reason = '';
  let mode = 'idle'; // idle | armed | pending

  const selectEl = h('select', { class: 'bc-select' });
  const permsEl = h('div', { class: 'bc-perms' });
  const controlsEl = h('div', { class: 'bc-controls' });
  const errorEl = h('div', { class: 'bc-error', style: 'display:none' });
  const silosEl = h('div', { class: 'bc-silo-warn', style: 'display:none' });
  const ckptEl = h('div', { class: 'bc-ckpt-note', style: 'display:none' });
  const card = h('div', { class: 'bc-start-card' },
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'config'), selectEl),
    silosEl, ckptEl, permsEl, controlsEl, errorEl);

  const showError = (msg) => { errorEl.textContent = msg; errorEl.style.display = ''; };
  const hideError = () => { errorEl.style.display = 'none'; };
  const blockers = () => state.permissives.filter((p) => p.blocking && !p.ok);

  function renderIdleControls() {
    const pilotBox = h('input', {
      type: 'checkbox', checked: pilot ? '' : null,
      onchange: (e) => { pilot = e.target.checked; },
    });
    const resumeBox = h('input', {
      type: 'checkbox', checked: resume ? '' : null,
      onchange: (e) => { resume = e.target.checked; },
    });
    const reasonInput = h('input', {
      class: 'bc-reason', type: 'text', maxlength: '200', placeholder: 'lý do khởi chạy…', value: reason,
      oninput: (e) => { reason = e.target.value; },
    });
    const startBtn = h('button', {
      class: 'bc-btn bc-btn-start', type: 'button',
      disabled: blockers().length ? '' : null,
      onclick: () => { if (!blockers().length) { mode = 'armed'; hideError(); renderControls(); } },
    }, 'Start');
    controlsEl.replaceChildren(
      h('label', { class: 'bc-check' }, pilotBox, ' pilot (5 ảnh)'),
      h('label', { class: 'bc-check' }, resumeBox, ' resume từ checkpoint'),
      reasonInput, startBtn);
    controlsEl._reasonInput = reasonInput;
    controlsEl._startBtn = startBtn;
  }

  function renderConfirm() {
    const warn = blockers().length === 0 && state.permissives.some((p) => p.code === 'MAIN_SILO' && !p.ok);
    // M6: an honest warning when a checkpoint exists but the operator leaves resume off —
    // the batch script backs it up and starts fresh into the same output dir (non-interactive).
    const freshOverCheckpoint = !!state.checkpoint && !resume;
    const confirmBtn = h('button', {
      class: 'bc-btn bc-btn-confirm', type: 'button',
      onclick: () => runStart(confirmBtn, cancelBtn),
    }, 'Xác nhận');
    const cancelBtn = h('button', {
      class: 'bc-btn bc-btn-cancel', type: 'button',
      onclick: () => { mode = 'idle'; renderControls(); },
    }, 'Huỷ');
    controlsEl.replaceChildren(
      h('span', { class: 'bc-confirm-text' },
        `→ Xác nhận khởi chạy "${selectedConfig}"${pilot ? ' (pilot)' : ''}` +
        (warn ? ' — CẢNH BÁO: ghi vào silo chính (output/synthetic)' : '') +
        (freshOverCheckpoint ? ' — sẽ sao lưu checkpoint và chạy lại từ đầu' : '') + ' ?'),
      confirmBtn, cancelBtn);
  }

  async function runStart(confirmBtn, cancelBtn) {
    if (mode === 'pending') return; // H2: guard against a double click racing the network
    mode = 'pending';
    confirmBtn.setAttribute('disabled', '');
    cancelBtn.setAttribute('disabled', '');
    try {
      await startBatch(selectedConfig, pilot, resume, reason);
      reason = ''; mode = 'idle';
      renderControls();
      await onChanged();
    } catch (e) {
      mode = 'idle';
      renderControls();
      showError(e.message);
    }
  }

  function renderControls() {
    if (mode === 'idle') renderIdleControls();
    else if (mode === 'armed') renderConfirm();
    // 'pending': leave the disabled confirm/cancel buttons as they are until settled
  }

  function rebuildSelect() {
    selectEl.replaceChildren(...state.configs.map((c) => h('option', {
      value: c.name, selected: c.name === selectedConfig ? '' : null,
    }, c.name)));
  }

  selectEl.addEventListener('change', (e) => {
    selectedConfig = e.target.value;
    onChanged(selectedConfig);
  });

  function update(newState) {
    const prevNames = state.configs.map((c) => c.name).join('|');
    state = newState;
    const stillPresent = state.configs.some((c) => c.name === selectedConfig);
    if (!selectedConfig || !stillPresent) selectedConfig = state.selected_config_name || (state.configs[0] || {}).name || null;
    if (prevNames !== state.configs.map((c) => c.name).join('|') || selectEl.value !== selectedConfig) rebuildSelect();
    permsEl.replaceChildren(...state.permissives.map(permissiveRow));
    const mainSilo = state.permissives.find((p) => p.code === 'MAIN_SILO');
    silosEl.style.display = mainSilo && !mainSilo.ok ? '' : 'none';
    if (mainSilo && !mainSilo.ok) silosEl.textContent = `⚠ ${mainSilo.message}`;

    // M6: default resume ON the first time this config shows a resumable checkpoint;
    // never again override the operator's own toggle on a later poll of the same config.
    if (state.checkpoint && resumeDefaultAppliedFor !== selectedConfig) {
      resume = true;
      resumeDefaultAppliedFor = selectedConfig;
    }
    ckptEl.style.display = state.checkpoint ? '' : 'none';
    if (state.checkpoint) {
      ckptEl.textContent = `có checkpoint: ${state.checkpoint.current_index}/${state.checkpoint.total} ` +
        '— mặc định resume (bật) để tiếp tục';
    }

    if (mode !== 'idle') return; // confirm/pending view is static until resolved (H2)
    if (!controlsEl._startBtn) { renderIdleControls(); return; }
    if (blockers().length) controlsEl._startBtn.setAttribute('disabled', '');
    else controlsEl._startBtn.removeAttribute('disabled');
  }

  renderIdleControls();
  return {
    card, update, getSelectedConfig: () => selectedConfig,
    // Used after a successful "Tạo mẻ mới" compose (phase 6B): `update()` alone
    // keeps the operator's current selection (by design, rule H2), so picking
    // the just-created config needs an explicit override once its name is
    // already present in `state.configs` (the caller awaits a state refresh first).
    forceSelectConfig(name) {
      if (!state.configs.some((c) => c.name === name)) return;
      selectedConfig = name;
      rebuildSelect();
    },
  };
}

export function createLiveRow(pid, onChanged) {
  let row = { pid };
  let reason = '';
  let mode = 'idle'; // idle | armed | pending

  const titleEl = h('div', { class: 'bc-live-title' });
  const controlsEl = h('div', { class: 'bc-controls' });
  const errorEl = h('div', { class: 'bc-error', style: 'display:none' });
  const card = h('div', { class: 'bc-live-card' }, titleEl, controlsEl, errorEl);

  const showError = (msg) => { errorEl.textContent = msg; errorEl.style.display = ''; };

  function renderIdleControls() {
    const reasonInput = h('input', {
      class: 'bc-reason', type: 'text', maxlength: '200', placeholder: 'lý do dừng…', value: reason,
      oninput: (e) => { reason = e.target.value; },
    });
    const stopBtn = h('button', {
      class: 'bc-btn bc-btn-stop', type: 'button',
      onclick: () => { mode = 'armed'; errorEl.style.display = 'none'; renderControls(); },
    }, 'Stop');
    controlsEl.replaceChildren(reasonInput, stopBtn);
    controlsEl._reasonInput = reasonInput;
  }

  function renderConfirm() {
    const confirmBtn = h('button', {
      class: 'bc-btn bc-btn-confirm', type: 'button',
      onclick: () => runStop(confirmBtn, cancelBtn),
    }, 'Xác nhận');
    const cancelBtn = h('button', {
      class: 'bc-btn bc-btn-cancel', type: 'button',
      onclick: () => { mode = 'idle'; renderControls(); },
    }, 'Huỷ');
    controlsEl.replaceChildren(
      h('span', { class: 'bc-confirm-text' },
        `→ Xác nhận dừng pid ${row.pid}${row.unit ? ` (${row.unit})` : ''} ` +
        '(batch nhận SIGINT, lưu checkpoint rồi thoát; chạy lại với resume để tiếp tục) ?'),
      confirmBtn, cancelBtn);
  }

  async function runStop(confirmBtn, cancelBtn) {
    if (mode === 'pending') return; // H2: guard against a double click racing the network
    mode = 'pending';
    confirmBtn.setAttribute('disabled', '');
    cancelBtn.setAttribute('disabled', '');
    try {
      await stopBatch(row.pid, row.start_ts, reason);
      reason = ''; mode = 'idle';
      renderControls();
      await onChanged();
    } catch (e) {
      mode = 'idle';
      renderControls();
      showError(e.message);
    }
  }

  function renderControls() {
    if (mode === 'idle') renderIdleControls();
    else if (mode === 'armed') renderConfirm();
  }

  function update(newRow) {
    row = newRow;
    titleEl.textContent = `pid ${row.pid} · ${row.config_name || '(config không rõ)'} ` +
      `${row.pilot ? '· pilot' : ''} · ${row.unit || 'không có unit systemd'} · ` +
      `từ ${fmtTime(row.start_ts)}`;
    if (mode !== 'idle') return;
    if (!controlsEl._reasonInput) renderIdleControls();
  }

  renderIdleControls();
  return { card, update };
}
