// Plant HMI page: Live polls the snapshot while the tab is visible; Replay derives the same
// snapshot shape from historian events. Both modes render through the shared panel functions.
import { buildDiagram } from './plant-hmi-pid-diagram.js';
import { updateDiagram } from './plant-hmi-pid-update.js';
import { initParticles, setAlivePids, setMode as setParticleMode, reset as resetParticles } from './plant-hmi-particle-layer.js';
import { startEventStream, resetEventStream } from './plant-hmi-event-stream.js';
import { visiblePolling } from './plant-hmi-visible-polling.js';
import { initReplayControls } from './plant-hmi-replay-controls.js';
import { initTrendPanel } from './plant-hmi-trend-panel.js';
import { initAlarmJournal } from './plant-hmi-alarm-journal.js';
import { initComfyProgressPanel } from './plant-hmi-comfyui-progress-panel.js';
import { initSetpointFaceplate } from './plant-hmi-setpoint-faceplate.js';
import { initBatchControl } from './plant-hmi-batch-control.js';
import { initOperatorTools } from './plant-hmi-operator-tools.js';
import {
  $, clock, setConn, renderAlarms, renderBatches, renderUtilities, renderDetail,
} from './plant-hmi-render-panels.js';

const POLL_MS = 3000;
const LABELS = {
  'TK-102': 'Hàng đợi job', 'R-201': 'Sinh mask', 'TK-101': 'Nền X-ray sạch',
  'P-601': 'Bơm inpaint', 'R-401': 'Hậu xử lý', 'TK-801': 'Silo ảnh', 'D-901': 'Job lỗi',
};
let snap = null;
let selected = null;
let mode = 'live';

function select(tag) {
  selected = selected === tag ? null : tag;
  for (const g of document.querySelectorAll('.eq')) g.classList.toggle('selected', g.dataset.tag === selected);
  if (snap) renderDetail(snap, selected);
}

function renderAll(prefix) {
  updateDiagram($('pid'), snap);
  renderAlarms(snap); renderBatches(snap); renderUtilities(snap); renderDetail(snap, selected);
  setConn(true, `${prefix} · ${clock(snap.ts)}`);
}

async function poll(isEnabled = () => true) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000);
  try {
    const res = await fetch('/plant-hmi/api/snapshot', { signal: ctrl.signal, cache: 'no-store' });
    if (!isEnabled()) return;                  // switched to replay while the request was in flight (M1)
    const body = await res.json();
    if (!isEnabled()) return;
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    snap = body;
    setAlivePids(snap.batches.map((b) => b.pid));
    renderAll('trực tiếp');
  } catch (err) {
    if (isEnabled()) setConn(false, `mất kết nối · ${err.name === 'AbortError' ? 'quá thời gian' : err.message}`);
  } finally {
    clearTimeout(timer);
  }
}

buildDiagram($('pid'), LABELS, select);
initParticles($('pid'));
const snapshotPoller = visiblePolling(poll, POLL_MS);
initComfyProgressPanel(document.getElementById('comfy-progress'));
initSetpointFaceplate(document.getElementById('setpoint-faceplate'));
initBatchControl(document.getElementById('batch-control'));
initOperatorTools(document.getElementById('operator-tools'));
const eventPoller = startEventStream();

// Replay derives a diagram-compatible snapshot from historian events; reuse the same render
// functions as Live so the whole P&ID (levels, alarms, batches, detail drawer) stays consistent.
// Only this module (app.js) ever calls setParticleMode (H3); replay-controls only ingests/resets.
const replay = initReplayControls($('replay-controls'), {
  isReplayActive: () => mode === 'replay',
  onFrame: (derivedSnap) => {
    if (mode !== 'replay') return;
    snap = derivedSnap;
    renderAll('phát lại');
  },
});
initTrendPanel($('trend-panel'), { getRunRange: replay.getRunRange });
initAlarmJournal($('alarm-journal'), { getRunRange: replay.getRunRange });

function setMode(next) {
  if (next === mode) return;
  mode = next;
  $('mode-live').setAttribute('aria-pressed', String(mode === 'live'));
  $('mode-replay').setAttribute('aria-pressed', String(mode === 'replay'));
  $('replay-card').hidden = mode !== 'replay';
  snapshotPoller.setEnabled(mode === 'live');
  eventPoller.setEnabled(mode === 'live');
  if (mode === 'live') {
    replay.stop();
    resetEventStream();
    resetParticles();
    setParticleMode('live');
    poll();                                  // snappy resume instead of waiting for next tick
  } else {
    setParticleMode('replay');
    resetParticles();
    replay.reactivate();                       // re-ingest the current run's events (H2)
  }
}
$('mode-live').addEventListener('click', () => setMode('live'));
$('mode-replay').addEventListener('click', () => setMode('replay'));
