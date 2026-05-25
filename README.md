# 🫧 simmer

> Stream your iOS Simulator to any browser — touch, keyboard, multi-sim, built-in terminal.

<p align="center">
  <img src="https://github.com/joshdholtz/simmer/raw/main/docs/hero.png" alt="simmer — iOS Simulator in your browser" width="100%">
</p>

<p align="center">
  <a href="https://github.com/joshdholtz/simmer/releases/latest"><img alt="GitHub release" src="https://img.shields.io/github/v/release/joshdholtz/simmer?style=flat-square&color=0a84ff"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-30d158?style=flat-square"></a>
  <img alt="Platform: macOS" src="https://img.shields.io/badge/platform-macOS-bf5af2?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-ff9f0a?style=flat-square">
</p>

---

Run `simmer` in your project directory, open a browser, and your iOS Simulator appears — tappable, typeable, and shareable over your local network or Tailscale. No Xcode open. No npm. Works from an iPad on the couch.

## Why

I do most of my dev work SSHed into a Mac mini. I wanted to see my iOS Simulator from wherever I am — on the couch, on a plane, from my iPad — without having to be sitting at my desk. I also really wanted it to work on a plane with minimal latency, which ruled out anything cloud-based.

Nothing out there was simple and local enough, so I built this.

## Features

- **Live stream** — renders the simulator at up to 30 fps in any browser tab
- **Touch & type** — tap, swipe, rotate, send text, press hardware buttons
- **Multi-sim** — open several simulators side-by-side with a draggable divider
- **Built-in terminal** — persistent PTY session that survives page refreshes (tmux-friendly)
- **Boot from sidebar** — start a shut-down simulator without touching Xcode
- **Remote-friendly** — streams over your LAN or Tailscale from any device

## Requirements

- macOS 13 Ventura or later
- Xcode Command Line Tools (`xcode-select --install`)
- Python 3.11+

Optional, for the **fast** backend (recommended):

- Screen Recording permission granted to Terminal / your shell
- Accessibility permission granted to `rotate_sim`

Optional, for the **compat** backend:

- [`idb-companion`](https://github.com/facebook/idb) — `brew tap facebook/fb && brew install idb-companion`

## Install

### Homebrew (recommended)

```bash
brew tap joshdholtz/tap
brew install simmer
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
simmer --port 8080     # custom port (default: 4040)
simmer --fps 30        # capture frame rate (default: 15)
simmer --quality 80    # JPEG quality 10–95 (default: 70)
simmer --mode fast     # force Quartz backend
simmer --mode compat   # force simctl+idb backend
simmer --kill          # stop a running instance
```

Then open `http://localhost:4040` in any browser. From another device on your network (or over Tailscale), use your Mac's IP instead of `localhost`.

## Backends

simmer picks the best backend automatically:

| Mode | Capture | Input | Requires |
|------|---------|-------|----------|
| **fast** | Quartz (native) | CGEvent | Screen Recording + Accessibility |
| **compat** | `simctl screenshot` | `idb` | `idb-companion` |

The startup log tells you which mode is active and what's needed to upgrade.

### Fast mode — grant permissions

In **System Settings → Privacy & Security**:

- **Screen Recording** → add Terminal (or your Python binary)
- **Accessibility** → add `rotate_sim` (prompted automatically on first rotate)

### Compat mode — install idb

```bash
brew tap facebook/fb
brew install idb-companion
```

No permissions required; works immediately, lower frame rate.

## Tips

### tmux scrolling

Add this to `~/.tmux.conf` so scroll events reach tmux rather than the raw terminal buffer:

```conf
set -g mouse on
```

### Open a specific simulator via URL

```
http://localhost:4040?view=<UDID>
```

### Data Saver mode

Enable in the sidebar to automatically reduce quality and frame rate — useful on slow Wi-Fi or when streaming to a phone.

### Font size in the terminal

Use the **A−** / **A+** buttons in the terminal drawer header. The setting persists across sessions.

## Architecture

```
simmer/
  __main__.py          CLI entry point + backend selection
  server.py            aiohttp HTTP + WebSocket server
  backend_quartz.py    Fast backend: Quartz window capture + CGEvent injection
  backend_simctl.py    Compat backend: simctl screenshot + idb input injection
  backend_base.py      Shared helpers, device discovery, boot
  static/
    index.html
    css/               tokens.css, layout.css, components.css, terminal.css
    js/                app.js, stream.js, terminal.js, api.js
```

**Streaming pipeline:**

1. Server captures the simulator window (Quartz or simctl) as JPEG
2. Frame is pushed over WebSocket as binary
3. Browser decodes with `createObjectURL` and draws to `<canvas>`
4. Touch / key events travel back over the same WebSocket
5. PTY sessions are persistent — terminal survives refresh and reconnect

## Prior art

| Tool | Capture | Input | Terminal | Multi-sim | Install |
|------|---------|-------|----------|-----------|---------|
| [serve-sim](https://github.com/EvanBacon/serve-sim) | simctl | idb | ✗ | ✗ | npm |
| [appetize.io](https://appetize.io) | cloud | cloud | ✗ | ✗ | account |
| **simmer** | Quartz / simctl | CGEvent / idb | ✓ | ✓ | Homebrew |

## Contributing

Issues and PRs welcome. A few things to know before diving in:

- No build step — the frontend is plain ES modules with no bundler
- Static files live in `simmer/static/` and are served directly by aiohttp in dev
- The Homebrew formula lives in `Formula/simmer.rb`; update it after bumping the version

```bash
git clone https://github.com/joshdholtz/simmer
cd simmer
pip install -e .
simmer   # edit → refresh, no restart needed for static changes
```

## License

MIT © [Josh Holtz](https://github.com/joshdholtz)
