const TIMEOUT = 8000;

async function _fetch(path, options = {}) {
  const abort = new AbortController();
  const t = setTimeout(() => abort.abort(), TIMEOUT);
  try {
    const r = await fetch(path, { signal: abort.signal, ...options });
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

export async function fetchInfo() {
  return _fetch('/api/info').catch(() => ({}));
}

export async function fetchSims() {
  return _fetch('/api/sims');
}

export async function fetchAvailableDevices() {
  return _fetch('/api/devices').catch(() => []);
}

export async function bootSim(udid) {
  return _fetch(`/api/boot/${udid}`, { method: 'POST' });
}
