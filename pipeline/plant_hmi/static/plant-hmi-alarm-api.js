// Thin fetch wrapper for the alarm ack/shelve API (phase 6B), mirrors
// `plant-hmi-setpoint-api.js`: one place that knows the base path, the request timeout, the
// CSRF header (rule H1) and how to surface the server's 403/422/500 detail text.
const BASE = '/plant-hmi/api/alarms';

async function postJson(path, body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: 'POST', signal: ctrl.signal, cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = (data && (data.detail || data.error)) || `HTTP ${res.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  } finally { clearTimeout(timer); }
}

export const ackAlarm = (key, reason) => postJson('/ack', { key, reason });
export const ackAllAlarms = (keys, reason) => postJson('/ack-all', { keys, reason });
export const shelveAlarm = (key, minutes, reason) => postJson('/shelve', { key, minutes, reason });
export const unshelveAlarm = (key) => postJson('/unshelve', { key });
