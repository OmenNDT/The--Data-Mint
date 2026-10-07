// Tiny shared DOM helpers for the setpoint faceplate modules (row + list orchestration).
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    if (k === 'style') { node.style.cssText = v; continue; }
    if (k.startsWith('on') && typeof v === 'function') { node.addEventListener(k.slice(2), v); continue; }
    node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) node.append(c);
  return node;
}

export const fmtTime = (ts) => (ts === null || ts === undefined ? '—'
  : new Date(ts * 1000).toLocaleString('vi-VN', { hour12: false }));
