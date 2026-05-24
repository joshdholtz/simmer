import { fetchInfo, fetchSims } from './api.js';
import { SimStream } from './stream.js';
import { SimTerminal } from './terminal.js';

// ── Icons ────────────────────────────────────────────────────────────────────
const IC = {
  rotate:   `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10a6.5 6.5 0 1 0 6.5-6.5H7"/><path d="M7 1.5v4H3"/></svg>`,
  home:     `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="7.5"/><rect x="6.5" y="6.5" width="7" height="7" rx="2.5"/></svg>`,
  sun:      `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="3.5"/><path d="M10 2.5v1.5M10 16v1.5M2.5 10H4M16 10h1.5M4.7 4.7l1 1M14.3 14.3l1 1M15.3 4.7l-1 1M5.7 14.3l-1 1"/></svg>`,
  moon:     `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3.5a6.5 6.5 0 0 0 0 13A7.5 7.5 0 0 1 10 3.5z"/></svg>`,
  terminal: `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7l4 3-4 3"/><path d="M11 13h5"/></svg>`,
  keyboard: `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="16" height="10" rx="2.5"/><path d="M5.5 10h.5M8.5 10H9M12 10h.5M15 10h.5M5.5 13H14.5"/></svg>`,
  refresh:  `<svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10a6.5 6.5 0 1 0 6.5-6.5H7"/><path d="M7 1.5v4H3"/></svg>`,
};

// ── State ────────────────────────────────────────────────────────────────────
let allSims = [];
let activeUdid = null;
let stream = null;
let terminal = null;
let terminalOpen = false;
let appearMode = 'dark';

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const deviceList     = $('device-list');
const modeBadge      = $('mode-badge');
const emptyState     = $('empty-state');
const viewportWrap   = $('viewport-wrap');
const deviceFrame    = $('device-frame');
const canvas         = $('screen');
const connectOverlay = $('connect-overlay');
const controlsPill   = $('controls-pill');
const termDrawer     = $('terminal-drawer');
const termEl         = $('term-el');
const kbdBar         = $('kbd-bar');
const kbdInput       = $('kbd-input');
const fpsSlider      = $('fps-slider');
const fpsVal         = $('fps-val');
const qualSlider     = $('qual-slider');
const qualVal        = $('qual-val');
const dsBtn          = $('ds-btn');
const projFilter     = $('proj-filter');
const projFilterWrap = $('proj-filter-wrap');

// ── Utility ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function simIcon(name) {
  const n = name.toLowerCase();
  if (n.includes('ipad')) return '⬛';
  if (n.includes('watch')) return '⌚';
  if (n.includes('tv')) return '📺';
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
    deviceList.innerHTML = `<div class="device-list-empty">${filterOn ? 'No project simulators' : 'No simulators running'}</div>`;
    return;
  }
  deviceList.innerHTML = sims.map(s => `
    <div class="device-item${s.id === activeUdid ? ' active' : ''}"
         data-udid="${esc(s.id)}" data-name="${esc(s.name)}" data-w="${s.width}" data-h="${s.height}">
      <span class="device-icon">${simIcon(s.name)}</span>
      <span class="device-info">
        <span class="device-name">${esc(s.name)}</span>
        <span class="device-dims">${s.width} × ${s.height}</span>
      </span>
      ${s.project_app ? '<span class="device-badge">★</span>' : ''}
    </div>`).join('');

  deviceList.querySelectorAll('.device-item').forEach(el => {
    el.addEventListener('click', () => {
      const { udid, name, w, h } = el.dataset;
      selectDevice(udid, name, parseInt(w), parseInt(h));
    });
  });
}

// ── Device selection ─────────────────────────────────────────────────────────
function selectDevice(udid, name, w, h) {
  if (udid === activeUdid) return;

  // Tear down existing stream
  stream?.destroy();
  stream = null;

  activeUdid = udid;
  renderDeviceList();

  // Set up canvas
  canvas.width  = Math.min(w, h);
  canvas.height = Math.max(w, h);
  showViewport();

  // Create stream
  stream = new SimStream(udid, canvas, {
    fps:     parseInt(fpsSlider.value),
    quality: parseInt(qualSlider.value),
    onStatus:     updateStatus,
    onFirstFrame: () => connectOverlay.classList.add('hidden'),
  });

  // Sync settings controls
  stream.updateSettings({ data_saver: dsBtn.classList.contains('active') });
}

