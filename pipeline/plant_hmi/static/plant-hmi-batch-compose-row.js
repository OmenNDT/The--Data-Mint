// One per-defect row in the "Tạo mẻ mới" form: weight slider + number (kept in
// sync), live computed image count, LoRA/mask-generator status badge. Disabled
// (weight forced to 0) when either is missing, so an operator can never submit
// a defect the pipeline cannot actually render. Persistent DOM: `setCount()`
// only sets textContent, never replaces nodes (rule H2).
import { h } from './plant-hmi-setpoint-dom.js';

export function createComposeRow(defect, onWeightChange) {
  const usable = defect.lora_present && defect.mask_generator;
  const missingParts = [];
  if (!defect.lora_present) missingParts.push('LoRA');
  if (!defect.mask_generator) missingParts.push('mask generator');

  const slider = h('input', {
    type: 'range', min: '0', max: '1', step: '0.001', value: String(defect.default_weight),
    disabled: usable ? null : '',
    oninput: (e) => { number.value = e.target.value; onWeightChange(defect.defect, Number(e.target.value) || 0); },
  });
  const number = h('input', {
    type: 'number', class: 'bcp-weight', min: '0', max: '1', step: '0.001',
    value: String(defect.default_weight), disabled: usable ? null : '',
    oninput: (e) => { slider.value = e.target.value; onWeightChange(defect.defect, Number(e.target.value) || 0); },
  });
  const countEl = h('span', { class: 'bcp-count' }, '0 ảnh');
  const badge = h('span', {
    class: `bcp-badge ${usable ? 'bcp-badge-ok' : 'bcp-badge-missing'}`,
    'data-tip': usable ? 'có LoRA và mask generator' : `thiếu: ${missingParts.join(', ')}`,
  }, usable ? '✓' : '✗');

  const row = h('div', { class: `bcp-row ${usable ? '' : 'bcp-row-disabled'}` },
    h('span', { class: 'bcp-label' }, defect.label), badge, slider, number, countEl);

  return {
    row,
    defect: defect.defect,
    usable,
    setCount(count) { countEl.textContent = `${count} ảnh`; },
    getWeight() { return usable ? (Number(number.value) || 0) : 0; },
  };
}
