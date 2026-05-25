from __future__ import annotations
import asyncio
import concurrent.futures
import fcntl
import hashlib
import json
import math
import os
import pty
import signal
import socket
import struct
import subprocess
import termios
import uuid
from importlib.resources import files
from pathlib import Path
from typing import Any, Optional

import aiohttp
from aiohttp import web

from .backend_base import sim_has_app, list_available_devices, boot_sim

import sys as _sys
if getattr(_sys, 'frozen', False):
    STATIC_DIR = Path(_sys._MEIPASS) / "simmer" / "static"
else:
    STATIC_DIR = Path(str(files(__package__).joinpath("static")))

# One single-thread executor per UDID for captures.
# max_workers=1 means at most one hung Quartz thread per simulator, ever.
# Everything else (list_sims, tap, PTY reads) uses the default executor.
_udid_executors: dict[str, concurrent.futures.ThreadPoolExecutor] = {}

# Asyncio-side flag: True while a capture coroutine is awaiting for this UDID.
# Prevents queuing a second task before the first thread finishes or times out.
_capture_in_flight: dict[str, bool] = {}

# One live sim WS per UDID — evicts zombie handlers on reconnect.
_active_sim_ws: dict[str, web.WebSocketResponse] = {}

# Persistent PTY sessions — survive WS disconnects so iPad can reattach.
# Each entry: {master_fd, proc, buf (bytearray), ws (current client or None), cleanup_task}
_pty_sessions: dict[str, dict] = {}
_PTY_BUF_MAX = 64 * 1024   # 64 KB replay buffer sent on reattach
_PTY_SESSION_TTL = 30 * 60  # 30 min before idle session is reaped

def _is_landscape(udid: str) -> bool:
    """Detect orientation from live Simulator window bounds.
    Uses only Quartz (thread-safe) — no AppKit main-thread requirement.
    """
    import re
    try:
        import Quartz
    except ImportError:
        return False

    # kCGWindowOwnerName is always available without Screen Recording.
    try:
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
    except (KeyError, AttributeError):
        return False
    sim_wins = []
    for w in (window_list or []):
        if w.get("kCGWindowOwnerName") != "Simulator":
            continue
        bounds = w.get("kCGWindowBounds", {})
        width, height = bounds.get("Width", 0), bounds.get("Height", 0)
        if width < 100 or height < 100:
            continue
        sim_wins.append({"x": bounds.get("X", 0), "y": bounds.get("Y", 0), "w": width, "h": height})

    if not sim_wins:
        return False
    if len(sim_wins) == 1:
        return sim_wins[0]["w"] > sim_wins[0]["h"]

    # Multiple windows: use plist WindowCenter to identify this device's window.
    import plistlib
    path = Path.home() / "Library/Preferences/com.apple.iphonesimulator.plist"
    try:
        with open(path, "rb") as f:
            plist = plistlib.load(f)
        prefs = plist.get("DevicePreferences", {}).get(udid, {})
        m = re.match(r'\{([\d.]+),\s*([\d.]+)\}', prefs.get("WindowCenter", ""))
        if m:
            cx, cy = float(m.group(1)), float(m.group(2))
            for win in sim_wins:
                if abs(win["x"] + win["w"] / 2 - cx) < 200 and abs(win["y"] + win["h"] / 2 - cy) < 200:
                    return win["w"] > win["h"]
    except Exception:
        pass

    largest = max(sim_wins, key=lambda w: w["w"] * w["h"])
    return largest["w"] > largest["h"]


