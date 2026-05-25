# simmer — project notes for AI assistants

## What this is

simmer streams iOS Simulators and Android Emulators to any browser tab with touch, keyboard, and a built-in terminal. It's a single Python server (aiohttp) + plain-ES-module frontend. No bundler, no npm.

## Architecture in one paragraph

`__main__.py` selects backends at startup and hands a single backend object to `server.py`. When both iOS and Android are available, they're wrapped in `MultiBackend` which routes every call to the right sub-backend by UDID. The server captures frames in a background task and pushes them over WebSocket as binary JPEG (iOS) or PNG (Android). The browser draws to `<canvas>` and sends touch/key events back over the same socket. PTY sessions survive page refresh.

## Key design decisions and gotchas

### Android adb — SDK vs Homebrew
Always use `~/Library/Android/sdk/platform-tools/adb`, **not** Homebrew's `android-platform-tools`. Homebrew's adb starts a separate daemon that can't see emulators launched by Android Studio. `_find_adb()` and `has_adb()` both check SDK roots first.

### Android tap coordinates — physical pixels, not dp
`adb screencap` returns physical pixel PNGs. Device dimensions (width/height on SimDevice) are stored as physical pixels. Tap/drag math is just `x = int(nx * dev_w)` with no density conversion. Do not add density logic here — it was tried and caused mis-taps because the dp→pixel conversion didn't round-trip cleanly.

### `start_new_session=True` in boot_avd
Emulators booted by simmer must be detached from simmer's process group. Without this, Ctrl+C sends SIGINT to the emulator too.

### `_needs_rotation` with MultiBackend
`backend.name` for MultiBackend contains all backend names, so `"android" not in backend.name` is unreliable. Instead look up `backend._backend_for(udid)` to get the specific sub-backend for that UDID, then check its name.

### WS dimensions come from query params, not list_sims
The WS handler reads `?w=<width>&h=<height>` from the URL (sent by `stream.js`) rather than calling `backend.list_sims()` on every connection. This avoids a slow serial-port round-trip on each connect.

### Session restore (localStorage)
`_SESSION_KEY` in `app.js` stores open UDIDs, terminal state, fps, quality, and dataSaver. On load, `restoreSession()` reopens the last layout. `_SIMS_CACHE` is a stale-while-revalidate cache — show cached sims instantly, fetch fresh in background.

## File map

```
simmer/
  __main__.py        CLI, backend selection, MultiBackend wiring
  server.py          aiohttp HTTP + WebSocket server, all routes
  backend_quartz.py  Fast backend: Quartz capture, CGEvent input
  backend_simctl.py  Compat backend: simctl capture, idb input
  backend_adb.py     Android backend: adb screencap + adb input, AVD boot
  backend_multi.py   Combines backends, routes by UDID, parallel polling
  backend_base.py    SimDevice dataclass, Backend protocol, shared helpers
  static/
    index.html
    css/             tokens.css, layout.css, components.css, terminal.css
    js/              app.js (UI), stream.js (WS+canvas), terminal.js, api.js
```

## What NOT to do

- Don't add a bundler or transpiler — the frontend is intentionally vanilla JS
- Don't re-introduce `--mode android` as a CLI flag — Android is always auto-detected now
- Don't create git tags or cut releases without explicit user instruction
- Don't convert Android coordinates to logical dp — stay in physical pixels end-to-end
