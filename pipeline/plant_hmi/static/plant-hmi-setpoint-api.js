// Thin fetch wrapper for the setpoint control API: one place that knows the base path,
// the request timeout, the CSRF header (rule H1: X-Plant-HMI, checked together with
// Origin/Sec-Fetch-Site server-side) and how to surface the server's 403/422/500 detail text.
const BASE = '/plant-hmi/api/control';

async function getJson(url, opts = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal, cache: 'no-store' });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = (body && (body.detail || body.error)) || `HTTP ${res.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return body;
  } finally { clearTimeout(timer); }
}

export const fetchSetpoints = () => getJson(`${BASE}/setpoints`);
export const fetchAudit = (limit = 10) => getJson(`${BASE}/audit?limit=${limit}`);
export const putSetpoint = (key, value, reason) => getJson(`${BASE}/setpoints/${key}`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
  body: JSON.stringify({ value, reason }),
});
export const clearSetpoint = (key, reason) => getJson(`${BASE}/setpoints/${key}`, {
  method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
  body: JSON.stringify({ reason }),
});
