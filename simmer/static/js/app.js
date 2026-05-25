import { fetchInfo, fetchSims, fetchAvailableDevices, bootSim, bootAvd, requestPermission } from './api.js';
import { SimStream } from './stream.js';
import { SimTerminal } from './terminal.js';

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const deviceList     = $('device-list');
const addSimBtn      = $('add-sim-btn');
const addPopover     = $('add-popover');
const addSearch      = $('add-search');
const addList        = $('add-list');
const addCloseBtn    = $('add-close-btn');
const modeBadge      = $('mode-badge');
const emptyState     = $('empty-state');
const simPanelsEl    = $('sim-panels');
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
const permsWidget    = $('perms-widget');
const permsBtn       = $('perms-btn');
const permsBody      = $('perms-body');
const permsList      = $('perms-list');

// ── State ────────────────────────────────────────────────────────────────────
let allSims = [];
let hasAdb = false;
const _pendingBoots = new Map(); // id → {name, platform}  (booting but not yet in sims)

// udid → { stream, panelEl, frameEl, canvasEl, overlayEl, pillEl, dotEl, ro, appearMode }
const simPanels = new Map();
let focusedUdid = null;

// Terminal tabs: [{id, label, terminal, el}]
let termTabs = [];
let activeTermTabId = null;
let termOpen = false;
let termPinned = false;

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
  if (n.includes('pixel') || n.includes('nexus') || n.includes('android') || n.includes('emulator')) return '🤖';
  return '📱';
}

function updateModeBadge(info) {
  if (!info.mode) return;
  const fast = info.mode.startsWith('fast');
  modeBadge.textContent = fast ? 'fast' : 'compat';
  modeBadge.className = 'mode-badge ' + (fast ? 'fast' : 'compat');
}

// ── Permissions widget ────────────────────────────────────────────────────────
function renderPermsWidget(info) {
  const p = info.permissions || {};
  const isFast = (info.mode || '').startsWith('fast');

  const missing = [];
  if (!p.screen_recording) missing.push({
    key: 'screen_recording',
    label: 'Screen Recording',
    detail: 'System Settings → Privacy & Security → Screen Recording',
  });
  if (!p.accessibility) missing.push({
    key: 'accessibility',
    label: 'Accessibility',
    detail: 'System Settings → Privacy & Security → Accessibility',
  });

  if (isFast || missing.length === 0) {
    permsWidget.classList.add('hidden');
    return;
  }

  permsWidget.classList.remove('hidden');

  const binPath = info.binary_path || '';
  permsList.innerHTML = missing.map(m => `
    <div class="perms-item">
      <div class="perms-item-top">
        <span class="perms-item-label">${esc(m.label)}</span>
        <button class="perms-grant-btn" data-perm="${esc(m.key)}">Open Settings</button>
      </div>
      <div class="perms-item-detail">${esc(m.detail)}</div>
      ${binPath ? `<div class="perms-item-path">
        <span class="perms-path-value">${esc(binPath)}</span>
        <button class="perms-copy-btn" data-path="${esc(binPath)}" title="Copy path">Copy</button>
      </div>` : ''}
    </div>
  `).join('');

  permsList.querySelectorAll('.perms-grant-btn').forEach(btn => {
    btn.onclick = async () => {
      await requestPermission(btn.dataset.perm);
      const updated = await fetchInfo();
      renderPermsWidget(updated);
      updateModeBadge(updated);
    };
  });

  permsList.querySelectorAll('.perms-copy-btn').forEach(btn => {
    btn.onclick = () => {
      navigator.clipboard.writeText(btn.dataset.path);
      btn.textContent = 'Copied';
      setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
    };
  });

  permsBtn.onclick = () => {
    const open = permsBody.classList.toggle('open');
    permsBtn.classList.toggle('open', open);
  };
}

// ── Sims cache (stale-while-revalidate) ───────────────────────────────────────
const _SIMS_CACHE = 'simmerSimsCache';

