// Alarm list with ISA-18.2 ack/shelve actions (phase 6B), split out of
// `plant-hmi-render-panels.js` to keep that file under 200 lines. Rows are persistent (one
// DOM node per alarm key, cached in a module-level map keyed by the container element):
// `renderAlarmList(container, snap)` only rebuilds a row's controls when the row itself has
// no open form, so typing a shelve reason survives the 3 s snapshot poll (same pattern as
// `plant-hmi-setpoint-row.js`'s H2 rule). `h` is imported (not a local copy): a local `h`
// that used `setAttribute('onclick', fn)` silently stringified every handler into a dead
// inline attribute (rule C1) - `plant-hmi-setpoint-dom.js`'s `h` uses `addEventListener`.
import { h } from './plant-hmi-setpoint-dom.js';
import { ackAlarm, ackAllAlarms, shelveAlarm, unshelveAlarm } from './plant-hmi-alarm-api.js';

const SHELVE_CHOICES = [[15, '15 phút'], [60, '1 giờ'], [480, '8 giờ']];

const clockFmt = (ts) => (ts === null || ts === undefined ? '—'
  : new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour12: false }));
function durationFmt(s) {
  if (s === null || s === undefined) return '—';
  s = Math.max(0, Math.round(s));
  const mm = Math.floor(s / 60);
  return mm ? `${mm} phút` : `${s} s`;
}

// container -> { rows: Map(key -> row controller), shelvedBox: element }
const registry = new WeakMap();

// `key`: occurrence key (ack target). `pointKey`: alarm-point key (shelve target, rule H5) -
// only meaningful for kind 'active' (a cleared row only offers ack, per rule M4).
function createRow(key, kind, pointKey, onChanged) {
  let mode = 'idle'; // idle | shelve-pick | shelve-confirm
  let minutes = 15;
  let reason = '';
  const titleEl = h('span', { class: 'atag' });
  const msgEl = h('span', { class: 'amsg' });
  const timeEl = h('span', { class: 'atime' });
  const controls = h('div', { class: 'alarm-actions' });
  const errorEl = h('div', { class: 'alarm-error', style: 'display:none' });
  const sevEl = h('span', { class: 'sev' });
  const card = h('div', { class: `alarm alarm-${kind}` }, sevEl, titleEl, msgEl, timeEl, controls, errorEl);

  const showError = (msg) => { errorEl.textContent = msg; errorEl.style.display = ''; };

  async function run(action) {
    try {
      await action();
      mode = 'idle'; reason = ''; errorEl.style.display = 'none';
      await onChanged();
    } catch (e) {
      mode = 'idle';
      renderControls();
      showError(e.message);
    }
  }

  function renderControls() {
    if (kind === 'cleared') {
      controls.replaceChildren(h('button', {
        class: 'alarm-btn alarm-btn-ack', type: 'button', onclick: () => run(() => ackAlarm(key, '')),
      }, 'Xác nhận'));
      return;
    }
    if (mode === 'idle') {
      const ackBtn = h('button', {
        class: 'alarm-btn alarm-btn-ack', type: 'button', onclick: () => run(() => ackAlarm(key, '')),
      }, 'Xác nhận');
      const shelveBtn = h('button', {
        class: 'alarm-btn alarm-btn-shelve', type: 'button',
        onclick: () => { mode = 'shelve-pick'; renderControls(); },
      }, 'Tạm tắt');
      controls.replaceChildren(ackBtn, shelveBtn);
      return;
    }
    if (mode === 'shelve-pick') {
      const picks = SHELVE_CHOICES.map(([m, label]) => h('button', {
        class: `alarm-btn alarm-btn-dur${m === minutes ? ' active' : ''}`, type: 'button',
        onclick: () => { minutes = m; mode = 'shelve-pick'; renderControls(); },
      }, label));
      const reasonInput = h('input', {
        class: 'alarm-reason', type: 'text', maxlength: '200', placeholder: 'lý do tạm tắt (bắt buộc)…',
        value: reason, oninput: (e) => { reason = e.target.value; },
      });
      const next = h('button', {
        class: 'alarm-btn alarm-btn-confirm', type: 'button',
        onclick: () => {
          if (!reason.trim()) { showError('cần nhập lý do tạm tắt'); return; }
          mode = 'shelve-confirm'; errorEl.style.display = 'none'; renderControls();
        },
      }, 'Tiếp tục');
      const cancel = h('button', {
        class: 'alarm-btn alarm-btn-cancel', type: 'button',
        onclick: () => { mode = 'idle'; renderControls(); },
      }, 'Huỷ');
      controls.replaceChildren(h('div', { class: 'alarm-dur-row' }, ...picks), reasonInput, next, cancel);
      return;
    }
    // shelve-confirm
    const label = SHELVE_CHOICES.find(([m]) => m === minutes)[1];
    controls.replaceChildren(
      h('span', {}, `→ Tạm tắt ${label}: "${reason}" ?`),
      h('button', {
        class: 'alarm-btn alarm-btn-confirm', type: 'button',
        onclick: () => run(() => shelveAlarm(pointKey, minutes, reason)),
      }, 'Xác nhận'),
      h('button', {
        class: 'alarm-btn alarm-btn-cancel', type: 'button',
        onclick: () => { mode = 'shelve-pick'; renderControls(); },
      }, 'Huỷ'));
  }

  function update(a, nowTs) {
    sevEl.className = `sev ${a.severity || ''}`;
    sevEl.textContent = a.severity || '';
    titleEl.textContent = a.tag || '';
    msgEl.textContent = a.message || '';
    if (kind === 'cleared') {
      timeEl.textContent = `${a.code} · đã hết · chờ xác nhận`;
    } else {
      timeEl.textContent = `${a.code} · từ ${clockFmt(a.since)} (${durationFmt(nowTs - a.since)})`;
      card.classList.toggle('acked', !!a.acked);
      card.classList.toggle('unacked', !a.acked);
    }
    if (mode === 'idle' || !controls.hasChildNodes()) renderControls();
  }

  renderControls();
  return { card, kind, update, hasOpenForm: () => mode !== 'idle' };
}

