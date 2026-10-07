// The "Tạo mẻ mới" (new batch) form: base config, slug name, total images, one
// weight row per defect (plant-hmi-batch-compose-row.js) with a live largest-
// remainder preview of the per-class count, backgrounds dir, reason, and a
// two-step confirm for "Lưu config" / "Lưu & chạy" (same armed/pending pattern
// as the start/stop controls, rule H2: a poll never rebuilds a half-typed form).
import { h } from './plant-hmi-setpoint-dom.js';
import { fetchComposeOptions, composeBatch } from './plant-hmi-batch-compose-api.js';
import { startBatch } from './plant-hmi-batch-control-api.js';
import { createComposeRow } from './plant-hmi-batch-compose-row.js';

// Mirrors plant_hmi/plant_batch_allocate.py:allocate_counts exactly: a live
// preview only, the server always recomputes and writes the authoritative
// (nudged) ratios on save.
function largestRemainderPreview(total, weights) {
  const counts = {};
  for (const d of Object.keys(weights)) counts[d] = 0;
  const positive = Object.entries(weights).filter(([, w]) => w > 0);
  if (!positive.length || !total) return counts;
  const wsum = positive.reduce((s, [, w]) => s + w, 0);
  const floors = positive.map(([d, w]) => {
    const raw = (total * w) / wsum;
    return [d, Math.floor(raw), raw - Math.floor(raw)];
  });
  let remainder = total - floors.reduce((s, [, f]) => s + f, 0);
  const order = [...floors].sort((a, b) => b[2] - a[2] || a[0].localeCompare(b[0]));
  for (const [d, f] of floors) counts[d] = f;
  for (let i = 0; i < remainder && i < order.length; i++) counts[order[i][0]] += 1;
  return counts;
}

