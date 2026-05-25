const CONNECT_TIMEOUT = 5000;
const RECONNECT_DELAY = 2000;
const NO_FRAME_WARN   = 4000;
const WATCHDOG_POLL   = 3000;
const WATCHDOG_STALE  = 8000;
const DRAG_THRESHOLD  = 0.015;

export class SimStream {
  #udid; #canvas; #ctx;
  #ws = null; #connectTimer = null; #reconnectTimer = null; #watchdog = null;
  #lastFrameAt = 0; #firstFrame = false; #frameInFlight = false;
  #portraitW; #portraitH; #isLandscape = false;
  #onStatus; #onFirstFrame; #onOrientationChange;

  constructor(udid, canvas, { fps = 15, quality = 70, onStatus, onFirstFrame, onOrientationChange } = {}) {
    this.#udid = udid;
    this.#canvas = canvas;
    this.#ctx = canvas.getContext('2d');
    this.#portraitW = canvas.width;
    this.#portraitH = canvas.height;
    this.#onStatus = onStatus ?? (() => {});
    this.#onFirstFrame = onFirstFrame ?? (() => {});
    this.#onOrientationChange = onOrientationChange ?? (() => {});

    this.settings = { fps, quality, data_saver: false, dev_w: canvas.width, dev_h: canvas.height };

    this.#setupPointer();
    this.#connect();
  }

  send(msg) {
    if (this.#ws?.readyState === WebSocket.OPEN) {
      this.#ws.send(JSON.stringify(msg));
    }
  }

  updateSettings(patch) {
    Object.assign(this.settings, patch);
    this.send({ type: 'settings', ...patch });
  }

  destroy() {
    clearTimeout(this.#connectTimer);
    clearTimeout(this.#reconnectTimer);
    clearInterval(this.#watchdog);
    if (this.#ws) { this.#ws.onclose = null; this.#ws.close(); this.#ws = null; }
  }

  #setOrientation(landscape) {
    if (landscape === this.#isLandscape) return;
    this.#isLandscape = landscape;
    this.#canvas.width  = landscape ? this.#portraitH : this.#portraitW;
    this.#canvas.height = landscape ? this.#portraitW : this.#portraitH;
    this.send({ type: 'settings', dev_w: this.#canvas.width, dev_h: this.#canvas.height });
    this.#onOrientationChange(this.#canvas.width, this.#canvas.height);
  }

  #connect() {
    clearTimeout(this.#connectTimer);
    clearTimeout(this.#reconnectTimer);
    if (this.#ws) { this.#ws.onclose = null; this.#ws.close(); }

    this.#firstFrame = false;
    this.#onStatus('connecting');

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(
      `${proto}//${location.host}/ws/${this.#udid}?fps=${this.settings.fps}&quality=${this.settings.quality}&w=${this.#portraitW}&h=${this.#portraitH}`
    );
    this.#ws = ws;
    ws.binaryType = 'blob';

    this.#connectTimer = setTimeout(() => {
      if (ws.readyState === WebSocket.CONNECTING) {
        ws.onclose = null; ws.close();
        this.#reconnectTimer = setTimeout(() => this.#connect(), 1000);
      }
    }, CONNECT_TIMEOUT);

    let noFrameTimer = null;

    ws.onopen = () => {
      clearTimeout(this.#connectTimer);
      this.#onStatus('connected');
      noFrameTimer = setTimeout(() => {
        if (!this.#firstFrame) this.#onStatus('no-frames');
      }, NO_FRAME_WARN);
    };

    ws.onclose = () => {
      clearTimeout(this.#connectTimer);
      clearTimeout(noFrameTimer);
      if (this.#ws === ws) {
        this.#onStatus('reconnecting');
        this.#reconnectTimer = setTimeout(() => this.#connect(), RECONNECT_DELAY);
      }
    };

    ws.onerror = () => ws.close();

    ws.onmessage = e => {
      if (typeof e.data === 'string') {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'rotated') this.#setOrientation(!this.#isLandscape);
        } catch {}
        return;
      }
      if (!(e.data instanceof Blob)) return;

      this.#lastFrameAt = Date.now();
      if (!this.#firstFrame) {
        this.#firstFrame = true;
        clearTimeout(noFrameTimer);
        this.#onStatus('streaming');
        this.#onFirstFrame();
      }
      if (this.#frameInFlight) return;
      this.#frameInFlight = true;

      const url = URL.createObjectURL(e.data);
      const img = new Image();
      img.onload = () => {
        this.#setOrientation(img.naturalWidth > img.naturalHeight);
        this.#ctx.drawImage(img, 0, 0, this.#canvas.width, this.#canvas.height);
        URL.revokeObjectURL(url);
        this.#frameInFlight = false;
      };
      img.onerror = () => { URL.revokeObjectURL(url); this.#frameInFlight = false; };
      img.src = url;
    };

    clearInterval(this.#watchdog);
    this.#watchdog = setInterval(() => {
      if (this.#ws?.readyState === WebSocket.OPEN &&
          this.#lastFrameAt > 0 &&
          Date.now() - this.#lastFrameAt > WATCHDOG_STALE) {
        this.#connect();
      }
    }, WATCHDOG_POLL);
  }

  #setupPointer() {
    const canvas = this.#canvas;
    let origin = null;

    const norm = e => {
      const r = canvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
        y: Math.max(0, Math.min(1, (e.clientY - r.top)  / r.height)),
      };
    };

    canvas.addEventListener('pointerdown', e => {
      e.preventDefault();
      canvas.setPointerCapture(e.pointerId);
      origin = norm(e);
    }, { passive: false });

    canvas.addEventListener('pointerup', e => {
      e.preventDefault();
      if (!origin) return;
      const end = norm(e);
      const dx = end.x - origin.x, dy = end.y - origin.y;
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) {
        this.send({ type: 'tap', x: end.x, y: end.y });
      } else {
        this.send({ type: 'drag', x1: origin.x, y1: origin.y, x2: end.x, y2: end.y });
      }
      origin = null;
    }, { passive: false });

    canvas.addEventListener('pointercancel', () => { origin = null; });
  }
}
