// Regression check for rule C1: a previous local `h()` in plant-hmi-alarm-list.js did
// `node.setAttribute('onclick', fn)`, which stringifies the handler into a dead inline
// attribute - every button looked right but did nothing when clicked. There is no JS test
// harness in this repo (no jsdom in node_modules), so this script provides the minimal DOM
// shim needed to load the real module unmodified and prove a click actually invokes the
// API call (`fetch`), not just that the button exists.
//
// Run: node tests/js/check-alarm-list-buttons.mjs

import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const staticDir = path.join(here, '..', '..', 'plant_hmi', 'static');

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.attributes = {};
    this.style = {};
    this._listeners = {};
    this.children = [];
    this.parentNode = null;
    this._text = '';
    this._classes = new Set();
    this.classList = {
      add: (c) => this._classes.add(c),
      remove: (c) => this._classes.delete(c),
      toggle: (c, on) => { if (on) this._classes.add(c); else this._classes.delete(c); },
      contains: (c) => this._classes.has(c),
    };
  }

  setAttribute(k, v) {
    this.attributes[k] = v;
    if (k === 'class') this._classes = new Set(String(v).split(/\s+/).filter(Boolean));
  }

  getAttribute(k) { return this.attributes[k]; }
  addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); }
  removeEventListener() {}

  append(...nodes) {
    for (const n of nodes.flat()) {
      if (n === null || n === undefined) continue;
      if (typeof n === 'string') { this._text += n; continue; }
      this.children.push(n);
      n.parentNode = this;
    }
  }

  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }

  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() {
    return this._text + this.children.map((c) => c.textContent || '').join('');
  }

  contains(node) {
    if (!node) return false;
    if (node === this) return true;
    return this.children.some((c) => c.contains(node));
  }

  // Simulates a real click: invokes every registered 'click' listener, as a browser would.
  click() { (this._listeners.click || []).forEach((fn) => fn({ target: this })); }

  querySelectorAll() { return []; }

  // Depth-first search by exact textContent match, used by the test to find a button.
  findByText(text) {
    if (this.textContent === text && this.tagName === 'BUTTON') return this;
    for (const c of this.children) {
      const found = c.findByText && c.findByText(text);
      if (found) return found;
    }
    return null;
  }
}

global.document = {
  createElement: (tag) => new FakeElement(tag),
  activeElement: null,
  getElementById: () => null,
};

const fetchCalls = [];
global.fetch = async (url, opts) => {
  fetchCalls.push({ url, opts, body: opts && opts.body ? JSON.parse(opts.body) : null });
  return { ok: true, json: async () => ({ acked_at: 123 }) };
};

const { renderAlarmList } = await import(path.join(staticDir, 'plant-hmi-alarm-list.js'));

function makeSnapshot() {
  return {
    ts: 1000,
    alarms: [{
      code: 'COMFY_DOWN', tag: 'U-902', severity: 'HI', pid: null, since: 900, message: 'down',
      key: 'COMFY_DOWN|U-902|None|900', point_key: 'COMFY_DOWN|U-902|None', acked: false, acked_at: null, shelved: false,
    }],
    alarms_cleared_unacked: [],
    alarms_shelved: [],
  };
}

async function main() {
  const container = new FakeElement('div');
  let refreshed = false;
  await renderAlarmList(container, makeSnapshot(), async () => { refreshed = true; });

  const ackBtn = container.findByText('Xác nhận');
  assert.ok(ackBtn, 'expected an "Xác nhận" button to be rendered for the active alarm');

  ackBtn.click();
  await new Promise((r) => setTimeout(r, 0)); // let the async onclick handler's microtasks settle

  assert.equal(fetchCalls.length, 1, 'clicking "Xác nhận" must call fetch exactly once (rule C1 regression)');
  assert.ok(fetchCalls[0].url.endsWith('/ack'), `expected a call to /ack, got ${fetchCalls[0].url}`);
  assert.equal(fetchCalls[0].body.key, 'COMFY_DOWN|U-902|None|900', 'must ack the occurrence key, not the point key');
  assert.ok(refreshed, 'the onChanged callback must run after a successful ack');

  // Tạm tắt must target the POINT key (rule H5), not the occurrence key.
  const container2 = new FakeElement('div');
  await renderAlarmList(container2, makeSnapshot(), async () => {});
  const shelveBtn = container2.findByText('Tạm tắt');
  assert.ok(shelveBtn, 'expected a "Tạm tắt" button');
  shelveBtn.click(); // -> shelve-pick
  const continueBtn = container2.findByText('Tiếp tục');
  assert.ok(continueBtn, 'expected a "Tiếp tục" button after choosing Tạm tắt');

  console.log('check-alarm-list-buttons: all assertions passed');
}

main().catch((err) => { console.error(err); process.exit(1); });
