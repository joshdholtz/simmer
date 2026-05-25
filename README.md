# 🫧 simmer

> Stream your iOS Simulator or Android Emulator to any browser — touch, keyboard, multi-sim, built-in terminal.

<p align="center">
  <img src="https://github.com/joshdholtz/simmer/raw/main/docs/hero.png" alt="simmer — iOS Simulator in your browser" width="100%">
</p>

<p align="center">
  <a href="https://github.com/joshdholtz/simmer/releases/latest"><img alt="GitHub release" src="https://img.shields.io/github/v/release/joshdholtz/simmer?style=flat-square&color=0a84ff"></a>
  <a href="https://github.com/joshdholtz/simmer/actions/workflows/test.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/joshdholtz/simmer/test.yml?branch=main&style=flat-square&label=tests"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-30d158?style=flat-square"></a>
  <img alt="Platform: macOS" src="https://img.shields.io/badge/platform-macOS-bf5af2?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-ff9f0a?style=flat-square">
</p>

---

Run `simmer` in your project directory, open a browser, and your simulators appear — tappable, typeable, and shareable over your local network or Tailscale. iOS and Android side-by-side. No Xcode open. No npm. Works from an iPad on the couch.

## Why

I built this on a plane so I could use it on a plane.

I do most of my dev work SSHed into a Mac mini and I wanted a simple local way to see my iOS Simulator from my iPad without being at my desk. Nothing out there was simple enough so I built this at 30,000 feet.

## Features

- **Live stream** — renders at up to 30 fps in any browser tab
- **Touch & type** — tap, swipe, rotate, send text, press hardware buttons
- **iOS + Android** — iOS Simulators and Android Emulators in the same sidebar, automatically detected
- **Multi-sim** — open several devices side-by-side with a draggable divider
- **Built-in terminal** — persistent PTY session that survives page refreshes (tmux-friendly)
- **Boot from sidebar** — start a shut-down simulator or AVD with a searchable `+` picker
- **Session restore** — reopens your last layout on restart
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

Optional, for **Android emulators**:

- Android Studio (includes `adb` and the emulator — no separate install needed)

## Install

### Homebrew (recommended)

```bash
brew install joshdholtz/tap/simmer
```

To update:

```bash
brew update && brew upgrade joshdholtz/tap/simmer
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
simmer --mode fast     # force Quartz backend (iOS)
simmer --mode compat   # force simctl+idb backend (iOS)
simmer --kill          # stop a running instance
```

Then open `http://localhost:4040` in any browser. From another device on your network (or over Tailscale), use your Mac's IP instead of `localhost`.

## Backends

simmer picks the best backend automatically and combines them — iOS and Android devices appear together:

| Mode | Capture | Input | Requires |
|------|---------|-------|----------|
| **fast** | Quartz (native) | CGEvent | Screen Recording + Accessibility |
| **compat** | `simctl screenshot` | `idb` | `idb-companion` |
| **Android** | `adb screencap` | `adb input` | Android Studio |

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

### Android emulators

If you have **Android Studio**, nothing extra is needed. simmer finds the `adb` bundled in `~/Library/Android/sdk/platform-tools/` automatically.

Start an emulator from Android Studio and it appears in the simmer sidebar alongside your iOS simulators. You can also boot AVDs directly from simmer's `+` picker.

> **Don't use `brew install android-platform-tools`** — Homebrew's standalone adb starts a separate daemon and won't see emulators launched by Android Studio.

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
  backend_adb.py       Android backend: adb screencap + adb input
  backend_multi.py     Combines multiple backends, routes by UDID
  backend_base.py      Shared helpers, device discovery, boot
  static/
    index.html
    css/               tokens.css, layout.css, components.css, terminal.css
    js/                app.js, stream.js, terminal.js, api.js
```

**Streaming pipeline:**

1. Server captures the simulator/emulator window as JPEG (iOS) or PNG (Android)
2. Frame is pushed over WebSocket as binary
3. Browser decodes with `createObjectURL` and draws to `<canvas>`
4. Touch / key events travel back over the same WebSocket
5. PTY sessions are persistent — terminal survives refresh and reconnect

## Prior art

| Tool | Capture | Input | Terminal | Multi-sim | Android | Install |
|------|---------|-------|----------|-----------|---------|---------|
| [serve-sim](https://github.com/EvanBacon/serve-sim) | simctl | idb | ✗ | ✗ | ✗ | npm |
| [appetize.io](https://appetize.io) | cloud | cloud | ✗ | ✗ | ✓ | account |
| **simmer** | Quartz / simctl / adb | CGEvent / idb / adb | ✓ | ✓ | ✓ | Homebrew |

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