def _rotate_jpeg_ccw90(jpeg_bytes: bytes, quality: int) -> Optional[bytes]:
    """Rotate a JPEG 90° CCW using CoreGraphics (fast, in-memory, no extra deps)."""
    try:
        import AppKit
        import Quartz
        ns_data = AppKit.NSData.dataWithBytes_length_(jpeg_bytes, len(jpeg_bytes))
        src = Quartz.CGImageSourceCreateWithData(ns_data, None)
        if not src:
            return None
        img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        if not img:
            return None
        ow = Quartz.CGImageGetWidth(img)
        oh = Quartz.CGImageGetHeight(img)
        # Rotated canvas: portrait (ow×oh) → landscape (oh×ow)
        cs = Quartz.CGColorSpaceCreateDeviceRGB()
        ctx = Quartz.CGBitmapContextCreate(
            None, oh, ow, 8, oh * 4, cs, Quartz.kCGImageAlphaNoneSkipLast
        )
        if not ctx:
            return None
        # CCW 90°: rotate first, then translate so image lands in positive space
        Quartz.CGContextRotateCTM(ctx, math.pi / 2)
        Quartz.CGContextTranslateCTM(ctx, 0, -oh)
        Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, ow, oh), img)
        rotated = Quartz.CGBitmapContextCreateImage(ctx)
        if not rotated:
            return None
        out = AppKit.NSMutableData.data()
        dest = Quartz.CGImageDestinationCreateWithData(out, "public.jpeg", 1, None)
        if not dest:
            return None
        Quartz.CGImageDestinationAddImage(dest, rotated, {
            Quartz.kCGImageDestinationLossyCompressionQuality: quality / 100.0
        })
        Quartz.CGImageDestinationFinalize(dest)
        return bytes(out) if len(out) > 0 else None
    except Exception as e:
        print(f"[rotate_jpeg] {e}", flush=True)
        return None


@web.middleware
async def _cors_middleware(request: web.Request, handler) -> web.StreamResponse:
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def make_app(
    backend: Any,
    fps: int = 15,
    quality: int = 70,
    project_dir: Optional[str] = None,
    bundle_id: Optional[str] = None,
) -> web.Application:
    app = web.Application(middlewares=[_cors_middleware])
    app["backend"] = backend
    app["default_fps"] = fps
    app["default_quality"] = quality
    app["project_dir"] = project_dir or os.getcwd()
    app["bundle_id"] = bundle_id
    app.router.add_get("/", _index)
    app.router.add_get("/api/info", _info)
    app.router.add_post("/api/request-permissions", _request_permissions)
    app.router.add_get("/api/sims", _sims)
    app.router.add_get("/api/devices", _devices)
    app.router.add_post("/api/boot/{udid}", _boot)
    app.router.add_get("/ws/pty", _ws_pty)   # must be before /ws/{udid}
    app.router.add_get("/ws/{udid}", _ws)
    app.router.add_static("/css", STATIC_DIR / "css")
    app.router.add_static("/js", STATIC_DIR / "js")
    return app


async def _index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def _info(request: web.Request) -> web.Response:
    from .backend_base import has_screen_recording, has_accessibility, has_idb
    info: dict = {"mode": request.app["backend"].name}
    if request.app.get("bundle_id"):
        info["bundle_id"] = request.app["bundle_id"]
    info["permissions"] = {
        "screen_recording": has_screen_recording(),
        "accessibility": has_accessibility(),
        "idb": has_idb(),
    }
    return web.json_response(info)


async def _request_permissions(request: web.Request) -> web.Response:
    body = await request.json()
    perm = body.get("permission")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _do_request_permissions, perm)
    from .backend_base import has_screen_recording, has_accessibility
    return web.json_response({
        "screen_recording": has_screen_recording(),
        "accessibility": has_accessibility(),
    })


_PREF_URLS = {
    "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    "accessibility":    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
}

def _do_request_permissions(perm: str) -> None:
    url = _PREF_URLS.get(perm)
    if url:
        import subprocess
        subprocess.Popen(["open", url])