function _readSimsCache() {
  try { return JSON.parse(localStorage.getItem(_SIMS_CACHE)); } catch { return null; }
}
function _writeSimsCache(sims, info) {
  try {
    localStorage.setItem(_SIMS_CACHE, JSON.stringify({
      sims, hasAdb: info.has_adb !== false,
      mode: info.mode, bundleId: info.bundle_id ?? null,
    }));
  } catch {}
}

// ── Device list ──────────────────────────────────────────────────────────────
async function loadSims() {
  // Show cached data immediately so the sidebar isn't blank while we wait
  const cached = _readSimsCache();
  if (cached?.sims) {
    allSims = cached.sims;
    hasAdb = cached.hasAdb ?? false;
    if (cached.mode) {
      const fast = cached.mode.startsWith('fast');
      modeBadge.textContent = fast ? 'fast' : 'compat';
      modeBadge.className = 'mode-badge ' + (fast ? 'fast' : 'compat');
    }
    if (cached.bundleId) {
      projFilterWrap.classList.add('visible');
      projFilterWrap.querySelector('span').textContent =
        cached.bundleId.split('.').pop() + ' only';
    }
    renderDeviceList();
  } else {
    deviceList.innerHTML = '<div class="device-list-empty">Scanning…</div>';
  }

  try {
    const [sims, info] = await Promise.all([fetchSims(), fetchInfo()]);
    allSims = sims;
    hasAdb = info.has_adb !== false;
    _writeSimsCache(sims, info);
    updateModeBadge(info);
    renderPermsWidget(info);

    if (info.bundle_id) {
      projFilterWrap.classList.add('visible');
      projFilterWrap.querySelector('span').textContent =
        info.bundle_id.split('.').pop() + ' only';
    } else {
      projFilterWrap.classList.remove('visible');
    }

    renderDeviceList();
  } catch {
    if (!cached?.sims) {
      deviceList.innerHTML = '<div class="device-list-empty">Could not reach server</div>';
    }
  }
}

// ── Add-simulator popover ─────────────────────────────────────────────────────
let _addDevices = [];
let _bootingIds = new Set();

function openAddPopover() {
  addPopover.classList.remove('hidden');
  addPopover.setAttribute('aria-hidden', 'false');
  addSearch.value = '';
  addList.innerHTML = '<div class="add-list-empty">Loading…</div>';
  addSearch.focus();

  fetchAvailableDevices().then(devices => {
    const bootedIds = new Set(allSims.map(s => s.id));
    _addDevices = devices.filter(d => !bootedIds.has(d.id));
    renderAddList('');
  }).catch(() => {
    addList.innerHTML = '<div class="add-list-empty">Could not load devices</div>';
  });
}

function closeAddPopover() {
  addPopover.classList.add('hidden');
  addPopover.setAttribute('aria-hidden', 'true');
}

function renderAddList(query) {
  const q = query.toLowerCase().trim();
  const filtered = q ? _addDevices.filter(d => d.name.toLowerCase().includes(q)) : _addDevices;

  if (!filtered.length) {
    addList.innerHTML = `<div class="add-list-empty">${q ? 'No matches' : 'No simulators available'}</div>`;
    return;
  }

  const groups = {};
  for (const d of filtered) {
    const g = d.platform === 'android' ? 'Android' : 'iOS';
    (groups[g] = groups[g] || []).push(d);
  }

  addList.innerHTML = Object.entries(groups).map(([label, devs]) => `
    <div class="add-group">
      <div class="add-group-label">${label}</div>
      ${devs.map(d => {
        const booting = _bootingIds.has(d.id);
        return `<div class="add-device-item" data-id="${esc(d.id)}" data-name="${esc(d.name)}"
                     data-platform="${esc(d.platform)}"
                     data-w="${d.width || 0}" data-h="${d.height || 0}">
          <span class="add-device-icon">${simIcon(d.name)}</span>
          <span class="add-device-info">
            <span class="add-device-name">${esc(d.name)}</span>
            ${d.runtime ? `<span class="add-device-sub">${esc(d.runtime)}</span>` : ''}
          </span>
          <button class="add-boot-btn${booting ? ' booting' : ''}" title="${booting ? 'Booting…' : 'Boot'}">
            ${booting ? '<span class="add-spinner"></span>' : '▶'}
          </button>
        </div>`;
      }).join('')}
    </div>`).join('');

  addList.querySelectorAll('.add-boot-btn:not(.booting)').forEach(btn => {
    const item = btn.closest('.add-device-item');
    btn.addEventListener('click', () => handleAddBoot(
      item.dataset.id, item.dataset.name, item.dataset.platform,
      parseInt(item.dataset.w), parseInt(item.dataset.h)
    ));
  });
}

