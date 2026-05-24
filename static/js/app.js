import { fetchInfo, fetchSims } from './api.js';
import { SimStream } from './stream.js';
import { SimTerminal } from './terminal.js';

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const deviceList     = $('device-list');
const modeBadge      = $('mode-badge');
const emptyState     = $('empty-state');
const viewportWrap   = $('viewport-wrap');
const canvas         = $('screen');
const connectOverlay = $('connect-overlay');
const controlsPill   = $('controls-pill');
const content        = $('content');
const termPanel      = $('terminal-panel');
const termPanes      = $('term-panes');
const termTabsBar    = $('term-tabs-bar');
const kbdBar         = $('kbd-bar');
const kbdInput       = $('kbd-input');
const fpsSlider      = $('fps-slider');
const fpsVal         = $('fps-val');
const qualSlider     = $('qual-slider');
const qualVal        = $('qual-val');
const dsBtn          = $('ds-btn');
const projFilter     = $('proj-filter');
const projFilterWrap = $('proj-filter-wrap');

// ── State ────────────────────────────────────────────────────────────────────
let allSims = [];
let activeUdid = null;
let stream = null;
let appearMode = 'dark';

// Terminal tabs: [{id, label, terminal, el}]
let termTabs = [];
let activeTermTabId = null;
let termOpen = false;
let termPinned = false; // true = right side, false = bottom

// ── Utility ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function simIcon(name) {
  const n = name.toLowerCase();
  if (n.includes('ipad'))   return '⬛';
  if (n.includes('watch'))  return '⌚';
  if (n.includes('tv'))     return '📺';
  if (n.includes('vision')) return '🥽';
  return '📱';
}

// ── Device list ──────────────────────────────────────────────────────────────
async function loadSims() {
  deviceList.innerHTML = '<div class="device-list-empty">Scanning…</div>';
  try {
    const [sims, info] = await Promise.all([fetchSims(), fetchInfo()]);
    allSims = sims;

    if (info.mode) {
      const fast = info.mode.startsWith('fast');
      modeBadge.textContent = fast ? 'fast' : 'compat';
      modeBadge.className = 'mode-badge ' + (fast ? 'fast' : 'compat');
    }

    if (info.bundle_id) {
      projFilterWrap.classList.add('visible');
      projFilterWrap.querySelector('span').textContent =
        info.bundle_id.split('.').pop() + ' only';
    } else {
      projFilterWrap.classList.remove('visible');
    }

    renderDeviceList();
  } catch {
    deviceList.innerHTML = '<div class="device-list-empty">Could not reach server</div>';
  }
}

function renderDeviceList() {
  const filterOn = projFilter.checked;
  const sims = filterOn ? allSims.filter(s => s.project_app) : allSims;
  if (!sims.length) {
    deviceList.innerHTML = `<div class="device-list-empty">${
      filterOn ? 'No project simulators' : 'No simulators running'
    }</div>`;
    return;
  }
  deviceList.innerHTML = sims.map(s => `
    <div class="device-item${s.id === activeUdid ? ' active' : ''}"
         data-udid="${esc(s.id)}" data-name="${esc(s.name)}"
         data-w="${s.width}" data-h="${s.height}">
      <span class="device-icon">${simIcon(s.name)}</span>
      <span class="device-info">
        <span class="device-name">${esc(s.name)}</span>
        <span class="device-dims">${s.width} × ${s.height}</span>
      </span>
      ${s.project_app ? '<span class="device-badge">★</span>' : ''}
    </div>`).join('');

  deviceList.querySelectorAll('.device-item').forEach(el => {
    el.addEventListener('click', () =>
      selectDevice(el.dataset.udid, el.dataset.name,
                   parseInt(el.dataset.w), parseInt(el.dataset.h)));
  });
}

// ── Simulator selection ───────────────────────────────────────────────────────
function selectDevice(udid, name, w, h) {
  if (udid === activeUdid) return;
  stream?.destroy();
  stream = null;
  activeUdid = udid;
  renderDeviceList();

  canvas.width  = Math.min(w, h);
  canvas.height = Math.max(w, h);

  emptyState.classList.add('hidden');
  viewportWrap.classList.remove('hidden');
  connectOverlay.classList.remove('hidden');
  connectOverlay.innerHTML = '<div class="spinner"></div><span>Connecting…</span>';
  controlsPill.classList.remove('hidden');

  stream = new SimStream(udid, canvas, {
    fps:     parseInt(fpsSlider.value),
    quality: parseInt(qualSlider.value),
    onStatus: updateStatus,
    onFirstFrame: () => connectOverlay.classList.add('hidden'),
  });
  stream.updateSettings({ data_saver: dsBtn.classList.contains('active') });
}

