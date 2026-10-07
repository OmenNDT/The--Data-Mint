// Thin fetch wrapper for the batch start/stop control API (phase 6A): one place that
// knows the base path, request timeout, CSRF header (rule H1) and how to surface the
// server's 400/403/409/422/500 detail/error/failures payload as a thrown Error.
const BASE = '/plant-hmi/api/control/batch';
const READ_TIMEOUT_MS = 8000;
// M1: start/stop can take probes + `systemd-run` (10 s) + up to ~8 s of active/visible
// polling server-side; an 8 s client abort fired mid-launch, leaving the UI showing a
// false failure while the batch kept starting (and inviting a retry that feeds H2).
const WRITE_TIMEOUT_MS = 30000;

async function call(url, opts = {}, timeoutMs = READ_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal, cache: 'no-store' });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error(_detailText(body, res.status));
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  } finally { clearTimeout(timer); }
}

function _detailText(body, status) {
  if (!body) return `HTTP ${status}`;
  if (Array.isArray(body.failures)) {
    return body.failures.filter((f) => !f.ok).map((f) => `${f.code}: ${f.message}`).join('; ') ||
      body.error || `HTTP ${status}`;
  }
  const detail = body.detail || body.error;
  return typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : `HTTP ${status}`);
}

const postJson = (url, payload) => call(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
  body: JSON.stringify(payload),
}, WRITE_TIMEOUT_MS);

export const fetchBatchState = (configName) =>
  call(`${BASE}${configName ? `?config=${encodeURIComponent(configName)}` : ''}`);
export const fetchBatchAudit = (limit = 10) => call(`${BASE}/audit?limit=${limit}`);
export const startBatch = (config, pilot, resume, reason) =>
  postJson(`${BASE}/start`, { config, pilot, resume, reason });
export const stopBatch = (pid, startTs, reason) =>
  postJson(`${BASE}/stop`, { pid, start_ts: startTs, reason });
