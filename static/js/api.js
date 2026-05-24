const TIMEOUT = 8000;

async function _fetch(path) {
  const abort = new AbortController();
  const t = setTimeout(() => abort.abort(), TIMEOUT);
  try {
    const r = await fetch(path, { signal: abort.signal });
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
