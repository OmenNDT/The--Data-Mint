/* Cổng v2 (thước 16 đặc trưng khuyết tật, tham chiếu W0003 thật): quyết định + chi tiết từng loại, đọc từ
   dòng lịch sử v2 gần nhất (rec.ruler === 'v2', rec.v2.types ghi trong realism/loop_gate_v2.gate_v2). */
(function () {
  const { esc, num } = window.RealismIssues;
  const DEC = { best: '✓ mốc', accepted: '✓ tốt hơn', neutral: '= không đổi', rejected: '✗ bị loại' };
  const METRIC_LABEL = { c2st: 'C2ST', kid: 'KID', density: 'Density', coverage: 'Coverage' };
  const VERDICT = { better: 'tốt hơn', worse: 'tệ hơn', same: 'không đổi' };

  function metricCell(mv) {
    if (!mv) return '<td class="num">—</td>';
    const cls = mv.verdict === 'worse' ? 'fail' : mv.verdict === 'better' ? 'pass' : '';
    return `<td class="num ${cls}">${num(mv.new, 3)} so ${num(mv.best, 3)} (${VERDICT[mv.verdict] || '—'})</td>`;
  }

  function typeRow(t, e) {
    const d = e.detection || {};
    const detCell = `<td class="num ${d.blocked ? 'fail' : ''}">${num(d.real, 2)} / ${num(d.new, 2)}
      (kém ${num(100 * (d.gap_new ?? NaN), 1)} đ%)${d.blocked ? ' · CHẶN' : ''}</td>`;
    if (e.skip_reason) {
      return `<tr><td>${esc(t)}</td>${detCell}<td colspan="4" class="msg">${esc(e.skip_reason)}</td></tr>`;
    }
    const m = e.metrics || {};
    return `<tr><td>${esc(t)}</td>${detCell}${['c2st', 'kid', 'density', 'coverage'].map(k => metricCell(m[k])).join('')}</tr>`;
  }

  function renderV2Gate(el, history) {
    const rec = (history || []).slice().reverse().find(r => r.ruler === 'v2');
    if (!rec) {
      el.innerHTML = '<p class="msg">Chưa có vòng nào dùng thước mới (v2): chạy "1 · Đánh giá bộ mới nhất".</p>';
      return;
    }
    const v2 = rec.v2 || {};
    const types = v2.types || {};
    const head = `<p><span class="st ${rec.decision === 'rejected' ? 'fail' : rec.decision === 'neutral' ? '' : 'pass'}">
        ${DEC[rec.decision] || rec.decision}</span> (vòng ${rec.iter}${rec.compared_to != null ? `, so vòng ${rec.compared_to}` : ''})
        ${v2.mean_c2st16 != null ? ` · C2ST16 trung bình ${num(v2.mean_c2st16, 3)}` : ''}</p>
      <ul>${(rec.reasons || []).map(r => `<li>${esc(r)}</li>`).join('')}</ul>`;
    const typeKeys = Object.keys(types);
    const table = typeKeys.length
      ? `<table><thead><tr><th>Loại</th><th>Tách vùng thật/sinh</th>
          ${['c2st', 'kid', 'density', 'coverage'].map(k => `<th>${METRIC_LABEL[k]}</th>`).join('')}</tr></thead>
          <tbody>${typeKeys.map(t => typeRow(t, types[t])).join('')}</tbody></table>`
      : '<p class="msg">Chưa có loại nào đủ điều kiện so cặp ở vòng này (xem phần chỉ báo dưới).</p>';
    const ignored = (v2.ignored || []).length
      ? `<p class="msg">Chỉ báo (chưa đủ điều kiện so cặp, không ảnh hưởng quyết định): ${v2.ignored.map(esc).join(', ')}</p>`
      : '';
    el.innerHTML = head + table + ignored;
  }

  window.RealismV2 = { renderV2Gate };
})();
