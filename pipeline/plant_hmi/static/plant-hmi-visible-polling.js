// Chained-setTimeout polling that runs only while the tab is visible: no pile-up
// (next run is scheduled after the previous one settles), resumes on visibilitychange.
// Returns a controller so callers can pause/resume polling (e.g. the Live/Replay switch).
// `task` receives an `isEnabled()` getter so it can bail after an `await` if setEnabled(false)
// fired while a request was in flight (M1): the in-flight request itself is not aborted, but
// its continuation must not apply state once polling has been disabled.
export function visiblePolling(task, ms) {
  let timer = null;
  let inFlight = false;
  let enabled = true;
  const isEnabled = () => enabled;
  async function loop() {
    timer = null;
    if (!enabled || document.hidden || inFlight) return;
    inFlight = true;
    try { await task(isEnabled); } catch { /* task reports its own errors */ }
    inFlight = false;
    if (enabled && !document.hidden) timer = setTimeout(loop, ms);
  }
  document.addEventListener('visibilitychange', () => {
    if (enabled && !document.hidden && !timer) loop();
  });
  loop();
  return {
    setEnabled(next) {
      enabled = next;
      if (enabled && !timer && !document.hidden) loop();
      if (!enabled && timer) { clearTimeout(timer); timer = null; }
    },
  };
}