function updateStatus(status) {
  const dot = $('status-dot');
  if (!dot) return;
  dot.className = 'status-dot';
  const span = connectOverlay.querySelector('span');
  if (status === 'streaming') {
    dot.classList.add('connected');
  } else if (status === 'connected') {
    dot.classList.add('connected');
  } else if (status === 'reconnecting') {
    dot.classList.add('reconnecting');
    connectOverlay.classList.remove('hidden');
    if (span) span.textContent = 'Reconnecting…';
  } else if (status === 'no-frames') {
    connectOverlay.classList.remove('hidden');
    connectOverlay.innerHTML =
      `<span>No frames received.<br>Grant Screen Recording or run with <code>--mode compat</code>.</span>`;
  } else {
    connectOverlay.classList.remove('hidden');
    if (span) span.textContent = 'Connecting…';
  }
}

// ── Settings ─────────────────────────────────────────────────────────────────
fpsSlider.addEventListener('input', () => {
  fpsVal.textContent = fpsSlider.value;
  stream?.updateSettings({ fps: parseInt(fpsSlider.value) });
});
qualSlider.addEventListener('input', () => {
  qualVal.textContent = qualSlider.value;
  stream?.updateSettings({ quality: parseInt(qualSlider.value) });
});
dsBtn.addEventListener('click', () => {
  const on = dsBtn.classList.toggle('active');
  dsBtn.textContent = on ? 'Data Saver: On' : 'Data Saver';
  stream?.updateSettings({ data_saver: on });
});
projFilter.addEventListener('change', renderDeviceList);
$('btn-refresh').addEventListener('click', loadSims);

// ── Sim controls ──────────────────────────────────────────────────────────────
$('btn-rotate').addEventListener('click', () => stream?.send({ type: 'rotate' }));
$('btn-home').addEventListener('click',   () => stream?.send({ type: 'home' }));
$('btn-appear').addEventListener('click', () => {
  appearMode = appearMode === 'dark' ? 'light' : 'dark';
  const btn = $('btn-appear');
  if (appearMode === 'light') {
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="3.5"/><path d="M10 2.5v1.5M10 16v1.5M2.5 10H4M16 10h1.5M4.7 4.7l1 1M14.3 14.3l1 1M15.3 4.7l-1 1M5.7 14.3l-1 1"/></svg>`;
    btn.title = 'Switch to dark';
  } else {
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3.5a6.5 6.5 0 0 0 0 13A7.5 7.5 0 0 1 10 3.5z"/></svg>`;
    btn.title = 'Switch to light';
  }
  stream?.send({ type: 'appearance', mode: appearMode });
});

// ── Keyboard bar ──────────────────────────────────────────────────────────────
$('btn-kbd').addEventListener('click', () => {
  const open = kbdBar.classList.toggle('visible');
  $('btn-kbd').classList.toggle('active', open);
  if (open) kbdInput.focus();
});
function sendKbdText() {
  const t = kbdInput.value; if (!t) return;
  stream?.send({ type: 'text', text: t });
  kbdInput.value = ''; kbdInput.focus();
}
kbdInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendKbdText(); } });
$('kbd-send').addEventListener('click', sendKbdText);
$('kbd-bs').addEventListener('click',   () => stream?.send({ type: 'key', key: 'backspace' }));
$('kbd-ret').addEventListener('click',  () => stream?.send({ type: 'key', key: 'return' }));

// ── Terminal tabs ─────────────────────────────────────────────────────────────
function renderTermTabs() {
  termTabsBar.innerHTML = termTabs.map(t => `
    <div class="term-tab${t.id === activeTermTabId ? ' active' : ''}" data-id="${esc(t.id)}">
      <span>${esc(t.label)}</span>
      ${termTabs.length > 1 ? `<button class="term-tab-close" data-id="${esc(t.id)}">×</button>` : ''}
    </div>`).join('');

  termTabsBar.querySelectorAll('.term-tab').forEach(el => {
    el.addEventListener('click', e => {
      if (!e.target.classList.contains('term-tab-close')) activateTermTab(el.dataset.id);
    });
  });
  termTabsBar.querySelectorAll('.term-tab-close').forEach(el => {
    el.addEventListener('click', e => { e.stopPropagation(); closeTermTab(el.dataset.id); });
  });
}