async function handleAddBoot(id, name, platform, w, h) {
  if (_bootingIds.has(id)) return;
  _bootingIds.add(id);
  renderAddList(addSearch.value);

  const prevAndroidIds = new Set(allSims.filter(s => s.id.startsWith('emulator-')).map(s => s.id));

  try {
    if (platform === 'android') await bootAvd(id);
    else await bootSim(id);
  } catch { /* poll handles it */ }

  closeAddPopover();

  // Show a booting row in the sidebar while we wait
  if (platform === 'android') {
    _pendingBoots.set(id, { name, platform });
    renderDeviceList();
  }

  // Android emulators can take 2-3 minutes to fully boot
  const timeout = platform === 'android' ? 180_000 : 90_000;

  const poll = setInterval(async () => {
    const sims = await fetchSims().catch(() => null);
    if (!sims) return;
    let booted = null;
    if (platform === 'android') {
      booted = sims.find(s => s.id.startsWith('emulator-') && !prevAndroidIds.has(s.id));
    } else {
      booted = sims.find(s => s.id === id);
    }
    if (booted) {
      clearInterval(poll);
      _bootingIds.delete(id);
      _pendingBoots.delete(id);
      allSims = sims;
      renderDeviceList();
      addSimPanel(booted.id, booted.name, booted.width, booted.height);
    }
  }, 2000);

  setTimeout(() => {
    clearInterval(poll);
    _bootingIds.delete(id);
    _pendingBoots.delete(id);
    renderDeviceList();
  }, timeout);
}

addSimBtn.addEventListener('click', openAddPopover);
addCloseBtn.addEventListener('click', closeAddPopover);
addSearch.addEventListener('input', () => renderAddList(addSearch.value));
addPopover.addEventListener('keydown', e => { if (e.key === 'Escape') closeAddPopover(); });

function renderDeviceList() {
  const filterOn = projFilter.checked;
  const sims = filterOn ? allSims.filter(s => s.project_app) : allSims;
  const adbHint = !hasAdb
    ? '<div class="device-list-hint">🤖 <span>No <code>adb</code> — install <code>android-platform-tools</code> for Android</span></div>'
    : '';

  // Booting-but-not-yet-running rows
  const bootingRows = [..._pendingBoots.values()].map(b => `
    <div class="device-item device-item-booting">
      <span class="device-icon">${simIcon(b.name)}</span>
      <span class="device-info">
        <span class="device-name">${esc(b.name)}</span>
        <span class="device-dims">Booting…</span>
      </span>
      <span class="add-spinner" style="flex-shrink:0;margin-right:2px"></span>
    </div>`).join('');

  if (!sims.length) {
    deviceList.innerHTML = bootingRows + `<div class="device-list-empty">${
      filterOn ? 'No project simulators' : 'No simulators running'
    }</div>${adbHint}`;
    return;
  }
  deviceList.innerHTML = bootingRows + sims.map(s => `
    <div class="device-item${simPanels.has(s.id) ? ' active' : ''}"
         data-udid="${esc(s.id)}" data-name="${esc(s.name)}"
         data-w="${s.width}" data-h="${s.height}">
      <span class="device-icon">${simIcon(s.name)}</span>
      <span class="device-info">
        <span class="device-name">${esc(s.name)}</span>
        <span class="device-dims">${s.width && s.height ? `${s.width} × ${s.height}` : 'Android'}</span>
      </span>
      ${s.project_app ? '<span class="device-badge">★</span>' : ''}
    </div>`).join('') + adbHint;

  deviceList.querySelectorAll('.device-item').forEach(el => {
    el.addEventListener('click', () =>
      toggleDevice(el.dataset.udid, el.dataset.name,
                   parseInt(el.dataset.w), parseInt(el.dataset.h)));
  });
}

