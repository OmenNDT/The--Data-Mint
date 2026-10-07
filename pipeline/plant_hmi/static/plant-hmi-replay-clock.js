// Virtual replay clock over [start, end] seconds of a historian run. Speed multiplies
// wall-clock progress (x1/x10/x60/x600); the per-frame wall delta is capped (~250 ms) so a
// backgrounded tab does not teleport far ahead when it regains focus. Auto-pauses at `end`.
const FRAME_CAP_MS = 250;

export function createReplayClock({ onTick } = {}) {
  let start = 0, end = 0, t = 0, speed = 1, playing = false, rafId = null, lastWall = null;

  function emit() { if (onTick) onTick(t); }

  // Resets the playhead to `start`; call again whenever the selected run changes.
  function setRange(newStart, newEnd) {
    pause();
    start = newStart; end = Math.max(newStart, newEnd); t = start;
    emit();
  }

  function seek(fraction) {
    const clamped = Math.max(0, Math.min(1, fraction));
    t = start + (end - start) * clamped;
    emit();
  }

  function setSpeed(next) { speed = next; }

  function step(now) {
    rafId = null;
    const deltaMs = lastWall === null ? 0 : Math.min(FRAME_CAP_MS, now - lastWall);
    lastWall = now;
    t = Math.min(end, t + (deltaMs / 1000) * speed);
    const done = t >= end;
    if (done) playing = false;    // set before emit() so onTick reads the correct paused state (L6)
    emit();
    if (done) return;
    if (playing) rafId = requestAnimationFrame(step);
  }

  function play() {
    if (playing || start >= end) return;
    if (t >= end) t = start;               // replay again from the top after auto-pause
    playing = true;
    lastWall = null;
    rafId = requestAnimationFrame(step);
  }

  function pause() {
    playing = false;
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
    lastWall = null;
  }

  return {
    setRange, seek, setSpeed, play, pause,
    get time() { return t; },
    get playing() { return playing; },
    get start() { return start; },
    get end() { return end; },
  };
}
