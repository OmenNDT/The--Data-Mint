// Particle layer: one particle = one image job, moved by real telemetry (live) or driven by
// the replay clock (historian playback). Enter/exit records give each job a list of residencies
// (R-201 mask, P-601 ComfyUI, R-401 post); consecutive calls at the same unit merge into one
// residency. The particle travels into a unit during the first moments of its residency, glows
// while resident, then leaves to TK-801 (ok) or D-901 (failed).
import { anchor } from './plant-hmi-pid-diagram.js';

const NS = 'http://www.w3.org/2000/svg';
export const DISPLAY_LAG_S = 4;
const TRAVEL_S = 1.2;
const STALE_S = 330;   // drop a job with no outcome after this long, even if its pid is alive
const GHOST_S = 10;    // drop sooner once we know its pid died (live mode only)

const jobs = new Map();       // key run:job -> {segs:[{tag,t0,t1,err,call}], outcome, outcomeTs, defect, pid, retried}
let layer = null;
let mode = 'live';             // 'live': self-driven rAF loop; 'replay': caller drives renderAt(T)
let clockOffset = 0;           // server - client seconds (live only)
let alivePids = new Set();
let hasAlive = false;          // becomes true only after the first setAlivePids() call
let rafId = null;
let timeoutId = null;

export function initParticles(svg) {
  layer = document.createElementNS(NS, 'g');
  layer.setAttribute('aria-hidden', 'true');
  svg.appendChild(layer);
}

// Live mode only: called exclusively from the /api/events poller (never from /api/snapshot),
// so the clock offset always reflects the same feed the particles are drawn from.
export function setServerTime(serverTs) {
  clockOffset = serverTs - Date.now() / 1000;
}

export function setAlivePids(pids) {
  alivePids = new Set(pids);
  hasAlive = true;
}

// Switches between the live self-driven loop and replay (caller calls renderAt each frame).
export function setMode(next) {
  mode = next;
  stopLoop();
}

// Clears all tracked jobs and pid state; used on Live<->Replay switch and run change.
export function reset() {
  jobs.clear();
  alivePids = new Set();
  hasAlive = false;
  stopLoop();
  if (layer) layer.replaceChildren();
}

function stopLoop() {
  if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
  if (timeoutId !== null) { clearTimeout(timeoutId); timeoutId = null; }
}

export function ingest(events) {
  for (const ev of events) {
    if (ev.job === null || ev.job === undefined) continue;   // non-job records never draw (R5)
    const key = `${ev.run}:${ev.job}`;
    const job = jobs.get(key) || { segs: [], outcome: null, defect: ev.defect, pid: ev.pid, retried: false };
    job.lastTs = ev.ts;
    jobs.set(key, job);
    if (ev.kind === 'enter') {
      if (ev.tag === 'U-901') continue;                       // thermal hold: not a unit on the line
      const last = job.segs[job.segs.length - 1];
      if (last && last.tag === ev.tag) {
        last.t1 = null; last.call = ev.call;
        if (job.retried) last.err = false;                    // successful retry: particle turns teal again
      } else {
        job.segs.push({ tag: ev.tag, t0: ev.ts, t1: null, err: false, call: ev.call });
      }
      job.retried = false;
    } else if (ev.kind === 'exit') {
      const seg = job.segs.find((s) => s.call === ev.call);
      if (seg) {
        seg.t1 = ev.ts;
        if (!ev.ok) { seg.err = true; seg.errTs = ev.ts; }   // colour applies from the failing record on
      }
    } else if (ev.kind === 'job') {
      if (ev.outcome === 'retry') {
        const last = job.segs[job.segs.length - 1];
        if (last) { last.err = true; last.errTs = ev.ts; }
        job.retried = true;
      } else { job.outcome = ev.outcome; job.outcomeTs = ev.ts; }
    }
  }
  if (jobs.size && mode === 'live') startLiveLoop();
}

