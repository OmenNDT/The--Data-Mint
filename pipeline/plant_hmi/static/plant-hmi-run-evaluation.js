// "Đánh giá độ thật" for one run folder: starts the realism evaluator on the server, polls
// until it finishes, then shows per defect the C2ST and the six criteria real vs synthetic.
// AUC 0.5 on a criterion = real and synthetic indistinguishable; C2ST near 0.5 = good.
import { h, fmtTime } from './plant-hmi-setpoint-dom.js';

const TIP = 'So ảnh của lần chạy này với lỗi thật RIAWELC theo 6 tiêu chí hình dạng và biên, '
  + 'kèm C2ST (0,5 = không phân biệt được thật/sinh; gần 1 = dễ nhận ra là ảnh sinh). '
  + 'Chỉ đo được crack, porosity, lack of penetration, clustered/linear porosity, lack of fusion.';
const fmt = (v, d = 3) => (v === null || v === undefined ? '—'
  : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d }));

function c2stText(v) {
  if (v === null || v === undefined) return '—';
  const tag = v <= 0.6 ? 'khó phân biệt (tốt)' : v <= 0.75 ? 'phân biệt được một phần' : 'dễ nhận ra là ảnh sinh';
  return `${fmt(v)} · ${tag}`;
}

const NEW_TIP = 'Thước mới: 16 đặc trưng khuyết tật (hình dạng vùng + biên), so ảnh sinh với chính lỗi thật '
  + 'W0003 (×1, cùng tỉ lệ). "Hoàn hảo" là mức khi so ảnh thật với ảnh thật (chia đôi tập), đặt cạnh số đo '
  + 'thật/sinh để biết còn cách bao xa.';

function kidText(k) {
  if (!k) return '—';
  return `${fmt(k.value)} [${fmt(k.ci_low)}, ${fmt(k.ci_high)}]`;
}

function newRulerRow(e) {
  if (e.reference === null || e.reference === undefined) {
    return h('div', { class: 'ev-pair' },
      h('div', { class: 'ev-head' }, `${e.defect_type} · chưa có tham chiếu W0003, chỉ đo tách vùng ảnh sinh`),
      h('div', { class: 'ev-note' }, `Tách vùng sinh ${fmt(e.detection_rate_syn, 2)} (n=${e.n_syn})`));
  }
  const p = e.perfect || {};
  const warn = e.small_reference ? ' · tham chiếu ít mẫu, chỉ báo' : '';
  return h('div', { class: 'ev-pair' },
    h('div', { class: 'ev-head' }, `${e.defect_type} ↔ W0003/${e.reference} · n thật/sinh ${e.n_real}/${e.n_syn}${warn}`),
    h('div', { class: 'ev-grid' },
      h('span', { class: 'ev-th' }, 'Độ đo'), h('span', { class: 'ev-th' }, 'Thật'),
      h('span', { class: 'ev-th' }, 'Sinh'), h('span', { class: 'ev-th' }, 'Hoàn hảo'), h('span', { class: 'ev-th' }, ''),
      h('span', {}, 'Tách được vùng'), h('span', { class: 'ev-num' }, fmt(e.detection_rate_real, 2)),
      h('span', { class: 'ev-num' }, fmt(e.detection_rate_syn, 2)), h('span', { class: 'ev-num' }, '—'), h('span', {}, ''),
      h('span', {}, 'C2ST'), h('span', { class: 'ev-num' }, '—'),
      h('span', { class: 'ev-num' }, e.c2st_reason ? `— (${e.c2st_reason})` : fmt(e.c2st)),
      h('span', { class: 'ev-num' }, fmt(p.c2st)), h('span', {}, ''),
      h('span', {}, 'KID [CI]'), h('span', { class: 'ev-num' }, '—'),
      h('span', { class: 'ev-num' }, kidText(e.kid)), h('span', { class: 'ev-num' }, fmt(p.kid)), h('span', {}, ''),
      h('span', {}, 'Density'), h('span', { class: 'ev-num' }, '—'),
      h('span', { class: 'ev-num' }, fmt((e.density_coverage || {}).density)), h('span', { class: 'ev-num' }, fmt(p.density)), h('span', {}, ''),
      h('span', {}, 'Coverage'), h('span', { class: 'ev-num' }, '—'),
      h('span', { class: 'ev-num' }, fmt((e.density_coverage || {}).coverage)), h('span', { class: 'ev-num' }, fmt(p.coverage)), h('span', {}, '')));
}