function showViewport() {
  emptyState.classList.add('hidden');
  viewportWrap.classList.remove('hidden');
  connectOverlay.classList.remove('hidden');
  connectOverlay.innerHTML = '<div class="spinner"></div><span>Connecting…</span>';
  controlsPill.classList.remove('hidden');
}

function updateStatus(status) {
  const dot = $('status-dot');
  const span = connectOverlay.querySelector('span');
  if (!dot) return;

  dot.className = 'status-dot';
  if (status === 'connected' || status === 'streaming') {
    dot.classList.add('connected');
    if (status === 'streaming') connectOverlay.classList.add('hidden');
  } else if (status === 'reconnecting') {
    dot.classList.add('reconnecting');
    connectOverlay.classList.remove('hidden');
    if (span) span.textContent = 'Reconnecting…';
  } else if (status === 'no-frames') {
    connectOverlay.classList.remove('hidden');
    connectOverlay.innerHTML = `<span>No frames received.<br>Grant Screen Recording or run with <code>--mode compat</code>.</span>`;
  } else {
    connectOverlay.classList.remove('hidden');
    if (span) span.textContent = 'Connecting…';
  }
}

// ── Controls ─────────────────────────────────────────────────────────────────
$('btn-rotate').addEventListener('click', () => stream?.send({ type: 'rotate' }));
$('btn-home').addEventListener('click',   () => stream?.send({ type: 'home' }));

$('btn-appear').addEventListener('click', () => {
  appearMode = appearMode === 'dark' ? 'light' : 'dark';
  const btn = $('btn-appear');
  btn.innerHTML = appearMode === 'dark' ? IC.moon : IC.sun;
  btn.title = appearMode === 'dark' ? 'Switch to light' : 'Switch to dark';
  stream?.send({ type: 'appearance', mode: appearMode });
});

$('btn-kbd').addEventListener('click', () => {
  const open = kbdBar.classList.toggle('visible');
  $('btn-kbd').classList.toggle('active', open);
  if (open) {
    kbdBar.classList.toggle('above-terminal', terminalOpen);
    kbdInput.focus();
  }
});

$('btn-terminal').addEventListener('click', () => toggleTerminal());

// ── Terminal drawer ───────────────────────────────────────────────────────────
function toggleTerminal(forceOpen) {
  const shouldOpen = forceOpen ?? !terminalOpen;
  terminalOpen = shouldOpen;
  termDrawer.classList.toggle('open', shouldOpen);
  $('btn-terminal').classList.toggle('active', shouldOpen);

  if (kbdBar.classList.contains('visible')) {
    kbdBar.classList.toggle('above-terminal', shouldOpen);
  }

  if (shouldOpen && !terminal) {
    terminal = new SimTerminal(termEl, {
      onStatus: s => {
        const dot = $('term-status-dot');
        if (!dot) return;
        dot.className = 'status-dot';
        if (s === 'connected') dot.classList.add('connected');
        else if (s === 'reconnecting') dot.classList.add('reconnecting');
      },
    });
  }

  if (shouldOpen) {
    requestAnimationFrame(() => terminal?.fit());
  }
}

$('btn-close-term').addEventListener('click', () => toggleTerminal(false));

// Refit terminal when drawer finishes animating open
termDrawer.addEventListener('transitionend', () => {
  if (terminalOpen) terminal?.fit();
});

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

// ── Keyboard bar ─────────────────────────────────────────────────────────────
function sendKbdText() {
  const t = kbdInput.value;
  if (!t) return;
  stream?.send({ type: 'text', text: t });
  kbdInput.value = '';
  kbdInput.focus();
}

kbdInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendKbdText(); } });
$('kbd-send').addEventListener('click', sendKbdText);
$('kbd-bs').addEventListener('click',   () => stream?.send({ type: 'key', key: 'backspace' }));
$('kbd-ret').addEventListener('click',  () => stream?.send({ type: 'key', key: 'return' }));

// ── Resize observer — refit terminal when drawer size changes ─────────────────
new ResizeObserver(() => { if (terminalOpen) terminal?.fit(); }).observe(termDrawer);

// ── Boot ─────────────────────────────────────────────────────────────────────
$('btn-refresh').addEventListener('click', loadSims);

// Check URL param for direct-link to a simulator
const urlUdid = new URLSearchParams(location.search).get('view');

loadSims().then(() => {
  if (urlUdid) {
    const sim = allSims.find(s => s.id === urlUdid);
    if (sim) selectDevice(sim.id, sim.name, sim.width, sim.height);
  }
});
