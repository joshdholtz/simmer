# 🫧 simmer

Stream your iOS Simulator to any browser — touch, keyboard, terminal, side by side.

![simmer screenshot](https://github.com/joshdholtz/simmer/raw/main/docs/screenshot.png)

## What it does

- **Live stream** — your iOS Simulator renders in any browser at up to 30fps
- **Touch & type** — tap, drag, rotate, send text, press keys
- **Terminal** — built-in persistent terminal (survives reconnects, tmux-friendly)
- **Multi-sim** — open multiple simulators side-by-side with a draggable divider
- **Remote-friendly** — works great over Tailscale from an iPad

## Install

### Homebrew (recommended)

```bash
brew tap joshdholtz/tap
brew install simmer
```

### pip

```bash
pip install simmer
```

### From source

```bash
git clone https://github.com/joshdholtz/simmer
cd simmer
pip install -e .
```

## Usage

```bash
# Start in your project directory — simmer auto-detects your bundle ID
simmer

# Options
simmer --port 8080        # custom port (default: 4040)
simmer --fps 30           # frame rate (default: 15)
simmer --quality 80       # JPEG quality 10-95 (default: 70)
simmer --mode fast        # force Quartz backend
simmer --mode compat      # force simctl+idb backend
simmer --kill             # stop any running instance
```

Then open `http://localhost:4040` in your browser (or your Tailscale IP from any device).

## Backends

simmer auto-selects the best backend for your setup:

| Mode | Capture | Input | Requirement |
|------|---------|-------|-------------|
| **fast** | Quartz (native) | CGEvent | Screen Recording + Accessibility permissions |
| **compat** | simctl screenshot | idb | `brew install idb-companion` |

On first run, simmer tells you which mode it's using and what to do if you want to upgrade.

### Fast mode setup

Grant permissions in **System Settings → Privacy & Security**:
- Screen Recording → add Terminal (or your Python binary)
- Accessibility → add `rotate_sim` (prompted on first rotate)

### Compat mode setup

```bash
brew tap facebook/fb
brew install idb-companion
```

No permissions needed — works immediately, slower frame rate.

## Tips

### tmux scrolling

If you use tmux in the built-in terminal, enable mouse mode to get correct scrolling:

```bash
# ~/.tmux.conf
set -g mouse on
```

Without this, scroll events go to xterm.js's raw buffer instead of tmux's, which looks weird.

### Remote access

simmer binds to `0.0.0.0` so it's reachable from any device on your network.
[Tailscale](https://tailscale.com) is the easiest way to access it from outside your LAN.

### URL params

Open a specific simulator directly:

```
http://localhost:4040?view=<UDID>
```

### Data Saver

Enable in the sidebar to reduce bandwidth — lowers quality and frame rate automatically.

## Architecture

```
simmer/
  __main__.py          CLI entry point, backend selection
  server.py            aiohttp WebSocket + HTTP server
  backend_quartz.py    Fast backend: Quartz window capture + CGEvent injection
  backend_simctl.py    Compat backend: simctl screenshot + idb injection
  backend_base.py      Shared types and capability detection
  static/
    index.html
    css/               tokens, layout, components, terminal
    js/                app.js, stream.js, terminal.js, api.js
```

### How streaming works

1. Server captures the simulator window (Quartz or simctl) as JPEG
2. Frame is sent over WebSocket as binary
3. Browser decodes via `URL.createObjectURL` + `<canvas>`
4. Touch/tap/key events go back over the same WebSocket
5. PTY sessions are persistent — terminal survives page refresh and reconnects

### Why not serve-sim / appetize?

- [serve-sim](https://github.com/EvanBacon/serve-sim) (Expo) — similar idea, requires npm, no terminal
- [appetize.io](https://appetize.io) — cloud-hosted, not local, no terminal
- simmer — pure Python, no npm/node, has terminal, multi-sim, Homebrew-installable

## License

MIT