async def _run(fn, *args):
    """Run a blocking call in the default executor (list_sims, tap, drag, etc.)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


async def _capture(backend: Any, udid: str, quality: int) -> Optional[bytes]:
    """Capture one frame. Skips if a capture for this UDID is already in flight.

    Uses one single-thread executor per UDID so a hung Quartz call can never
    consume more than one OS thread per simulator, regardless of how many times
    the frame loop retries.
    """
    if _capture_in_flight.get(udid):
        return None  # thread still running from last attempt — skip this frame

    if udid not in _udid_executors:
        _udid_executors[udid] = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"cap-{udid[:8]}"
        )

    _capture_in_flight[udid] = True
    loop = asyncio.get_running_loop()
    # shield() lets the underlying thread future survive the wait_for timeout
    # so we can attempt to cancel a queued (not-yet-started) task afterward.
    fut = loop.run_in_executor(_udid_executors[udid], backend.capture, udid, quality)
    try:
        return await asyncio.wait_for(asyncio.shield(fut), timeout=3.0)
    except asyncio.TimeoutError:
        fut.cancel()  # no-op if thread already running, cancels if still queued
        return None
    except Exception:
        return None
    finally:
        _capture_in_flight[udid] = False


async def _devices(request: web.Request) -> web.Response:
    devices = await _run(list_available_devices)
    return web.json_response(devices)


async def _boot(request: web.Request) -> web.Response:
    udid = request.match_info["udid"]
    await _run(boot_sim, udid)
    return web.json_response({"ok": True})


async def _sims(request: web.Request) -> web.Response:
    backend = request.app["backend"]
    bundle_id = request.app.get("bundle_id")

    sims = await _run(backend.list_sims)

    if bundle_id:
        flags = await asyncio.gather(*[_run(sim_has_app, s.udid, bundle_id) for s in sims])
    else:
        flags = [False] * len(sims)

    result = [{**s.to_dict(), "project_app": flag} for s, flag in zip(sims, flags)]
    return web.json_response(result)


async def _ws(request: web.Request) -> web.WebSocketResponse:
    udid = request.match_info["udid"]
    backend = request.app["backend"]

    # Upgrade the WebSocket immediately so the client isn't stuck in CONNECTING
    # while we run the simctl subprocess.
    ws = web.WebSocketResponse(heartbeat=15)
    try:
        await ws.prepare(request)
    except (AssertionError, ConnectionResetError):
        return ws  # client disconnected before WS upgrade finished

    sim = await _run(lambda: next((s for s in backend.list_sims() if s.udid == udid), None))
    state = {
        "fps": int(request.rel_url.query.get("fps", request.app["default_fps"])),
        "quality": int(request.rel_url.query.get("quality", request.app["default_quality"])),
        "data_saver": request.rel_url.query.get("data_saver", "0") == "1",
        "dev_w": sim.width if sim else 390,
        "dev_h": sim.height if sim else 844,
    }

    # Evict any zombie handler for this UDID immediately
    old = _active_sim_ws.pop(udid, None)
    if old is not None and not old.closed:
        asyncio.ensure_future(old.close())
    _active_sim_ws[udid] = ws

    last_hash: list[Optional[str]] = [None]

    # Tell newly connected client the current orientation so page refreshes work
    if await _run(_is_landscape, udid):
        await ws.send_str(json.dumps({"type": "rotated"}))

    # simctl returns portrait-sized JPEGs regardless of device orientation; rotate server-side.
    _needs_rotation = "simctl" in backend.name

    async def frame_loop() -> None:
        send_failures = 0
        while not ws.closed:
            frame = await _capture(backend, udid, state["quality"])
            if frame:
                if _needs_rotation and await _run(_is_landscape, udid):
                    rotated = await _run(_rotate_jpeg_ccw90, frame, state["quality"])
                    if rotated:
                        frame = rotated
                if state["data_saver"]:
                    h = hashlib.md5(frame).hexdigest()
                    if h == last_hash[0]:
                        await asyncio.sleep(1.0 / state["fps"])
                        continue
                    last_hash[0] = h
                try:
                    await ws.send_bytes(frame)
                    send_failures = 0
                except Exception:
                    send_failures += 1
                    # After 3 consecutive send failures the client is gone — close cleanly
                    if send_failures >= 3:
                        await ws.close()
                        break
            await asyncio.sleep(1.0 / state["fps"])

    task = asyncio.create_task(frame_loop())
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await _handle_input(json.loads(msg.data), udid, state, backend, ws)
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                break
    finally:
        if _active_sim_ws.get(udid) is ws:
            _active_sim_ws.pop(udid, None)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return ws


async def _handle_input(data: dict, udid: str, state: dict, backend: Any, ws: Optional[web.WebSocketResponse] = None) -> None:
    t = data.get("type")
    if t not in ("tap", "drag"):
        print(f"[input] {t}", flush=True)

    if t == "settings":
        if "fps" in data:
            state["fps"] = max(1, min(60, int(data["fps"])))
        if "quality" in data:
            state["quality"] = max(10, min(95, int(data["quality"])))
        if "data_saver" in data:
            state["data_saver"] = bool(data["data_saver"])
        if "dev_w" in data:
            state["dev_w"] = int(data["dev_w"])
        if "dev_h" in data:
            state["dev_h"] = int(data["dev_h"])
        return

    if t == "tap":
        await _run(backend.tap, udid, data["x"], data["y"], state["dev_w"], state["dev_h"])
    elif t == "drag":
        await _run(backend.drag, udid, data["x1"], data["y1"], data["x2"], data["y2"], state["dev_w"], state["dev_h"])
    elif t == "key":
        await _run(backend.key, udid, data.get("key", ""))
    elif t == "text":
        await _run(backend.text, udid, data.get("text", ""))
    elif t == "home":
        await _run(backend.home, udid)
    elif t == "rotate":
        print(f"[server] rotate received udid={udid[:8]}", flush=True)
        try:
            await _run(backend.rotate, udid)
            if ws and not ws.closed:
                await ws.send_str(json.dumps({"type": "rotated"}))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[server] rotate error: {e}", flush=True)
    elif t == "appearance":
        await _run(backend.appearance, udid, data.get("mode", "dark"))


async def _pty_reader_loop(session_id: str) -> None:
    """Reads PTY output and fans it to the current WS client (if any).
    Runs independently of any single WS connection so the shell survives disconnects.
    """
    session = _pty_sessions.get(session_id)
    if not session:
        return
    loop = asyncio.get_running_loop()
    master_fd = session["master_fd"]

    while session_id in _pty_sessions:
        fut: asyncio.Future[bytes] = loop.create_future()

        def _readable(fd=master_fd, f=fut):
            loop.remove_reader(fd)
            try:
                data = os.read(fd, 4096)
                if not f.done():
                    f.set_result(data)
            except OSError as exc:
                if not f.done():
                    f.set_exception(exc)

        loop.add_reader(master_fd, _readable)
        try:
            data = await fut
        except (OSError, asyncio.CancelledError):
            loop.remove_reader(master_fd)
            break

        if not data:
            break

        # Append to replay buffer, keep last _PTY_BUF_MAX bytes
        session["buf"].extend(data)
        excess = len(session["buf"]) - _PTY_BUF_MAX
        if excess > 0:
            del session["buf"][:excess]

        # Forward to connected client
        ws = session.get("ws")
        if ws and not ws.closed:
            try:
                await ws.send_bytes(data)
            except Exception:
                session["ws"] = None

    # Shell exited or PTY error — remove session
    _pty_sessions.pop(session_id, None)


async def _pty_cleanup(session_id: str) -> None:
    """Called after _PTY_SESSION_TTL seconds of no client — tears down the shell."""
    await asyncio.sleep(_PTY_SESSION_TTL)
    session = _pty_sessions.pop(session_id, None)
    if not session:
        return
    loop = asyncio.get_running_loop()
    try:
        loop.remove_reader(session["master_fd"])
    except Exception:
        pass
    try:
        os.close(session["master_fd"])
    except OSError:
        pass
    try:
        session["proc"].kill()
    except Exception:
        pass
    try:
        session["proc"].wait()
    except Exception:
        pass
    print(f"[pty] session {session_id[:8]} expired after {_PTY_SESSION_TTL//60} min", flush=True)


async def _ws_pty(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    loop = asyncio.get_running_loop()

    session_id = request.rel_url.query.get("session", "")
    session = _pty_sessions.get(session_id)

    if session is None:
        # New session — spawn a shell
        cols = int(request.rel_url.query.get("cols", 220))
        rows = int(request.rel_url.query.get("rows", 50))
        cwd = request.app.get("project_dir") or os.path.expanduser("~")
        shell = os.environ.get("SHELL", "/bin/zsh")

        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

        proc = subprocess.Popen(
            [shell, "-l"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True,
            preexec_fn=os.setsid,
            cwd=cwd,
            env={**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor"},
        )
        os.close(slave_fd)

        session_id = uuid.uuid4().hex
        session = {"master_fd": master_fd, "proc": proc, "buf": bytearray(), "ws": None, "cleanup_task": None}
        _pty_sessions[session_id] = session
        asyncio.ensure_future(_pty_reader_loop(session_id))

        # Tell the client its session ID so it can reattach after disconnects
        await ws.send_str(json.dumps({"type": "session", "id": session_id}))
    else:
        # Reattaching to existing session
        ct = session.get("cleanup_task")
        if ct:
            ct.cancel()
            session["cleanup_task"] = None
        # Replay recent output so the screen isn't blank
        if session["buf"]:
            await ws.send_bytes(bytes(session["buf"]))
        print(f"[pty] reattached to session {session_id[:8]}", flush=True)

    session["ws"] = ws

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                try:
                    os.write(session["master_fd"], bytes(msg.data))
                except OSError:
                    break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    cmd = json.loads(msg.data)
                    if cmd.get("type") == "resize":
                        c, r = int(cmd["cols"]), int(cmd["rows"])
                        fcntl.ioctl(session["master_fd"], termios.TIOCSWINSZ, struct.pack("HHHH", r, c, 0, 0))
                        try:
                            os.killpg(os.getpgid(session["proc"].pid), signal.SIGWINCH)
                        except ProcessLookupError:
                            pass
                except Exception:
                    pass
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                break
    finally:
        if session.get("ws") is ws:
            session["ws"] = None
        # Keep session alive for _PTY_SESSION_TTL, then clean up
        if session_id in _pty_sessions:
            session["cleanup_task"] = asyncio.ensure_future(_pty_cleanup(session_id))

    return ws


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _tailscale_info() -> dict:
    import json as _json
    info: dict = {}

    ts_candidates = [
        "tailscale",
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ]
    ts_bin = next((c for c in ts_candidates if _which(c)), None)

    if ts_bin:
        try:
            r = subprocess.run([ts_bin, "ip", "-4"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                info["ip"] = r.stdout.strip()
        except Exception:
            pass
        try:
            r = subprocess.run([ts_bin, "status", "--json"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                dns = _json.loads(r.stdout).get("Self", {}).get("DNSName", "").rstrip(".")
                if dns:
                    info["hostname"] = dns
        except Exception:
            pass

    if "ip" not in info:
        try:
            import ipaddress
            r = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            addr = ipaddress.IPv4Address(parts[1])
                            if addr in ipaddress.IPv4Network("100.64.0.0/10"):
                                info["ip"] = str(addr)
                                break
                        except Exception:
                            pass
        except Exception:
            pass

    return info


def _which(cmd: str) -> bool:
    import shutil as _shutil
    if os.path.isabs(cmd):
        return os.path.isfile(cmd) and os.access(cmd, os.X_OK)
    return _shutil.which(cmd) is not None


async def run(
    backend: Any,
    port: int = 8080,
    fps: int = 15,
    quality: int = 70,
    project_dir: Optional[str] = None,
    bundle_id: Optional[str] = None,
) -> None:
    app = make_app(backend, fps=fps, quality=quality, project_dir=project_dir, bundle_id=bundle_id)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"\nsimmer  [{backend.name}]")
    print("─" * 40)

    local_ip = _local_ip()
    ts = _tailscale_info()

    urls = []
    urls.append(("localhost", f"http://localhost:{port}"))
    if local_ip:
        urls.append(("local network", f"http://{local_ip}:{port}"))
    if "ip" in ts:
        urls.append(("tailscale IP", f"http://{ts['ip']}:{port}"))
    if "hostname" in ts:
        urls.append(("tailscale host", f"http://{ts['hostname']}:{port}"))

    label_w = max(len(label) for label, _ in urls)
    for label, url in urls:
        tag = "  ← use this on iPad" if "tailscale" in label else ""
        print(f"  {label:<{label_w}}  {url}{tag}")

    if bundle_id:
        print(f"\n  Project: {bundle_id}")

    if not ts:
        print("\n  Tailscale not detected — iPad access over the internet won't work.")
        print("  Install: https://tailscale.com/download/mac")

    print("\n  HTTP is fine — Tailscale encrypts the tunnel, no HTTPS needed.")
    print("─" * 40 + "\n")

    # OS-level signal handlers — fire even when the event loop is blocked
    signal.signal(signal.SIGINT,  lambda *_: os._exit(0))
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))

    await asyncio.Event().wait()  # run forever
