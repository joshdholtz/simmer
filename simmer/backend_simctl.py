"""Compat backend: simctl screenshot + idb injection.
No macOS permissions required. Needs idb installed:
  brew tap facebook/fb && brew install idb-companion
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .backend_base import SimDevice, logical_size

name = "compat (simctl+idb)"

_IDB = shutil.which("idb") or "idb"


# ── Sim discovery ──────────────────────────────────────────────────────────────


def list_sims() -> list[SimDevice]:
    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "--json"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    sims = []
    for devices in json.loads(result.stdout).get("devices", {}).values():
        for dev in devices:
            if dev.get("state") != "Booted":
                continue
            size = _size_for_device(dev["name"], dev["udid"])
            if size:
                sims.append(
                    SimDevice(
                        udid=dev["udid"],
                        name=dev["name"],
                        width=size[0],
                        height=size[1],
                    )
                )
    return sims


def _size_for_device(name: str, udid: str) -> Optional[tuple[int, int]]:
    # iPad simulator names change often and broad fallbacks like "iPad" can be
    # stale. Measure booted iPads so idb tap coordinates match the live screen.
    if "ipad" in name.lower():
        return _measure(udid) or logical_size(name)
    return logical_size(name) or _measure(udid)


def _logical_size_from_screenshot(w: int, h: int) -> tuple[int, int]:
    short = min(w, h)
    # iPads are 2x even when their screenshots are wider than iPhone 3x
    # screenshots. The old width >= 900 => 3x heuristic made modern iPads
    # report ~550pt wide, so idb taps landed far from the browser tap.
    scale = 2 if short < 900 or short // 2 >= 744 else 3
    return w // scale, h // scale


def _measure(udid: str) -> Optional[tuple[int, int]]:
    """Get logical size by capturing a PNG and dividing by estimated scale."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = f.name
    try:
        r = subprocess.run(["xcrun", "simctl", "io", udid, "screenshot", tmp], capture_output=True)
        if r.returncode != 0:
            return None
        data = Path(tmp).read_bytes()
        if len(data) < 24 or data[:4] != b"\x89PNG":
            return None
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        return _logical_size_from_screenshot(w, h)
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── Capture ────────────────────────────────────────────────────────────────────


def capture(udid: str, quality: int = 70) -> Optional[bytes]:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        tmp = f.name
    try:
        r = subprocess.run(
            ["xcrun", "simctl", "io", udid, "screenshot", "--type", "jpeg", tmp],
            capture_output=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        return Path(tmp).read_bytes()
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── Input injection via idb ────────────────────────────────────────────────────


def _idb(*args: str) -> None:
    subprocess.run([_IDB, *args], capture_output=True)


def tap(udid: str, nx: float, ny: float, dev_w: int, dev_h: int) -> None:
    _idb("ui", "tap", str(int(nx * dev_w)), str(int(ny * dev_h)), "--udid", udid)


def drag(udid: str, nx1: float, ny1: float, nx2: float, ny2: float, dev_w: int, dev_h: int) -> None:
    _idb(
        "ui",
        "swipe",
        str(int(nx1 * dev_w)),
        str(int(ny1 * dev_h)),
        str(int(nx2 * dev_w)),
        str(int(ny2 * dev_h)),
        "--udid",
        udid,
    )


_KEY_MAP: dict[str, str] = {
    "backspace": "delete",
    "delete": "delete",
    "return": "return",
    "enter": "return",
    "tab": "tab",
    "escape": "escape",
    "space": "space",
    "arrowleft": "left",
    "arrowright": "right",
    "arrowup": "up",
    "arrowdown": "down",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "pagedown": "page_down",
}


def key(udid: str, k: str) -> None:
    mapped = _KEY_MAP.get(k.lower())
    if mapped:
        _idb("key", mapped, "--udid", udid)


def text(udid: str, t: str) -> None:
    _idb("text", t, "--udid", udid)


def home(udid: str) -> None:
    _idb("ui", "button", "HOME", "--udid", udid)


_ROTATE_LOG = "/tmp/simmer_rotate.log"


def _rlog(*args) -> None:
    import datetime

    msg = " ".join(str(a) for a in args)
    line = f"{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n"
    print(line, end="", flush=True)
    try:
        with open(_ROTATE_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def rotate(udid: str) -> None:
    import time

    import AppKit
    import Quartz

    Path(_ROTATE_LOG).write_text("")  # clear on each attempt
    _rlog(f"backend=simctl udid={udid[:8]}")

    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "--json"],
        capture_output=True,
        text=True,
    )
    dev_name = None
    for devices in json.loads(result.stdout).get("devices", {}).values():
        for dev in devices:
            if dev.get("udid") == udid:
                dev_name = dev["name"]
                break
        if dev_name:
            break
    if not dev_name:
        _rlog("udid not found in simctl list")
        return

    _rlog(f"dev_name={dev_name!r}")

    apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.iphonesimulator")
    if not apps:
        _rlog("Simulator.app not running")
        return
    apps[0].activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    time.sleep(0.15)

    # Find window via Quartz (no Accessibility required)
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    all_sim_wins = [w for w in (window_list or []) if w.get("kCGWindowOwnerName") == "Simulator"]
    _rlog(f"Simulator windows on screen: {[(w.get('kCGWindowName'), w.get('kCGWindowBounds')) for w in all_sim_wins]}")

    win = None
    for w in all_sim_wins:
        if w.get("kCGWindowName", "") != dev_name:
            continue
        bounds = w.get("kCGWindowBounds", {})
        if bounds.get("Width", 0) > 100:
            win = {
                "x": int(bounds["X"]),
                "y": int(bounds["Y"]),
                "width": int(bounds["Width"]),
                "height": int(bounds["Height"]),
            }
            break

    _rlog(f"target window: {win}")

    # Use the compiled Swift helper which has its own Accessibility identity.
    # On first run macOS prompts the user to grant it — one-time setup.
    import shutil

    # Check PATH first (installed via Homebrew), then fall back to dev repo root
    helper_path = shutil.which("rotate_sim") or str(Path(__file__).parent.parent / "rotate_sim")
    helper = Path(helper_path)
    if not helper.exists():
        _rlog("rotate_sim binary not found — run: swiftc rotate_sim.swift -o rotate_sim")
        return

    # Pass window center coordinates so the Swift helper can click the right
    # window without needing Screen Recording permission itself.
    cmd = [str(helper), dev_name]
    if win:
        cx = win["x"] + win["width"] // 2
        cy = win["y"] + win["height"] // 2
        cmd += [str(cx), str(cy)]
        _rlog(f"passing window center ({cx}, {cy}) to rotate_sim")

    _rlog(f"running {helper} {dev_name!r}")
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=8,
    )
    _rlog(f"rotate_sim rc={r.returncode} stdout={r.stdout.strip()!r} stderr={r.stderr.strip()!r}")
    if r.returncode == 2:
        print(
            "\n[rotate] rotate_sim needs Accessibility permission.\n"
            "  macOS has opened System Settings → Privacy & Security → Accessibility.\n"
            "  Click '+', navigate to simmer/rotate_sim, and add it.\n"
            "  Then tap Rotate again.\n",
            flush=True,
        )
    _rlog("done")


def appearance(udid: str, mode: str) -> None:
    subprocess.run(["xcrun", "simctl", "ui", udid, "appearance", mode], capture_output=True)
