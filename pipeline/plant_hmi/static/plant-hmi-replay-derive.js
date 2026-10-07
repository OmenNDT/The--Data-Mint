// Pure derivation of a diagram-compatible "snapshot" from replayed events: produced = ok
// outcomes so far, failed = failed outcomes so far, running = units with an open enter.
// Shaped exactly like the live snapshot so plant-hmi-app.js's existing render functions
// (updateDiagram, renderAlarms, renderBatches, renderUtilities, renderDetail) work unchanged
// when fed a replay-derived object instead of the polled one.
const RUN_TAGS = ['R-201', 'P-601', 'R-401'];
const CHECKPOINT_EVERY = 2000;    // bounds backward-seek replay cost (L8)

function buildSnapshot(T, produced, failed, pendingIn, running, meta) {
  const equipment = {
    'TK-102': { state: 'idle', level: pendingIn, unit: 'job', label: 'Hàng đợi job' },
    'TK-801': { state: 'idle', level: produced, max: meta.target ?? null, unit: 'ảnh', label: 'Silo ảnh' },
    'D-901': { state: failed > 0 ? 'running' : 'idle', level: failed, unit: 'job', label: 'Job lỗi' },
  };
  for (const tag of RUN_TAGS) {
    const n = running[tag] || 0;
    equipment[tag] = { state: n > 0 ? 'running' : 'idle', level: n };
  }
  const anyRunning = Object.values(running).some((n) => n > 0);
  return {
    ts: T,
    equipment,
    alarms: [],                                 // see plant-hmi-alarm-journal.js for replay alarms
    batches: anyRunning || produced || failed
      ? [{ pid: meta.pid ?? null, produced, target: meta.target ?? null, failed, pilot: false,
           config_name: meta.batch ?? '—', uptime_s: T - (meta.first_ts ?? T),
           rate_img_h: null, eta_s: null, newest_image_ts: null }]
      : [],
    instruments: {},
    flows: { stages: {}, has_telemetry: false, thermal_hold: false },
    // GPU/ComfyUI/host are not part of the historian record: never fabricate ok:false/0 values
    // that would look like real faults (M7); the render panel shows "không có dữ liệu khi phát lại".
    utilities: { gpu: { unavailable: true }, comfy: { unavailable: true }, host: { unavailable: true } },
  };
}

// Incremental deriver: events must be sorted ascending by ts (the historian contract
// guarantees this per run). Walking forward from the last position is O(1) amortised. A
// checkpoint of the running totals is snapshotted every CHECKPOINT_EVERY events so a backward
// seek (scrubbing the slider) only replays from the nearest checkpoint, not from event 0 (L8).
export function createDeriver(events, meta = {}) {
  const sorted = events;
  let idx, produced, failed, jobsSeen, terminal, running, checkpoints;

  function freshState() {
    idx = 0; produced = 0; failed = 0; running = {};
    jobsSeen = new Set(); terminal = new Set();
    checkpoints = [{ idx: 0, produced: 0, failed: 0, running: {}, jobsSeen: new Set(), terminal: new Set() }];
  }
  freshState();

  function restore(cp) {
    idx = cp.idx; produced = cp.produced; failed = cp.failed;
    running = { ...cp.running };
    jobsSeen = new Set(cp.jobsSeen);
    terminal = new Set(cp.terminal);
  }

  // Last checkpoint whose event timestamp is still <= T.
  function checkpointFor(T) {
    let best = checkpoints[0];
    for (const cp of checkpoints) {
      if (cp.idx === 0 || sorted[cp.idx - 1].ts <= T) best = cp; else break;
    }
    return best;
  }

  function at(T) {
    if (idx > 0 && sorted[idx - 1].ts > T) restore(checkpointFor(T));
    while (idx < sorted.length && sorted[idx].ts <= T) {
      const ev = sorted[idx];
      idx += 1;
      if (ev.job === null || ev.job === undefined) continue;
      jobsSeen.add(ev.job);
      if (ev.kind === 'enter') {
        if (ev.tag === 'U-901') continue;       // thermal hold: not a unit on the line
        running[ev.tag] = (running[ev.tag] || 0) + 1;
      } else if (ev.kind === 'exit') {
        if (running[ev.tag]) running[ev.tag] -= 1;
      } else if (ev.kind === 'job' && !terminal.has(ev.job)) {
        if (ev.outcome === 'ok') { terminal.add(ev.job); produced += 1; }
        else if (ev.outcome === 'failed') { terminal.add(ev.job); failed += 1; }
      }
      if (idx % CHECKPOINT_EVERY === 0) {
        checkpoints.push({ idx, produced, failed, running: { ...running },
          jobsSeen: new Set(jobsSeen), terminal: new Set(terminal) });
      }
    }
    const pendingIn = Math.max(0, jobsSeen.size - terminal.size);
    return buildSnapshot(T, produced, failed, pendingIn, running, meta);
  }

  return { at, reset: freshState };
}
