// P-601 (ComfyUI) black-box progress panel: node, step bar, it/s, elapsed time.
// Self-polling (visiblePolling, 1s) so any page that mounts a container gets a
// live view without the host page wiring a poll loop itself.
import { visiblePolling } from './plant-hmi-visible-polling.js';
import { h, fmt, duration } from './plant-hmi-render-panels.js';

const POLL_MS = 1000;
const ENDPOINT = '/plant-hmi/api/comfyui/progress';
const IDLE = { connected: false, phase: 'idle' };

function bar(step, steps) {
  const pct = step === null || steps === null || steps === undefined || !steps
    ? 0 : Math.max(0, Math.min(1, step / steps)) * 100;
  return h('div', { class: 'comfy-bar' }, h('i', { style: `width:${pct}%` }));
}

function renderExecuting(container, data) {
  container.append(
    h('div', { class: 'comfy-node' },
      h('span', { class: 'comfy-node-title' }, data.node_title || data.node || '—'),
      h('span', { class: 'comfy-node-id' }, data.node ? `node ${data.node}` : '—')),
    // step_seen: this node never emitted a step tick yet (loader/one-shot node,
    // e.g. checkpoint load) — never fake a percentage, say so plainly instead
    data.step_seen
      ? [bar(data.step, data.steps),
        h('div', { class: 'comfy-line' },
          h('span', {}, `${fmt(data.step)} / ${fmt(data.steps)} bước`),
          h('span', {}, data.it_s === null || data.it_s === undefined ? '— it/s' : `${fmt(data.it_s, 2)} it/s`))]
      : h('div', { class: 'comfy-line muted' }, 'chưa có bước đo (đang tải/ chạy node một lần)'),
    h('div', { class: 'comfy-line muted' },
      h('span', {}, `đã chạy ${duration(data.elapsed_s)}`),
      // L9: prompt_id can arrive malformed from a future ComfyUI build; never throw on .slice
      h('span', {}, data.prompt_id ? `prompt ${String(data.prompt_id).slice(0, 8)}` : '—')),
  );
}

function render(container, data) {
  container.replaceChildren();
  const connLabel = data.connected ? 'đang lắng nghe' : 'mất kết nối tới ComfyUI';
  container.append(h('div', { class: `comfy-conn ${data.connected ? 'ok' : 'down'}` }, connLabel));

  if (!data.connected) {
    container.append(h('div', { class: 'comfy-empty' }, 'Không quan sát được (kiểm tra ComfyUI 127.0.0.1:8188)'));
    return;
  }

  if (data.phase === 'executing') {
    renderExecuting(container, data);
  } else if (data.phase === 'busy_foreign') {
    container.append(h('div', { class: 'comfy-empty' },
      'ComfyUI đang bận với tác vụ khác (không phải batch pipeline) — không quan sát được'));
  } else {
    container.append(h('div', { class: 'comfy-empty' }, 'Nghỉ, chưa có prompt nào đang chạy'));
  }

  container.append(h('div', { class: 'comfy-stats' },
    h('span', {}, `prompt gần nhất: ${data.last_prompt_s === null || data.last_prompt_s === undefined
      ? '—' : `${fmt(data.last_prompt_s, 1)} s`}`),
    h('span', {}, `prompt / giờ: ${fmt(data.prompts_1h)}`)));
}

export function initComfyProgressPanel(container) {
  async function poll() {
    let data;
    try {
      const res = await fetch(ENDPOINT, { cache: 'no-store' });
      data = res.ok ? await res.json() : IDLE;
    } catch {
      data = IDLE;
    }
    render(container, data || IDLE);
  }
  return visiblePolling(poll, POLL_MS);
}