function newRulerBlock(dm) {
  if (!dm || !dm.types || !dm.types.length) {
    return h('div', { class: 'ev-note' }, dm && dm.error ? `Thước mới lỗi: ${dm.error}` : 'Thước mới chưa có kết quả');
  }
  return h('div', { class: 'ev-section', title: NEW_TIP },
    h('div', { class: 'ev-section-head' }, 'Thước mới (16 đặc trưng khuyết tật, so W0003 thật)'),
    ...dm.types.map(newRulerRow));
}

function pairTable(p) {
  return h('div', { class: 'ev-pair' },
    h('div', { class: 'ev-head' }, `${p.pair} · dùng ${p.n_used}/${p.n_syn} ảnh · C2ST ${c2stText(p.c2st)}`),
    h('div', { class: 'ev-grid' },
      h('span', { class: 'ev-th' }, 'Tiêu chí'), h('span', { class: 'ev-th' }, 'Thật'),
      h('span', { class: 'ev-th' }, 'Sinh'), h('span', { class: 'ev-th' }, 'AUC'), h('span', { class: 'ev-th' }, ''),
      ...p.criteria.flatMap((c) => [
        h('span', {}, c.label), h('span', { class: 'ev-num' }, fmt(c.real)), h('span', { class: 'ev-num' }, fmt(c.syn)),
        h('span', { class: 'ev-num' }, fmt(c.auc, 2)),
        h('span', { class: `ev-verdict ${c.verdict === 'khác rõ' ? 'bad' : c.verdict === 'hơi lệch' ? 'warn' : 'ok'}` }, c.verdict),
      ])));
}

export function evaluationBlock(run, call, say) {
  const panel = h('div', { class: 'ev-panel', hidden: '' });
  let timer = null;

  function render(st) {
    if (st.state === 'running') { panel.replaceChildren(h('div', { class: 'ev-note' }, 'Đang đánh giá…')); return; }
    if (st.state === 'error') { panel.replaceChildren(h('div', { class: 'ev-note bad' }, `Lỗi: ${st.error}`)); return; }
    if (st.state === 'none') { panel.replaceChildren(h('div', { class: 'ev-note' }, 'Chưa đánh giá lần chạy này')); return; }
    panel.replaceChildren(
      h('div', { class: 'ev-note' }, `Kết quả ${fmtTime(st.finished)} · `,
        h('a', { href: '/plant-hmi/realism/', target: '_blank', rel: 'noopener' }, 'xem trên trang Độ thật')),
      newRulerBlock(st.defect_metrics),
      h('details', { class: 'ev-old' },
        h('summary', {}, 'Thước cũ (6 đặc trưng, so RIAWELC, xuyên miền), không dùng để quyết định'),
        ...(st.pairs.length ? st.pairs.map(pairTable)
          : [h('div', { class: 'ev-note' }, 'Lần chạy không có loại lỗi nào có ảnh thật để đối chiếu')])));
  }

  async function poll() {
    try {
      const st = await call(`/evaluate?name=${encodeURIComponent(run.name)}`);
      render(st);
      timer = st.state === 'running' ? setTimeout(poll, 2000) : null;
    } catch (e) { say(`Không đọc được kết quả đánh giá: ${e.message}`, true); }
  }

  const button = h('button', { class: 'ot-mini', title: TIP,
    onclick: async () => {
      panel.hidden = false;
      try {
        await call('/evaluate', { name: run.name });
        render({ state: 'running' });
        clearTimeout(timer); timer = setTimeout(poll, 1500);
      } catch (e) { say(`Không chạy được đánh giá: ${e.message}`, true); }
    } }, 'Đánh giá độ thật');

  // show the newest finished result (if any) right away when the list opens
  call(`/evaluate?name=${encodeURIComponent(run.name)}`).then((st) => {
    if (st.state !== 'none') { panel.hidden = false; render(st); if (st.state === 'running') timer = setTimeout(poll, 2000); }
  }).catch(() => {});
  return { button, panel };
}
