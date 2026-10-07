// Pulls telemetry flow records for the particle layer every 2 s (visible tab only, live mode).
import { ingest, setServerTime, reset as resetParticles } from './plant-hmi-particle-layer.js';
import { visiblePolling } from './plant-hmi-visible-polling.js';

let since = null;

async function pull(isEnabled = () => true) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000);
  try {
    const q = since === null ? '' : `?since=${since}`;
    const res = await fetch(`/plant-hmi/api/events${q}`, { signal: ctrl.signal, cache: 'no-store' });
    if (!isEnabled() || !res.ok) return;        // switched to replay while the request was in flight (M1)
    const body = await res.json();
    if (!isEnabled()) return;
    setServerTime(body.ts);                    // the only place the live clock offset is set
    if (body.truncated) { resetParticles(); since = null; }
    // first load (or right after a truncated response): only the last minute, so old jobs
    // do not replay on open
    const events = since === null ? body.events.filter((e) => e.ts > body.ts - 60) : body.events;
    since = body.cursor ?? body.ts;             // server-declared cursor is always the next `since`
    ingest(events);
  } finally {
    clearTimeout(timer);
  }
}

// Forces the next poll to behave like a first load; used when switching back from replay so
// stale historical `since` values do not replay a burst of old jobs.
export function resetEventStream() {
  since = null;
}

export function startEventStream() {
  return visiblePolling(pull, 2000);
}