export function createComposeForm(onComposed) {
  let options = null;
  let rows = new Map(); // defect -> row controller
  let weights = {};
  let baseConfig = null;
  let name = '';
  let totalImages = 1000;
  let backgroundsDir = '';
  let reason = '';
  let mode = 'idle'; // idle | armed-save | armed-run | pending

  const baseSelect = h('select', { class: 'bc-select' });
  const nameInput = h('input', {
    type: 'text', class: 'bcp-input', placeholder: 'ten-config-slug', maxlength: '60',
    oninput: (e) => { name = e.target.value; },
  });
  const totalInput = h('input', {
    type: 'number', class: 'bcp-input', min: '1', max: '20000', value: String(totalImages),
    oninput: (e) => { totalImages = parseInt(e.target.value, 10) || 0; recomputeCounts(); },
  });
  const bgInput = h('input', {
    type: 'text', class: 'bcp-input bcp-input-wide', placeholder: '/duong/dan/backgrounds',
    oninput: (e) => { backgroundsDir = e.target.value; },
  });
  const reasonInput = h('input', {
    type: 'text', class: 'bcp-input bcp-input-wide', maxlength: '200', placeholder: 'lý do tạo mẻ…',
    oninput: (e) => { reason = e.target.value; },
  });
  const rowsEl = h('div', { class: 'bcp-rows' });
  const errorEl = h('div', { class: 'bc-error', style: 'display:none' });
  const statusEl = h('div', { class: 'muted bc-status' });
  const controlsEl = h('div', { class: 'bc-controls' });

  const card = h('div', { class: 'bcp-card', style: 'display:none' },
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'base config'), baseSelect),
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'tên (slug)'), nameInput),
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'total images'), totalInput),
    rowsEl,
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'backgrounds dir'), bgInput),
    h('div', { class: 'bc-row' }, h('label', { class: 'bc-label' }, 'lý do'), reasonInput),
    controlsEl, errorEl, statusEl);

  const showError = (msg) => { errorEl.textContent = msg; errorEl.style.display = ''; };
  const hideError = () => { errorEl.style.display = 'none'; };

  function recomputeCounts() {
    const counts = largestRemainderPreview(totalImages, weights);
    for (const [defect, ctrl] of rows) ctrl.setCount(counts[defect] || 0);
  }

  function onWeightChange(defect, weight) {
    weights[defect] = weight;
    recomputeCounts();
  }

  function rebuildRows() {
    rowsEl.replaceChildren();
    rows = new Map();
    weights = {};
    if (!options) return;
    for (const defect of options.defects) {
      const ctrl = createComposeRow(defect, onWeightChange);
      rows.set(defect.defect, ctrl);
      weights[defect.defect] = ctrl.getWeight();
      rowsEl.append(ctrl.row);
    }
    recomputeCounts();
  }

  async function loadOptions() {
    if (!baseConfig) return;
    statusEl.textContent = 'đang tải danh sách defect…';
    try {
      options = await fetchComposeOptions(baseConfig);
      if (options.default_total_images) {
        totalImages = options.default_total_images;
        totalInput.value = String(totalImages);
      }
      if (!backgroundsDir && options.default_backgrounds_dir) {
        backgroundsDir = options.default_backgrounds_dir;
        bgInput.value = backgroundsDir;
      }
      rebuildRows();
      statusEl.textContent = '';
    } catch (e) {
      statusEl.textContent = `không tải được defect: ${e.message}`;
    }
  }

  baseSelect.addEventListener('change', (e) => { baseConfig = e.target.value; loadOptions(); });

  function renderIdleControls() {
    const saveBtn = h('button', {
      class: 'bc-btn bc-btn-start', type: 'button',
      onclick: () => { mode = 'armed-save'; hideError(); renderControls(); },
    }, 'Lưu config');
    const runBtn = h('button', {
      class: 'bc-btn bc-btn-start', type: 'button',
      onclick: () => { mode = 'armed-run'; hideError(); renderControls(); },
    }, 'Lưu & chạy');
    controlsEl.replaceChildren(saveBtn, runBtn);
  }

  function renderConfirm(andRun) {
    const confirmBtn = h('button', {
      class: 'bc-btn bc-btn-confirm', type: 'button',
      onclick: () => runCompose(andRun, confirmBtn, cancelBtn),
    }, 'Xác nhận');
    const cancelBtn = h('button', {
      class: 'bc-btn bc-btn-cancel', type: 'button',
      onclick: () => { mode = 'idle'; renderControls(); },
    }, 'Huỷ');
    controlsEl.replaceChildren(
      h('span', { class: 'bc-confirm-text' },
        `→ Xác nhận tạo config "${name}" (${totalImages} ảnh)${andRun ? ' và chạy ngay' : ''} ?`),
      confirmBtn, cancelBtn);
  }

  function renderControls() {
    if (mode === 'idle') renderIdleControls();
    else if (mode === 'armed-save') renderConfirm(false);
    else if (mode === 'armed-run') renderConfirm(true);
  }

  async function runCompose(andRun, confirmBtn, cancelBtn) {
    if (mode === 'pending') return; // H2: guard a double click racing the network
    mode = 'pending';
    confirmBtn.setAttribute('disabled', '');
    cancelBtn.setAttribute('disabled', '');
    try {
      const result = await composeBatch({
        name, base_config: baseConfig, total_images: totalImages, distribution: weights,
        backgrounds_dir: backgroundsDir || null, reason, overwrite: false,
      });
      if (andRun) await startBatch(result.config_name, false, false, reason);
      mode = 'idle';
      renderControls();
      await onComposed(result.config_name);
    } catch (e) {
      mode = 'idle';
      renderControls();
      showError(e.message);
    }
  }

  renderIdleControls();

  return {
    card,
    setConfigs(configs) {
      const names = configs.map((c) => c.name);
      if (baseConfig && !names.includes(baseConfig)) baseConfig = null;
      if (!baseConfig && names.length) baseConfig = names[0];
      baseSelect.replaceChildren(...names.map((n) => h('option', {
        value: n, selected: n === baseConfig ? '' : null,
      }, n)));
      if (baseConfig && !options) loadOptions();
    },
    show() { card.style.display = ''; if (!options) loadOptions(); },
    hide() { card.style.display = 'none'; },
    isVisible() { return card.style.display !== 'none'; },
  };
}