// ── Sim panel management ──────────────────────────────────────────────────────
function toggleDevice(udid, name, w, h) {
  if (simPanels.has(udid)) {
    removeSimPanel(udid);
  } else {
    addSimPanel(udid, name, w, h);
  }
}

function addSimPanel(udid, name, w, h) {
  if (simPanels.has(udid)) { setFocusedPanel(udid); return; }

  // ── Build DOM ──
  const panelEl = document.createElement('div');
  panelEl.className = 'sim-panel';
  panelEl.dataset.udid = udid;

  const frameEl = document.createElement('div');
  frameEl.className = 'device-frame';

  const canvasEl = document.createElement('canvas');
  canvasEl.width  = Math.min(w, h);
  canvasEl.height = Math.max(w, h);

  const overlayEl = document.createElement('div');
  overlayEl.className = 'connect-overlay';
  overlayEl.innerHTML = '<div class="spinner"></div><span>Connecting…</span>';

  frameEl.append(canvasEl, overlayEl);

  const pillEl = createPill(udid);
  panelEl.append(frameEl, pillEl);

  simPanelsEl.appendChild(panelEl);
  emptyState.classList.add('hidden');

  // ── Panel object ──
  const dotEl = pillEl.querySelector('.status-dot');
  const panel = {
    stream: null, panelEl, frameEl, canvasEl, overlayEl, pillEl, dotEl,
    ro: null, appearMode: 'dark',
  };
  simPanels.set(udid, panel);

  rebuildDividers();

  // ── ResizeObserver ──
  panel.ro = new ResizeObserver(() => sizeFrame(panel));
  panel.ro.observe(panelEl);

  // ── Stream ──
  panel.stream = new SimStream(udid, canvasEl, {
    fps:     parseInt(fpsSlider.value),
    quality: parseInt(qualSlider.value),
    onStatus:            s => updatePanelStatus(udid, s),
    onFirstFrame:        () => overlayEl.classList.add('hidden'),
    onOrientationChange: () => sizeFrame(panel),
  });
  panel.stream.updateSettings({ data_saver: dsBtn.classList.contains('active') });

  setFocusedPanel(udid);
  renderDeviceList();
  saveSession();
}

function removeSimPanel(udid) {
  const panel = simPanels.get(udid);
  if (!panel) return;

  panel.stream?.destroy();
  panel.ro?.disconnect();
  panel.panelEl.remove();
  simPanels.delete(udid);

  rebuildDividers();

  if (focusedUdid === udid) {
    focusedUdid = simPanels.size ? [...simPanels.keys()][0] : null;
    if (focusedUdid) setFocusedPanel(focusedUdid);
  }

  if (!simPanels.size) emptyState.classList.remove('hidden');
  renderDeviceList();
  saveSession();
}

// Corner radius in logical points for each device class.
// Matches UIScreen.cornerRadius on the actual device at 1× logical resolution.
function deviceCornerRadius(w, h) {
  const short = Math.min(w, h);
  if (short >= 500) return 12;   // Android physical pixels (1080+) — moderate radius
  if (short >= 744) return 18;   // iPad logical dp
  if (short <= 320) return 4;    // iPhone SE 1st gen
  if (short <= 375) return 39;   // iPhone X / SE 2nd–3rd gen era
  return 47;                     // iPhone 12 and later (larger radius)
}