function lerp(a, b, p) {
  // orthogonal route: horizontal first, then vertical
  const [ax, ay] = a, [bx, by] = b;
  const h = Math.abs(bx - ax), v = Math.abs(by - ay), d = (h + v) * Math.min(1, Math.max(0, p));
  return d <= h ? [ax + Math.sign(bx - ax) * d, ay] : [bx, ay + Math.sign(by - ay) * (d - h)];
}

// Position of a job at display time T, or null when not on screen.
function place(job, T) {
  const segs = job.segs;
  if (!segs.length || T < segs[0].t0) return null;
  let i = segs.length - 1;
  while (i > 0 && segs[i].t0 > T) i -= 1;
  const seg = segs[i];
  const prevTag = i === 0 ? 'TK-102' : segs[i - 1].tag;
  const inside = seg.t1 === null ? T - seg.t0 : Math.min(T, seg.t1) - seg.t0;
  const travel = seg.t1 === null ? TRAVEL_S : Math.min(TRAVEL_S, (seg.t1 - seg.t0) / 2);
  if (i === segs.length - 1 && job.outcome && T >= job.outcomeTs) {
    const p = (T - job.outcomeTs) / TRAVEL_S;
    if (p >= 1) return 'done';
    return { xy: lerp(anchor(seg.tag), anchor(job.outcome === 'ok' ? 'TK-801' : 'D-901'), p),
      err: job.outcome !== 'ok', moving: true };
  }
  if (inside < travel && prevTag !== seg.tag) {
    return { xy: lerp(anchor(prevTag), anchor(seg.tag), inside / travel), err: false, moving: true };
  }
  // err colour only from the moment the failing exit/retry record landed, not from segment start
  const errActive = seg.err && T >= (seg.errTs ?? seg.t0);
  return { xy: anchor(seg.tag), err: errActive, moving: false };
}

// Renders one frame at display time T. `serverNow` drives staleness/ghost checks; in live mode
// it trails T by DISPLAY_LAG_S, in replay it equals T (no lag applied to historian playback).
// In replay, finished/stale jobs are never deleted (only skipped this frame) so seeking
// backwards or replaying past the end still shows them at the right position (H1).
export function renderAt(T, serverNow = T) {
  if (!layer) return;
  const dots = [];
  for (const [key, job] of jobs) {
    const noOutcome = !job.outcome;
    const stale = noOutcome && serverNow - job.lastTs > STALE_S;
    const ghost = hasAlive && noOutcome && !alivePids.has(job.pid) && serverNow - job.lastTs > GHOST_S;
    const pos = (stale || ghost) ? 'done' : place(job, T);
    const finished = pos === 'done' || (job.outcome && T - job.outcomeTs > 60);
    if (finished) {
      if (mode === 'live') jobs.delete(key);
      continue;
    }
    if (pos) dots.push([key, job, pos]);
  }
  layer.replaceChildren(...dots.map(([key, job, pos]) => {
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', pos.xy[0]);
    c.setAttribute('cy', pos.xy[1]);
    c.setAttribute('r', pos.moving ? 6 : 8);
    c.setAttribute('class', `particle${pos.err ? ' err' : ''}${pos.moving ? '' : ' resident'}`);
    const title = document.createElementNS(NS, 'title');
    title.textContent = `job ${key.split(':')[1]} · ${job.defect || ''}`;
    c.appendChild(title);
    return c;
  }));
}

function liveFrame() {
  timeoutId = null;
  const T = Date.now() / 1000 + clockOffset - DISPLAY_LAG_S;
  renderAt(T, T + DISPLAY_LAG_S);
  if (jobs.size && mode === 'live') timeoutId = setTimeout(() => { rafId = requestAnimationFrame(liveFrame); }, 33);
}

function startLiveLoop() {
  if (rafId === null && timeoutId === null && layer) rafId = requestAnimationFrame(liveFrame);
}
