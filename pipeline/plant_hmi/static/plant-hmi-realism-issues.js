/* Độ thật: bảng 5 vấn đề (bộ gốc → vòng mới nhất), lịch sử các vòng kèm đồ thị C2ST, bảng sáu tiêu chí. */
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v, d = 2) => v == null || !isFinite(v) ? '—'
    : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d, minimumFractionDigits: 0 });
  const CRIT = { vung_dac: 'Độ đặc', vung_huong: 'Góc nghiêng vùng', bien_daodong: 'Độ dao động dọc biên',
    vung_lechtam: 'Độ lệch tâm', vung_dayhop: 'Độ đầy hộp bao', bien_doc: 'Độ dốc tại biên (lần nhiễu)' };
  const MAIN = ['CR↔crack', 'PO↔porosity', 'LP↔lack_of_penetration', 'LP↔lack_of_fusion'];
  const PAIR_VI = { 'CR↔crack': 'Nứt', 'PO↔porosity': 'Rỗ khí', 'LP↔lack_of_penetration': 'Không thấu',
    'PO↔clustered_porosity': 'Rỗ khí dạng cụm', 'PO↔linear_porosity': 'Rỗ khí dạng chuỗi', 'LP↔lack_of_fusion': 'Không ngấu' };
  const ST = { pass: 'Đạt', fail: 'Chưa đạt', na: 'Chưa đo' };
  const DEC = { best: '✓ mốc', accepted: '✓ tốt hơn', neutral: '= không đổi', rejected: '✗ bị loại' };

  function tval(t) {
    const v = t.measured;
    if (v == null) return '—';
    if (t.stat === 'lt45') return num(100 * v, 1) + '%';
    if (t.stat === 'ratio') return num(v, 2) + '×';
    if (t.crit === 'vung_huong' && t.stat !== 'auc') return num(v, 1) + '°';
    return num(v, 3);
  }

  function renderIssues(el, iss) {
    const base = Object.fromEntries((iss.baseline || []).map(i => [i.id, i]));
    el.innerHTML = (iss.latest || []).map(i => {
      const b = base[i.id] || { targets: [], status: 'na' };
      const rows = i.targets.map((t, k) => `<tr><td>${esc(t.label)}</td><td class="num">${tval(b.targets[k] || {})}</td>
        <td class="num ${t.pass === true ? 'pass' : t.pass === false ? 'fail' : ''}">${tval(t)}</td></tr>`).join('');
      return `<div class="issue"><h3>${i.id}. ${esc(i.title)} <span class="st ${b.status}">gốc: ${ST[b.status]}</span>
          <span class="st ${i.status}">vòng ${iss.latest_iter ?? '—'}: ${ST[i.status]}</span></h3>
        <p><b>Phát hiện:</b> ${esc(i.finding)}</p><p><b>Việc cần làm:</b> ${esc(i.action)}</p>
        ${i.knobs.length ? `<p><b>Núm vặn:</b> ${i.knobs.map(esc).join(', ')}</p>` : ''}
        <div class="well"><table><thead><tr><th>Mục tiêu</th><th>Gốc</th><th>Mới nhất</th></tr></thead>
        <tbody>${rows}</tbody></table></div></div>`;
    }).join('') || '<p class="msg">Chưa có lượt đo nào: bấm "1 · Đánh giá bộ mới nhất".</p>';
  }

  function renderHistory(tableEl, trendEl, h) {
    tableEl.innerHTML = h.length ? `<table><thead><tr><th>Vòng</th><th>Bộ ảnh</th><th>Thước</th><th>Vấn đề đạt</th><th>Cổng</th>
      ${MAIN.map(p => `<th>C2ST ${PAIR_VI[p]}</th>`).join('')}</tr></thead><tbody>${h.slice().reverse().map(r => {
        const ok = Object.values(r.issues || {}).filter(s => s === 'pass').length;
        const dec = `<span title="${esc((r.reasons || []).join('; '))}">${DEC[r.decision] || '—'}${r.compared_to != null ? ` (so vòng ${r.compared_to})` : ''}</span>`;
        const mean16 = r.v2 && r.v2.mean_c2st16 != null ? ` · C2ST16 ${num(r.v2.mean_c2st16, 3)}` : '';
        const ruler = r.ruler === 'v2' ? `v2${mean16}` : 'v1';
        return `<tr><td class="num">${r.iter}</td><td>${esc(String(r.source).split('/').slice(-2).join('/'))}</td>
          <td>${ruler}</td><td class="num ${r.all_pass ? 'pass' : ''}">${ok} / 5</td><td>${dec}</td>
          ${MAIN.map(p => `<td class="num">${num((r.c2st || {})[p], 3)}</td>`).join('')}</tr>`;
      }).join('')}</tbody></table>` : '';
    const W = 640, H = 170, X0 = 44, X1 = W - 12, Y0 = 14, Y1 = H - 28;
    const n = Math.max(h.length - 1, 1), sx = i => X0 + (X1 - X0) * i / n, sy = v => Y1 - (Y1 - Y0) * (v - 0.5) / 0.5;
    const cols = ['#d0655f', '#5ec8d8', '#c9a15e'];
    let g = [0.5, 0.75, 1].map(v => `<line x1="${X0}" x2="${X1}" y1="${sy(v)}" y2="${sy(v)}" stroke="rgba(255,255,255,.07)"/>
      <text x="${X0 - 6}" y="${sy(v) + 4}" font-size="10.5" fill="#8a8aa0" text-anchor="end">${num(v, 2)}</text>`).join('');
    g += `<text x="${X0}" y="${H - 8}" font-size="10.5" fill="#8a8aa0">C2ST theo vòng (0,5 là không phân biệt được thật/sinh); nét đứt = bản tốt nhất tại thời điểm đó</text>`;
    // Đường "tốt nhất tới lúc đó": TB C2ST các cặp chính của vòng đang là mốc/được nhận gần nhất, giữ ngang tới
    // khi có mốc mới (suy lại từ decision mỗi dòng lịch sử, không cần gọi API riêng).
    let runningBest = null, bestPts = [];
    h.forEach((r, i) => {
      if (r.decision === 'best' || r.decision === 'accepted') {
        const vals = MAIN.map(p => (r.c2st || {})[p]).filter(v => v != null);
        if (vals.length) runningBest = vals.reduce((a, b) => a + b, 0) / vals.length;
      }
      if (runningBest != null) bestPts.push([runningBest, i]);
    });
    if (bestPts.length) {
      g += `<polyline fill="none" stroke="#9a9ab0" stroke-width="1.5" stroke-dasharray="4,3"
        points="${bestPts.map(([v, i]) => `${sx(i)},${sy(Math.max(v, .5))}`).join(' ')}"/>`;
    }
    MAIN.forEach((p, k) => {
      const pts = h.map((r, i) => [(r.c2st || {})[p], i]).filter(x => x[0] != null);
      if (!pts.length) return;
      g += `<polyline fill="none" stroke="${cols[k]}" stroke-width="2" points="${pts.map(([v, i]) => `${sx(i)},${sy(Math.max(v, .5))}`).join(' ')}"/>`
        + pts.map(([v, i]) => `<circle cx="${sx(i)}" cy="${sy(Math.max(v, .5))}" r="3" fill="${cols[k]}"/>`).join('')
        + `<text x="${X1 - 150}" y="${Y0 + 12 + 13 * k}" font-size="11" fill="${cols[k]}">${PAIR_VI[p]}</text>`;
    });
    trendEl.innerHTML = h.length ? `<svg viewBox="0 0 ${W} ${H}" style="width:100%;min-width:420px">${g}</svg>` : '<p class="msg">Chưa có vòng nào.</p>';
  }

  function aucClass(a) { if (a == null) return ''; const d = Math.abs(a - 0.5); return d > 0.25 ? 'hi' : d > 0.1 ? 'lo' : ''; }

  const kidCell = k => (k ? `${num(k.value, 3)} [${num(k.ci_low, 3)}, ${num(k.ci_high, 3)}]` : '—');

  // Mục tiêu v2 tuyệt đối (mirror realism/issues_v2.py, không gọi lại server): null=None nghĩa là chưa đo được.
  const boundOk = (v, lo, hi) => v == null ? null : (lo == null || v >= lo) && (hi == null || v <= hi);
  const passCls = ok => ok === true ? 'pass' : ok === false ? 'fail' : '';

  function renderDefectMetrics(el, latest) {
    const dm = latest && latest.defect_metrics;
    if (!dm || !dm.types || !dm.types.length) {
      el.innerHTML = `<p class="msg">${dm && dm.error ? 'Lỗi đo thước mới: ' + esc(dm.error) : 'Chưa có kết quả thước mới (bấm "1 · Đánh giá bộ mới nhất").'}</p>`;
      return;
    }
    el.innerHTML = `<table><thead><tr><th>Loại lỗi</th><th>Tham chiếu W0003</th><th>n thật/sinh</th>
      <th>Tách vùng thật/sinh</th><th>C2ST (hoàn hảo)</th><th>KID [CI] (hoàn hảo)</th>
      <th>Density (hoàn hảo)</th><th>Coverage (hoàn hảo)</th></tr></thead><tbody>
      ${dm.types.map(e => {
        if (e.reference == null) {
          return `<tr><td>${esc(e.defect_type)}</td><td class="msg">— (chưa có mẫu thật)</td><td class="num">—/${e.n_syn}</td>
            <td class="num">—/${num(e.detection_rate_syn, 2)}</td><td class="num">—</td><td class="num">—</td>
            <td class="num">—</td><td class="num">—</td></tr>`;
        }
        const p = e.perfect || {}, nul = e.null || {};
        const warn = e.small_reference ? ' <span class="st fail" title="Tham chiếu W0003 ít mẫu, chỉ báo, không dùng làm cổng">ít mẫu</span>' : '';
        const c2st = e.c2st_reason ? `— <span class="msg" title="${esc(e.c2st_reason)}">(?)</span>` : num(e.c2st, 3);
        const detOk = boundOk(e.detection_rate_real != null && e.detection_rate_syn != null
          ? e.detection_rate_real - e.detection_rate_syn : null, null, 0.10);
        const c2stOk = e.c2st_reason ? null : boundOk(e.c2st, null, (nul.c2st || {}).p95);
        const kidOk = boundOk((e.kid || {}).value, null, (nul.kid || {}).p95);
        const dc = e.density_coverage || {};
        const densOk = boundOk(dc.density, (nul.density || {}).p5, (nul.density || {}).p95);
        const covOk = boundOk(dc.coverage, (nul.coverage || {}).p5, null);
        return `<tr><td>${esc(e.defect_type)}${warn}</td><td>${esc(e.reference)}</td>
          <td class="num">${e.n_real}/${e.n_syn}</td>
          <td class="num ${passCls(detOk)}">${num(e.detection_rate_real, 2)}/${num(e.detection_rate_syn, 2)}</td>
          <td class="num ${passCls(c2stOk)}">${c2st} (${num(p.c2st, 3)})</td>
          <td class="num ${passCls(kidOk)}">${kidCell(e.kid)} (${num(p.kid, 3)})</td>
          <td class="num ${passCls(densOk)}">${num(dc.density, 3)} (${num(p.density, 3)})</td>
          <td class="num ${passCls(covOk)}">${num(dc.coverage, 3)} (${num(p.coverage, 3)})</td></tr>`;
      }).join('')}</tbody></table>`;
  }

  function renderResults(el, base, latest, showAll) {
    if (!latest) { el.innerHTML = '<p class="msg">Chưa có kết quả.</p>'; return; }
    const pairs = latest.pairs.filter(p => showAll || MAIN.includes(p.pair));
    const bmap = Object.fromEntries(((base || {}).pairs || []).map(p => [p.pair, p]));
    const cell = (d, k) => d && d.syn_med != null ? `${num(d.syn_med, k === 'vung_huong' ? 1 : 3)} (${num(d.auc, 2)})` : '—';
    el.innerHTML = `<table><thead><tr><th>Tiêu chí</th>${pairs.map(p => `<th>${PAIR_VI[p.pair] || p.pair}<br><span class="msg">
      dùng ${p.n_used}/${p.n_syn} · C2ST ${num(p.c2st, 3)}</span></th>`).join('')}</tr></thead><tbody>
      ${Object.keys(CRIT).map(k => `<tr><td>${CRIT[k]}</td>${pairs.map(p => {
        const d = p.crit[k], b = ((bmap[p.pair] || {}).crit || {})[k];
        const vert = k === 'vung_huong' ? `<br><span class="msg">đứng: thật ${num(100 * d.real_lt45, 0)}%, mới ${num(100 * (d.syn_lt45 ?? NaN), 0)}%</span>` : '';
        return `<td class="num ${aucClass(d.auc)}">${num(d.real_med, k === 'vung_huong' ? 1 : 3)} · ${cell(b, k)} → ${cell(d, k)}${vert}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table>`;
  }

  window.RealismIssues = { renderIssues, renderHistory, renderResults, renderDefectMetrics, num, esc };
})();