function sizeFrame(panel) {
  const { panelEl, frameEl, canvasEl } = panel;
  const rect = panelEl.getBoundingClientRect();
  // Account for horizontal padding (2 × sp-5 = 40px) and bottom space for pill
  const availW = Math.max(1, rect.width  - 40);
  const availH = Math.max(1, rect.height - 20 - (48 + 32)); // top sp-5, bottom pill+gap
  const scale  = Math.min(availW / canvasEl.width, availH / canvasEl.height);
  frameEl.style.width  = Math.round(canvasEl.width  * scale) + 'px';
  frameEl.style.height = Math.round(canvasEl.height * scale) + 'px';
  const r = Math.round(deviceCornerRadius(canvasEl.width, canvasEl.height) * scale);
  frameEl.style.borderRadius = r + 'px';
}

// ── Dividers between panels ───────────────────────────────────────────────────
function rebuildDividers() {
  simPanelsEl.querySelectorAll('.sim-divider').forEach(d => d.remove());
  const panels = [...simPanelsEl.querySelectorAll('.sim-panel')];

  // Reset to equal flex shares whenever panels change
  panels.forEach(p => { p.style.flex = ''; });

  for (let i = 0; i < panels.length - 1; i++) {
    const divider = document.createElement('div');
    divider.className = 'sim-divider';
    panels[i].insertAdjacentElement('afterend', divider);
    initDividerDrag(divider, panels[i], panels[i + 1]);
  }

  simPanels.forEach(p => sizeFrame(p));
}

function initDividerDrag(divider, leftEl, rightEl) {
  let startX, leftW, rightW;

  divider.addEventListener('pointerdown', e => {
    e.preventDefault();
    divider.setPointerCapture(e.pointerId);
    startX = e.clientX;
    leftW  = leftEl.getBoundingClientRect().width;
    rightW = rightEl.getBoundingClientRect().width;

    divider.addEventListener('pointermove', onMove);
    divider.addEventListener('pointerup', onUp, { once: true });
  });

  function onMove(e) {
    const delta = e.clientX - startX;
    const total = leftW + rightW;
    const newLeft = Math.max(120, Math.min(total - 120, leftW + delta));
    const pct = (newLeft / total * 100).toFixed(2);
    leftEl.style.flex  = `0 0 ${pct}%`;
    rightEl.style.flex = `0 0 ${(100 - parseFloat(pct)).toFixed(2)}%`;
    const lu = leftEl.dataset.udid, ru = rightEl.dataset.udid;
    if (simPanels.has(lu))  sizeFrame(simPanels.get(lu));
    if (simPanels.has(ru))  sizeFrame(simPanels.get(ru));
  }

  function onUp() {
    divider.removeEventListener('pointermove', onMove);
  }
}

// ── Focus ─────────────────────────────────────────────────────────────────────
function setFocusedPanel(udid) {
  focusedUdid = udid;
  simPanels.forEach((p, id) =>
    p.panelEl.classList.toggle('focused', id === udid));
}

// ── Per-panel status ──────────────────────────────────────────────────────────
function updatePanelStatus(udid, status) {
  const panel = simPanels.get(udid);
  if (!panel) return;
  const { dotEl, overlayEl } = panel;
  dotEl.className = 'status-dot';
  if (status === 'streaming' || status === 'connected') {
    dotEl.classList.add('connected');
  } else if (status === 'reconnecting') {
    dotEl.classList.add('reconnecting');
    overlayEl.innerHTML = '<span>Reconnecting…</span>';
    overlayEl.classList.remove('hidden');
  } else if (status === 'no-frames') {
    overlayEl.classList.remove('hidden');
    overlayEl.innerHTML =
      `<span>No frames received.<br>Grant Screen Recording or run with <code>--mode compat</code>.</span>`;
  } else {
    overlayEl.innerHTML = '<div class="spinner"></div><span>Connecting…</span>';
    overlayEl.classList.remove('hidden');
  }
}

