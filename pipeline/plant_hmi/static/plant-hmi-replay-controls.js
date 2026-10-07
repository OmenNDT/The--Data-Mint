// Run picker + playback controls for historian replay: fetches /api/history/runs, loads a
// run's events once (cursor-paginated), then drives the replay clock, the particle layer and
// a diagram-render callback together. Gracefully reports "chưa có dữ liệu historian" while the
// backend historian endpoints are not deployed yet (404/500/network error).
//
// Only app.js calls plant-hmi-particle-layer's setMode() (H3): this module only ingests/resets
// particle data, it never switches Live<->Replay itself.
import { createReplayClock } from './plant-hmi-replay-clock.js';
import { createDeriver } from './plant-hmi-replay-derive.js';
import { ingest as ingestParticles, reset as resetParticles, renderAt as renderParticles }
  from './plant-hmi-particle-layer.js';

const SPEEDS = [1, 10, 60, 600];
const BASE = '/plant-hmi/api/history';
const MAX_PAGES = 40;

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style') node.style.cssText = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) node.append(c);
  return node;
}
const clockFmt = (ts) => (ts === null || ts === undefined ? '—'
  : new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour12: false }));

async function getJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(url, { signal: ctrl.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally { clearTimeout(timer); }
}

// Cursor-paginated fetch per the historian contract: cursor=0 first, follow next_cursor until
// null, hard-capped at MAX_PAGES pages. `stillCurrent()` is checked before every page request
// so a superseded run selection aborts instead of racing the newer one (H3).
async function fetchRunEvents(run, stillCurrent) {
  const events = [];
  let cursor = 0, total = null, page = 0;
  for (; page < MAX_PAGES; page += 1) {
    if (!stillCurrent()) return null;
    const body = await getJson(`${BASE}/events?run=${encodeURIComponent(run)}&cursor=${cursor}&limit=5000`);
    if (!stillCurrent()) return null;
    events.push(...(body.events || []));
    total = body.total ?? total;
    if (body.next_cursor === null || body.next_cursor === undefined) { cursor = null; break; }
    cursor = body.next_cursor;
  }
  return { events, total, truncated: cursor !== null };
}

export function initReplayControls(root, { onFrame, isReplayActive } = {}) {
  let runs = [];
  let currentRun = null;
  let currentEvents = [];          // kept so re-entering Replay can re-ingest without refetching (H2)
  let deriver = null;
  let speed = 1;
  let loadSeq = 0;                 // request token: bumped on every selectRun (H3)
  const active = () => (isReplayActive ? isReplayActive() : true);

  const clock = createReplayClock({ onTick: tick });
  const runSelect = h('select', { class: 'replay-select' }, h('option', { value: '' }, 'chọn run…'));
  const playBtn = h('button', { class: 'replay-btn', type: 'button', disabled: 'true' }, '▶ Chạy');
  const seek = h('input', { type: 'range', min: '0', max: '1000', value: '0', class: 'replay-seek', disabled: 'true' });
  const timeLabel = h('span', { class: 'replay-time mono' }, '—');
  const status = h('div', { class: 'replay-status muted' }, 'đang tải danh sách run…');
  const speedButtons = SPEEDS.map((s) => {
    const b = h('button', { class: `replay-speed${s === 1 ? ' active' : ''}`, type: 'button' }, `x${s}`);
    b.addEventListener('click', () => {
      speed = s; clock.setSpeed(s);
      for (const other of speedButtons) other.classList.toggle('active', other === b);
    });
    return b;
  });

  function tick(T) {
    if (!deriver || !currentRun) return;
    const frac = currentRun.first_ts === currentRun.last_ts ? 0
      : (T - currentRun.first_ts) / (currentRun.last_ts - currentRun.first_ts);
    seek.value = String(Math.round(frac * 1000));
    timeLabel.textContent = clockFmt(T);
    playBtn.textContent = clock.playing ? '⏸ Tạm dừng' : '▶ Chạy';
    renderParticles(T, T);                                    // replay: no display lag
    if (onFrame) onFrame(deriver.at(T), T);
  }

  playBtn.addEventListener('click', () => {
    if (!currentRun) return;
    if (clock.playing) clock.pause(); else clock.play();
    playBtn.textContent = clock.playing ? '⏸ Tạm dừng' : '▶ Chạy';
  });
  seek.addEventListener('input', () => { clock.pause(); clock.seek(Number(seek.value) / 1000); });

  async function selectRun(run) {
    const seq = ++loadSeq;
    currentRun = run;
    currentEvents = [];
    clock.pause();
    playBtn.disabled = true; seek.disabled = true;
    status.textContent = 'đang tải sự kiện của run…';
    try {
      const stillCurrent = () => seq === loadSeq && active();
      const result = await fetchRunEvents(run.run, stillCurrent);
      if (!result || !stillCurrent()) return;                // superseded or left Replay mode (H3)
      const events = result.events.sort((a, b) => a.ts - b.ts);
      currentEvents = events;
      resetParticles();
      ingestParticles(events);
      deriver = createDeriver(events, run);
      clock.setRange(run.first_ts, run.last_ts);
      clock.setSpeed(speed);
      playBtn.disabled = false; seek.disabled = false;
      const countMsg = result.truncated && result.total
        ? `đã cắt bớt: ${events.length.toLocaleString('vi-VN')}/${result.total.toLocaleString('vi-VN')} sự kiện`
        : `${events.length.toLocaleString('vi-VN')} sự kiện`;
      status.textContent = `${countMsg} · ${clockFmt(run.first_ts)} → ${clockFmt(run.last_ts)}`;
      tick(run.first_ts);
    } catch (err) {
      if (seq === loadSeq) status.textContent = `không tải được sự kiện: ${err.message}`;
    }
  }

  runSelect.addEventListener('change', () => {
    const run = runs.find((r) => String(r.run) === runSelect.value);
    if (run) selectRun(run);
  });

  async function loadRuns() {
    try {
      runs = await getJson(`${BASE}/runs`);
      for (const r of runs) {
        runSelect.append(h('option', { value: String(r.run) },
          `${r.run} · ${r.batch || '—'} · ${clockFmt(r.first_ts)} (${r.jobs_ok ?? 0} ok / ${r.jobs_failed ?? 0} lỗi)`));
      }
      status.textContent = runs.length ? 'chọn một run để phát lại' : 'chưa có run nào trong historian';
    } catch {
      status.textContent = 'chưa có dữ liệu historian';
    }
  }

  root.replaceChildren(
    h('div', { class: 'replay-row' }, runSelect, playBtn, timeLabel),
    h('div', { class: 'replay-row' }, seek),
    h('div', { class: 'replay-row' }, ...speedButtons),
    status);
  loadRuns();

  return {
    stop() { clock.pause(); },
    getRunRange() { return currentRun ? [currentRun.first_ts, currentRun.last_ts] : null; },
    // Re-ingests the already-fetched events of the current run without a network round-trip;
    // used when app.js switches back into Replay mode after visiting Live (H2).
    reactivate() {
      if (currentEvents.length) ingestParticles(currentEvents);
      if (currentRun) tick(clock.time);
    },
  };
}
