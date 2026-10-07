// Thin fetch wrapper for the "Tạo mẻ mới" compose API (new-batch form): same
// contract as plant-hmi-batch-control-api.js (base path, timeouts, CSRF header,
// 400/403/404/500 detail/error/failures surfaced as a thrown Error).
const BASE = '/plant-hmi/api/control/batch';
const READ_TIMEOUT_MS = 8000;
const WRITE_TIMEOUT_MS = 15000; // compose only validates + writes one YAML file, no systemd-run wait

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
    return body.failures.map((f) => f.message || f.field).join('; ') || body.error || `HTTP ${status}`;
  }
  const detail = body.detail || body.error;
  return typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : `HTTP ${status}`);
}

export const fetchComposeOptions = (base) =>
  call(`${BASE}/compose-options${base ? `?base=${encodeURIComponent(base)}` : ''}`);

export const composeBatch = (payload) => call(`${BASE}/compose`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
  body: JSON.stringify(payload),
}, WRITE_TIMEOUT_MS);