// ── Controls pill (per panel) ─────────────────────────────────────────────────
function createPill(udid) {
  const pill = document.createElement('div');
  pill.className = 'controls-pill';
  pill.innerHTML = `
    <div class="status-dot"></div>
    <div class="pill-sep"></div>
    <button class="pill-btn" data-action="rotate" title="Rotate">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3.5 10a6.5 6.5 0 1 0 6.5-6.5H7"/><path d="M7 1.5v4H3"/>
      </svg>
    </button>
    <button class="pill-btn" data-action="home" title="Home">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 9.5L10 3l7 6.5"/><path d="M5 8.5v8h3.5v-4h3v4H15v-8"/>
      </svg>
    </button>
    <button class="pill-btn" data-action="appear" title="Switch to light">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
        <path d="M10 3.5a6.5 6.5 0 0 0 0 13A7.5 7.5 0 0 1 10 3.5z"/>
      </svg>
    </button>
    <div class="pill-sep"></div>
    <button class="pill-btn" data-action="kbd" title="Keyboard">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <rect x="1" y="5" width="18" height="11" rx="2"/>
        <path d="M5 9h1M9 9h1M13 9h1M5 13h10"/>
      </svg>
    </button>
    <button class="pill-btn" data-action="close" title="Close simulator">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
        <path d="M5 5l10 10M15 5L5 15"/>
      </svg>
    </button>`;

  pill.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const panel  = simPanels.get(udid);

    setFocusedPanel(udid);

    switch (action) {
      case 'rotate': panel?.stream?.send({ type: 'rotate' }); break;
      case 'home':   panel?.stream?.send({ type: 'home' });   break;
      case 'appear': {
        if (!panel) break;
        panel.appearMode = panel.appearMode === 'dark' ? 'light' : 'dark';
        const light = panel.appearMode === 'light';
        btn.innerHTML = light
          ? `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="3.5"/><path d="M10 2.5v1.5M10 16v1.5M2.5 10H4M16 10h1.5M4.7 4.7l1 1M14.3 14.3l1 1M15.3 4.7l-1 1M5.7 14.3l-1 1"/></svg>`
          : `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3.5a6.5 6.5 0 0 0 0 13A7.5 7.5 0 0 1 10 3.5z"/></svg>`;
        btn.title = light ? 'Switch to dark' : 'Switch to light';
        panel.stream?.send({ type: 'appearance', mode: panel.appearMode });
        break;
      }
      case 'kbd': {
        const open = kbdBar.classList.toggle('visible');
        btn.classList.toggle('active', open);
        if (open) kbdInput.focus();
        break;
      }
      case 'close': removeSimPanel(udid); break;
    }
  });

  // clicking anywhere on the panel body (outside controls) focuses it
  return pill;
}

// ── Settings sliders ─────────────────────────────────────────────────────────
fpsSlider.addEventListener('input', () => {
  fpsVal.textContent = fpsSlider.value;
  simPanels.forEach(p => p.stream?.updateSettings({ fps: parseInt(fpsSlider.value) }));
  saveSession();
});
qualSlider.addEventListener('input', () => {
  qualVal.textContent = qualSlider.value;
  simPanels.forEach(p => p.stream?.updateSettings({ quality: parseInt(qualSlider.value) }));
  saveSession();
});
dsBtn.addEventListener('click', () => {
  const on = dsBtn.classList.toggle('active');
  dsBtn.textContent = on ? 'Data Saver: On' : 'Data Saver';
  simPanels.forEach(p => p.stream?.updateSettings({ data_saver: on }));
  saveSession();
});
projFilter.addEventListener('change', renderDeviceList);
$('btn-refresh').addEventListener('click', loadSims);

