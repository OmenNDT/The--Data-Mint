/* Độ thật: hỏi trạng thái mỗi 3 giây khi tab đang hiện, vẽ lại các bảng, điều khiển vòng lặp.
   Nút nặng (đề xuất, sinh lại, tự lặp, dừng) bấm hai lần: lần đầu nhá hổ phách, lần hai mới gửi (hết hạn sau 6 giây). */
(function () {
  const $ = id => document.getElementById(id);
  const { renderIssues, renderHistory, renderResults, renderDefectMetrics, num, esc } = window.RealismIssues;
  const TYPES = [['crack', 'Nứt', 1], ['porosity', 'Rỗ khí', 1], ['lack_of_penetration', 'Không thấu', 1],
    ['clustered_porosity', 'Rỗ khí dạng cụm', 0], ['linear_porosity', 'Rỗ khí dạng chuỗi', 0], ['lack_of_fusion', 'Không ngấu', 1]];
  const STAGE = { evaluate: 'Đang đo sáu tiêu chí', generate: 'Đang sinh ảnh', propose: 'Đề xuất núm', auto: 'Tự lặp' };
  const JOB = { idle: 'rảnh', running: 'đang chạy', done: 'xong', failed: 'lỗi', stopped: 'đã dừng', dead: 'tiến trình đã chết' };
  let last = null, results = {}, armedBtn = null, armTimer = null, timer = null;

  $('types').insertAdjacentHTML('beforeend', TYPES.map(([id, vi, on]) =>
    `<label><input type="checkbox" value="${id}" ${on ? 'checked' : ''} style="width:auto"> ${vi}</label>`).join(''));

  async function getJSON(url) { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) throw new Error(r.status); return r.json(); }

  async function result(id) {
    if (!id) return null;
    if (!(id in results)) results[id] = await getJSON(`/plant-hmi/realism/api/result/${encodeURIComponent(id)}`).catch(() => null);
    return results[id];
  }

  function renderJob(j) {
    const running = j.state === 'running';
    $('job-badge').textContent = `vòng lặp: ${JOB[j.state] || j.state}${j.action ? ' · ' + j.action : ''}`;
    $('job-badge').className = 'badge ' + j.state;
    ['btn-evaluate', 'btn-propose', 'btn-cycle', 'btn-auto'].forEach(b => { $(b).disabled = running; });
    $('btn-stop').disabled = !running;
    let pct = 0, stage = STAGE[j.stage] || j.stage || '—';
    if (j.stage === 'generate' && j.gen_total) { pct = 100 * j.gen_done / j.gen_total; stage += ` (vòng ${j.gen_iter}): ${j.gen_done}/${j.gen_total} ảnh`; }
    else if (j.stage === 'evaluate' && j.eval_total) { pct = 100 * j.eval_done / j.eval_total; stage += `: ${j.eval_done}/${j.eval_total} ảnh`; }
    else if (!running && j.state === 'done') pct = 100;
    $('job-stage').textContent = running ? stage : (j.run_id ? `Lượt gần nhất ${j.run_id}: ${JOB[j.state]}` : 'Chưa chạy lượt nào');
    $('job-bar').style.width = pct + '%';
    $('job-msg').className = j.error ? 'err' : 'msg';
    $('job-msg').textContent = j.error || (j.reason ? 'Kết thúc: ' + j.reason : '')
      || (j.why && j.why.length ? 'Đề xuất: ' + j.why.join(' · ') : '');
  }

  async function refresh() {
    try {
      const s = await getJSON('/plant-hmi/realism/api/state');
      last = s;
      renderJob(s.job);
      renderIssues($('issues'), s.issues);
      renderHistory($('history'), $('trend'), s.history || []);
      window.RealismV2.renderV2Gate($('v2-gate'), s.history || []);
      if (!window.RealismKnobs.isEditing()) window.RealismKnobs.render($('knobs'), $('audit'), s.knobs, s.best, refresh);
      const latestResult = await result(s.latest_eval);
      renderDefectMetrics($('defect-metrics'), latestResult);
      renderResults($('results'), await result(s.baseline_eval), latestResult, true);
    } catch (e) { $('job-msg').className = 'err'; $('job-msg').textContent = 'Không đọc được trạng thái: ' + e.message; }
    window.dispatchEvent(new CustomEvent('realism-refresh'));  // đồng bộ nhịp 3s cho mục "Độ nhạy núm" (bước 4)
  }

  function schedule() { clearTimeout(timer); if (!document.hidden) timer = setTimeout(async () => { await refresh(); schedule(); }, 3000); }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); schedule(); } });

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Plant-HMI': '1' }, body: JSON.stringify(body || {}) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || ('lỗi ' + r.status));
    return d;
  }

  function params(action) {
    return { action, n_per_type: parseInt($('n-per-type').value, 10), max_iter: parseInt($('max-iter').value, 10),
      types: [...document.querySelectorAll('#types input:checked')].map(i => i.value) };
  }

  async function act(btn, fn) {
    if (btn.dataset.arm && armedBtn !== btn) {                        // bước 1: nhá, chờ bấm lại
      if (armedBtn) { armedBtn.classList.remove('armed'); armedBtn.textContent = armedBtn.dataset.label; }
      armedBtn = btn; btn.dataset.label = btn.dataset.label || btn.textContent;
      btn.classList.add('armed'); btn.textContent = btn.dataset.arm + ' Bấm lần nữa';
      clearTimeout(armTimer); armTimer = setTimeout(() => { btn.classList.remove('armed'); btn.textContent = btn.dataset.label; armedBtn = null; }, 6000);
      return;
    }
    clearTimeout(armTimer);
    if (armedBtn) { armedBtn.classList.remove('armed'); armedBtn.textContent = armedBtn.dataset.label; armedBtn = null; }
    try { await fn(); $('job-msg').className = 'msg'; $('job-msg').textContent = 'Đã gửi.'; }
    catch (e) { $('job-msg').className = 'err'; $('job-msg').textContent = e.message; }
    setTimeout(refresh, 800);
  }

  $('btn-evaluate').onclick = e => act(e.currentTarget, () => post('/plant-hmi/realism/api/run', params('evaluate')));
  $('btn-propose').onclick = e => act(e.currentTarget, () => post('/plant-hmi/realism/api/run', params('propose')));
  $('btn-cycle').onclick = e => act(e.currentTarget, () => post('/plant-hmi/realism/api/run', params('cycle')));
  $('btn-auto').onclick = e => act(e.currentTarget, () => post('/plant-hmi/realism/api/run', params('auto')));
  $('btn-stop').onclick = e => act(e.currentTarget, () => post('/plant-hmi/realism/api/stop'));
  refresh(); schedule();
})();