function renderShelvedSummary(box, shelved, onChanged) {
  let open = box._shelvedOpen || false;
  const head = h('button', {
    class: 'alarm-shelved-head', type: 'button',
    onclick: () => { box._shelvedOpen = !open; renderShelvedSummary(box, shelved, onChanged); },
  }, `${shelved.length} báo động đang tạm tắt ${open ? '▲' : '▼'}`);
  const list = open ? shelved.map((s) => h('div', { class: 'alarm-shelved-row' },
    h('span', { class: 'atag' }, s.tag), h('span', { class: 'amsg' }, s.reason || ''),
    h('span', { class: 'atime' }, `${s.code} · hết hạn ${clockFmt(s.until)}`),
    h('button', {
      class: 'alarm-btn alarm-btn-cancel', type: 'button',
      onclick: async () => { await unshelveAlarm(s.key); await onChanged(); },
    }, 'Bỏ tạm tắt'))) : [];
  box.replaceChildren(head, ...list);
}

// Rule M4: a row whose kind no longer matches the list it now appears in (active alarm
// cleared, or - in principle - a cleared row became active again) is discarded and
// recreated fresh, instead of reusing a stale row stuck offering the wrong actions.
function rowFor(entry, key, kind, pointKey, refresh) {
  const existing = entry.rows.get(key);
  if (existing && existing.kind === kind) return existing;
  const row = createRow(key, kind, pointKey, refresh);
  entry.rows.set(key, row);
  return row;
}
export function renderAlarmList(container, snap, onChanged) {
  let entry = registry.get(container);
  if (!entry) {
    entry = { rows: new Map(), shelvedBox: h('div', { class: 'alarm-shelved-box' }) };
    registry.set(container, entry);
  }
  const alarms = snap.alarms || [];
  const cleared = snap.alarms_cleared_unacked || [];
  const shelved = snap.alarms_shelved || [];
  const refresh = onChanged || (() => {});

  const seen = new Set();
  const orderedCards = [];
  for (const a of alarms) {
    seen.add(a.key);
    const row = rowFor(entry, a.key, 'active', a.point_key, refresh);
    if (!row.hasOpenForm()) row.update(a, snap.ts);
    orderedCards.push(row.card);
  }
  for (const c of cleared) {
    seen.add(c.key);
    const row = rowFor(entry, c.key, 'cleared', null, refresh);
    row.update(c, snap.ts);
    orderedCards.push(row.card);
  }
  for (const key of [...entry.rows.keys()]) {
    if (!seen.has(key)) entry.rows.delete(key);  // acked-and-gone, or ack carried it away
  }

  const anyOpenForm = [...entry.rows.values()].some((r) => r.hasOpenForm());
  if (!container.contains(document.activeElement) || !anyOpenForm) {
    const children = [];
    if (!alarms.length && !cleared.length) children.push(h('div', { class: 'empty' }, 'Không có báo động'));
    else children.push(...orderedCards);
    if (alarms.length > 1) {
      children.unshift(h('button', {
        class: 'alarm-btn alarm-btn-ack-all', type: 'button',
        onclick: async () => { await ackAllAlarms(alarms.map((a) => a.key), ''); await refresh(); },
      }, 'Xác nhận tất cả'));
    }
    if (shelved.length) {
      renderShelvedSummary(entry.shelvedBox, shelved, refresh);
      children.push(entry.shelvedBox);
    }
    container.replaceChildren(...children);
  }
}