// ── Keyboard bar (sends to focused panel) ─────────────────────────────────────
function sendKbdText() {
  const t = kbdInput.value; if (!t) return;
  simPanels.get(focusedUdid)?.stream?.send({ type: 'text', text: t });
  kbdInput.value = ''; kbdInput.focus();
}
kbdInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendKbdText(); } });
$('kbd-send').addEventListener('click', sendKbdText);
$('kbd-bs').addEventListener('click',  () => simPanels.get(focusedUdid)?.stream?.send({ type: 'key', key: 'backspace' }));
$('kbd-ret').addEventListener('click', () => simPanels.get(focusedUdid)?.stream?.send({ type: 'key', key: 'return' }));

// ── Terminal font size ────────────────────────────────────────────────────────
const FONT_MIN = 9, FONT_MAX = 24;
let termFontSize = parseInt(localStorage.getItem('termFontSize') || '13');

function applyFontSize(size) {
  termFontSize = Math.max(FONT_MIN, Math.min(FONT_MAX, size));
  localStorage.setItem('termFontSize', termFontSize);
  $('font-size-val').textContent = termFontSize;
  termTabs.forEach(t => t.terminal.setFontSize(termFontSize));
}

$('btn-font-dec').addEventListener('click', () => applyFontSize(termFontSize - 1));
$('btn-font-inc').addEventListener('click', () => applyFontSize(termFontSize + 1));
$('font-size-val').textContent = termFontSize;

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
    const tab = termTabs.find(t => t.id === id);
    tab?.terminal.fit();
    tab?.terminal.focus();
  });
}

function addTermTab() {
  const id    = 'term-' + Date.now();
  const n     = termTabs.length + 1;
  const label = n === 1 ? 'Terminal' : `Terminal ${n}`;

  const el = document.createElement('div');
  el.className = 'term-pane';
  termPanes.appendChild(el);

  const terminal = new SimTerminal(el, {
    onStatus: s => {
      if (id !== activeTermTabId) return;
      const dot = $('term-status-dot');
      if (!dot) return;
      dot.className = 'status-dot';
      if (s === 'connected')    dot.classList.add('connected');
      else if (s === 'reconnecting') dot.classList.add('reconnecting');
    },
  });

  terminal.setFontSize(termFontSize);
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

  if (!termTabs.length) { setTermOpen(false); return; }
  if (activeTermTabId === id) activateTermTab(termTabs[Math.max(0, idx - 1)].id);
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
    if (open) {
      const active = termTabs.find(t => t.id === activeTermTabId);
      active?.terminal.fit();
      active?.terminal.focus();
    }
  }, { once: true });

  if (open && !termTabs.length) addTermTab();
  saveSession();
}

$('btn-terminal').addEventListener('click', () => setTermOpen(!termOpen));
$('btn-close-term').addEventListener('click', () => {
  // Unpin when closing so the bottom tab bar is always reachable
  if (termPinned) {
    termPinned = false;
    content.classList.remove('pinned-right');
    $('btn-pin-term').classList.remove('active');
    termPanel.style.width = '';
    termPanel.style.height = '300px';
  }
  setTermOpen(false);
});
$('btn-add-term').addEventListener('click', addTermTab);

$('btn-pin-term').addEventListener('click', () => {
  termPinned = !termPinned;
  content.classList.toggle('pinned-right', termPinned);
  $('btn-pin-term').classList.toggle('active', termPinned);

  if (termPinned) {
    termPanel.style.height = '';
  } else {
    termPanel.style.width = '';
    termPanel.style.height = '300px';
  }

  saveSession();
  requestAnimationFrame(() => {
    termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
    simPanels.forEach(p => sizeFrame(p));
  });
});

