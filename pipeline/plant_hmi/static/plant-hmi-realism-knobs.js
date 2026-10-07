/* Độ thật: bảng núm vặn kiểu faceplate DCS. Mỗi núm: THỬ (kho núm thử của vòng lặp, sửa được), SẢN XUẤT (kho mọi đợt
   sinh của launcher đọc), PV (giá trị đợt sinh gần nhất đã nạp). Mọi thao tác ghi đều hai bước (Đặt → Xác nhận / Huỷ),
   không dùng window.confirm; lúc xác nhận đọc lại ô nhập nên giá trị gửi đi luôn là giá trị đang hiện. */
(function () {
  const { num, esc } = window.RealismIssues;
  const ISSUE_TITLE = { 1: 'Vấn đề 1 · mép', 2: 'Vấn đề 2 · nứt', 3: 'Vấn đề 3 · rỗ khí', 4: 'Vấn đề 4 · không thấu' };
  const H = { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' };
  let armed = null;                                   // khoá nút đang chờ xác nhận

  async function send(method, url, body) {
    const r = await fetch(url, { method, headers: H, body: JSON.stringify(body || {}) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || ('lỗi ' + r.status));
  }

  function btn(key, label, confirmLabel, attrs) {
    const on = armed === key;
    return `<button type="button" data-key="${esc(key)}" ${attrs || ''} class="${on ? 'armed' : ''}">${on ? confirmLabel : label}</button>`
      + (on ? '<button type="button" data-cancel="1">Huỷ</button>' : '');
  }

  function render(el, auditEl, k, best, onSaved) {
    const byIssue = {};
    Object.entries(k.registry).forEach(([n, s]) => (byIssue[s.issue] = byIssue[s.issue] || []).push([n, s]));
    const promoteLabel = best ? `Đưa bản tốt nhất (vòng ${best.iter}) vào sản xuất` : 'Đưa bản tốt nhất vào sản xuất';
    const bestLine = best
      ? `<p class="msg">Bản tốt nhất: vòng ${best.iter}${best.score ? ` · đạt ${best.score.n_pass}/5 · C2ST TB ${num(best.score.mean_c2st, 3)}` : ''}</p>`
      : '<p class="msg">Chưa có bản tốt nhất (chạy một vòng trên bộ đề thi trước).</p>';
    el.innerHTML = `${bestLine}<div class="ctl">${btn('promote', promoteLabel, 'Xác nhận: sản xuất dùng núm bản tốt nhất', best ? '' : 'disabled')}
        ${btn('reset', 'Sản xuất về mặc định', 'Xác nhận: sản xuất về hành vi cũ')}</div>
      ${k.env_override ? '<p class="warn">Launcher đang có env REALISM_KNOBS: đè lên kho sản xuất.</p>' : ''}`
      + Object.entries(byIssue).map(([iss, list]) => {
        const fix = Object.fromEntries(list.map(([n, s]) => [n, s.fix]));
        return `<div class="issue"><h3>${ISSUE_TITLE[iss] || 'Vấn đề ' + iss}
          ${btn('preset-' + iss, 'Núm thử = giá trị sửa đề xuất', 'Xác nhận đặt', `data-changes="${esc(JSON.stringify(fix))}"`)}</h3>
          ${list.map(([n, s]) => {
            const c = k.candidate[n] || {}, p = k.production[n] || {}, pv = (k.pv || {})[n];
            return `<div class="knob"><div><div class="lbl">${esc(s.label)}</div>
              <div class="lim">${esc(n)} · ${num(s.min, 2)} tới ${num(s.max, 2)} · mặc định ${num(s.default, 2)} · đề xuất ${num(s.fix, 2)}</div></div>
              <div class="sppv"><span>thử</span>${num(c.value, 3)}<span>sx</span>${num(p.value, 3)}<span>PV</span>${pv ? num(pv.value, 3) : '—'}</div>
              <div class="edit"><input data-in="${esc(n)}" type="number" step="any" value="${c.value}">
                ${btn('set-' + n, 'Đặt núm thử', 'Xác nhận', `data-set="${esc(n)}"`)}</div></div>`;
          }).join('')}</div>`;
      }).join('') + '<div id="knob-err" class="err"></div>';
    auditEl.innerHTML = (k.audit || []).map(a => `<li>${new Date(a.ts * 1000).toLocaleString('vi-VN')} · ${esc(a.store || '')}
      · ${esc(a.who)} · ${esc(a.name)} ${num(a.old, 3)} → ${num(a.new, 3)}${a.reason ? ' · ' + esc(a.reason) : ''}</li>`).join('');

    el.onclick = async e => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.cancel) { armed = null; onSaved(); return; }
      const key = b.dataset.key;
      if (key === 'promote' && !best) return;                 // chưa có bản tốt nhất: nút khoá, không làm gì
      if (armed !== key) { armed = key; render(el, auditEl, k, best, onSaved); return; }
      try {
        if (key === 'promote') await send('POST', '/plant-hmi/realism/api/promote');
        else if (key === 'reset') await send('POST', '/plant-hmi/realism/api/reset-production');
        else if (b.dataset.set) {
          const v = Number(el.querySelector(`[data-in="${b.dataset.set}"]`).value);   // đọc lại lúc xác nhận
          await send('PUT', '/plant-hmi/realism/api/knobs', { changes: { [b.dataset.set]: v }, reason: 'chỉnh tay trên HMI' });
        } else {
          await send('PUT', '/plant-hmi/realism/api/knobs', { changes: JSON.parse(b.dataset.changes),
            reason: `núm thử = giá trị sửa đề xuất, ${key}` });
        }
        armed = null; onSaved();
      } catch (err) { el.querySelector('#knob-err').textContent = err.message; }
    };
  }

  window.RealismKnobs = { render, isEditing: () => !!armed };
})();