function activateTermTab(id) {
  activeTermTabId = id;
  termTabs.forEach(t => t.el.classList.toggle('active', t.id === id));
  renderTermTabs();
  requestAnimationFrame(() => {
    termTabs.find(t => t.id === id)?.terminal.fit();
  });
}

function addTermTab() {
  const id = 'term-' + Date.now();
  const n = termTabs.length + 1;
  const label = n === 1 ? 'Terminal' : `Terminal ${n}`;

  const el = document.createElement('div');
  el.className = 'term-pane';
  termPanes.appendChild(el);

  const terminal = new SimTerminal(el, {
    onStatus: s => {
      // Only show status for the active tab
      if (id !== activeTermTabId) return;
      const dot = $('term-status-dot');
      if (!dot) return;
      dot.className = 'status-dot';
      if (s === 'connected') dot.classList.add('connected');
      else if (s === 'reconnecting') dot.classList.add('reconnecting');
    },
  });

  termTabs.push({ id, label, terminal, el });
  activateTermTab(id);
  renderTermTabs();
}

function closeTermTab(id) {
  const idx = termTabs.findIndex(t => t.id === id);
  if (idx === -1) return;
  termTabs[idx].terminal.destroy();
  termTabs[idx].el.remove();
  termTabs.splice(idx, 1);

  if (!termTabs.length) {
    setTermOpen(false);
    return;
  }
  if (activeTermTabId === id) {
    activateTermTab(termTabs[Math.max(0, idx - 1)].id);
  }
  renderTermTabs();
}

// ── Terminal open/close/pin ───────────────────────────────────────────────────
function setTermOpen(open) {
  termOpen = open;
  $('btn-terminal').classList.toggle('active', open);

  termPanel.classList.add('animating');
  termPanel.classList.toggle('closed', !open);
  termPanel.addEventListener('transitionend', () => {
    termPanel.classList.remove('animating');
    if (open) termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
  }, { once: true });

  if (open && !termTabs.length) addTermTab();
}

$('btn-terminal').addEventListener('click', () => setTermOpen(!termOpen));
$('btn-close-term').addEventListener('click', () => setTermOpen(false));
$('btn-add-term').addEventListener('click', addTermTab);

$('btn-pin-term').addEventListener('click', () => {
  termPinned = !termPinned;
  content.classList.toggle('pinned-right', termPinned);
  $('btn-pin-term').classList.toggle('active', termPinned);

  // Reset any drag-set inline size so CSS takes over
  if (termPinned) {
    termPanel.style.height = '';
  } else {
    termPanel.style.width = '';
    termPanel.style.height = '300px';
  }

  requestAnimationFrame(() => {
    termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
  });
});

// ── Resize (drag handle) ──────────────────────────────────────────────────────
(function initResize() {
  const handle = $('term-resize-handle');
  let startPos, startSize;

  handle.addEventListener('pointerdown', e => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);

    if (termPinned) {
      startPos = e.clientX;
      startSize = termPanel.getBoundingClientRect().width;
    } else {
      startPos = e.clientY;
      startSize = termPanel.getBoundingClientRect().height;
    }

    handle.addEventListener('pointermove', onMove);
    handle.addEventListener('pointerup', () => {
      handle.removeEventListener('pointermove', onMove);
      termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
    }, { once: true });
  });

  function onMove(e) {
    if (termPinned) {
      // Dragging left = wider terminal
      const delta = startPos - e.clientX;
      const w = Math.max(180, Math.min(window.innerWidth * 0.6, startSize + delta));
      termPanel.style.width = w + 'px';
    } else {
      // Dragging up = taller terminal
      const delta = startPos - e.clientY;
      const h = Math.max(80, Math.min(window.innerHeight * 0.75, startSize + delta));
      termPanel.style.height = h + 'px';
    }
    termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
  }
})();

// Refit on window resize
new ResizeObserver(() => {
  termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
}).observe(termPanel);

// ── Boot ─────────────────────────────────────────────────────────────────────
const urlUdid = new URLSearchParams(location.search).get('view');
loadSims().then(() => {
  if (urlUdid) {
    const sim = allSims.find(s => s.id === urlUdid);
    if (sim) selectDevice(sim.id, sim.name, sim.width, sim.height);
  }
});