// ── Terminal resize (drag handle) ─────────────────────────────────────────────
(function initTermResize() {
  const handle = $('term-resize-handle');
  let startPos, startSize;

  handle.addEventListener('pointerdown', e => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);

    if (termPinned) {
      startPos  = e.clientX;
      startSize = termPanel.getBoundingClientRect().width;
    } else {
      startPos  = e.clientY;
      startSize = termPanel.getBoundingClientRect().height;
    }

    handle.addEventListener('pointermove', onMove);
    handle.addEventListener('pointerup', () => {
      handle.removeEventListener('pointermove', onMove);
      termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
      saveSession();
    }, { once: true });
  });

  function onMove(e) {
    if (termPinned) {
      const delta = startPos - e.clientX;
      const w = Math.max(180, Math.min(window.innerWidth * 0.6, startSize + delta));
      termPanel.style.width = w + 'px';
    } else {
      const delta = startPos - e.clientY;
      const h = Math.max(80, Math.min(window.innerHeight * 0.75, startSize + delta));
      termPanel.style.height = h + 'px';
    }
    termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
    simPanels.forEach(p => sizeFrame(p));
  }
})();

// Refit terminal + sim frames on window resize
new ResizeObserver(() => {
  termTabs.find(t => t.id === activeTermTabId)?.terminal.fit();
  simPanels.forEach(p => sizeFrame(p));
}).observe(termPanel);

// ── Session persistence ───────────────────────────────────────────────────────
const _SESSION_KEY = 'simmerSession';

function saveSession() {
  const pinned = termPinned;
  try {
    localStorage.setItem(_SESSION_KEY, JSON.stringify({
      openUdids:   [...simPanels.keys()],
      termOpen,
      termPinned:  pinned,
      termHeight:  pinned ? null : (parseInt(termPanel.style.height) || null),
      termWidth:   pinned ? (parseInt(termPanel.style.width)  || null) : null,
      fps:         parseInt(fpsSlider.value),
      quality:     parseInt(qualSlider.value),
      dataSaver:   dsBtn.classList.contains('active'),
    }));
  } catch { /* storage full or private mode */ }
}

function restoreSession() {
  try { return JSON.parse(localStorage.getItem(_SESSION_KEY)); } catch { return null; }
}

// ── Startup ───────────────────────────────────────────────────────────────────
const urlUdid = new URLSearchParams(location.search).get('view');
loadSims().then(() => {
  if (urlUdid) {
    const sim = allSims.find(s => s.id === urlUdid);
    if (sim) addSimPanel(sim.id, sim.name, sim.width, sim.height);
    return;
  }

  const s = restoreSession();
  if (!s) return;

  // Restore sliders before opening panels so streams pick up the right values
  if (s.fps)     { fpsSlider.value  = s.fps;     fpsVal.textContent  = s.fps; }
  if (s.quality) { qualSlider.value = s.quality;  qualVal.textContent = s.quality; }
  if (s.dataSaver) {
    dsBtn.classList.add('active');
    dsBtn.textContent = 'Data Saver: On';
  }

  // Restore open simulator panels (only those still running)
  for (const udid of (s.openUdids || [])) {
    const sim = allSims.find(sim => sim.id === udid);
    if (sim) addSimPanel(sim.id, sim.name, sim.width, sim.height);
  }

  // Restore terminal layout first, then open it (so size is set before fit())
  // Only restore pinned state if the terminal was also open — otherwise the
  // bottom tab bar would be hidden with no way to reopen the terminal.
  if (s.termPinned && s.termOpen) {
    termPinned = true;
    content.classList.add('pinned-right');
    $('btn-pin-term').classList.add('active');
    if (s.termWidth) termPanel.style.width = s.termWidth + 'px';
  } else if (s.termHeight) {
    termPanel.style.height = s.termHeight + 'px';
  }
  if (s.termOpen) setTermOpen(true);
});
