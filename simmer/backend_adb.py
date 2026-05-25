from __future__ import annotations
import os
import re
import shutil
import subprocess
from typing import Optional

from .backend_base import SimDevice

name = "android (adb)"

_SDK_ROOTS = [
    os.environ.get("ANDROID_HOME", ""),
    os.environ.get("ANDROID_SDK_ROOT", ""),
    os.path.expanduser("~/Library/Android/sdk"),
]


def _find_adb() -> str:
    # Prefer SDK-bundled adb — it shares a daemon with the running emulator.
    # Homebrew's standalone adb starts a separate daemon and won't see emulators.
    for root in _SDK_ROOTS:
        candidate = os.path.join(root, "platform-tools", "adb")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("adb") or "adb"


def _find_emulator() -> str:
    for root in _SDK_ROOTS:
        candidate = os.path.join(root, "emulator", "emulator")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("emulator") or "emulator"


_ADB = _find_adb()
_EMULATOR = _find_emulator()


def _adb(serial: str, *args, timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run([_ADB, "-s", serial, *args], capture_output=True, timeout=timeout)


def _parse_size(text: str) -> Optional[tuple[int, int]]:
    for line in text.splitlines():
        m = re.search(r"(\d+)x(\d+)", line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None



def _device_name(serial: str) -> str:
    try:
        avd = _adb(serial, "emu", "avd", "name", timeout=3)
        if avd.returncode == 0:
            name = avd.stdout.decode().strip().splitlines()[0].strip()
            if name:
                return name.replace("_", " ")
    except Exception:
        pass
    try:
        model = _adb(serial, "shell", "getprop", "ro.product.model", timeout=3)
        name = model.stdout.decode().strip()
        if name:
            return name
    except Exception:
        pass
    return serial


def list_sims() -> list[SimDevice]:
    try:
        r = subprocess.run([_ADB, "devices"], capture_output=True, text=True, timeout=3)
    except Exception:
        return []

    devices = []
    for line in r.stdout.splitlines()[1:]:
        if "\t" not in line:
            continue
        serial, state = line.split("\t", 1)
        serial, state = serial.strip(), state.strip()
        if state != "device" or not serial.startswith("emulator-"):
            continue
        try:
            size_r = _adb(serial, "shell", "wm", "size", timeout=4)
            size   = _parse_size(size_r.stdout.decode())
            if not size:
                continue
            pw, ph = size
            # Store physical pixels directly — screencap returns physical-pixel PNGs
            # so using physical pixels for tap/drag avoids density rounding errors.
            devices.append(SimDevice(
                udid=serial,
                name=_device_name(serial),
                width=min(pw, ph),
                height=max(pw, ph),
            ))
        except Exception:
            continue
    return devices


def list_available_avds() -> list[dict]:
    """Return AVDs that exist but aren't currently running."""
    running = {s.udid for s in list_sims()}
    try:
        r = subprocess.run([_EMULATOR, "-list-avds"], capture_output=True, text=True, timeout=5)
        avds = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []
    # We can't know the serial before boot, so flag by AVD name
    return [{"name": a.replace("_", " "), "avd": a} for a in avds]


def boot_avd(avd: str) -> None:
    subprocess.Popen(
        [_EMULATOR, "-avd", avd, "-no-snapshot-load"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class AdbBackend:
    name = "android (adb)"

    def list_sims(self) -> list[SimDevice]:
        return list_sims()

    def capture(self, udid: str, quality: int) -> Optional[bytes]:
        try:
            r = _adb(udid, "exec-out", "screencap", "-p", timeout=6)
            if r.returncode != 0 or not r.stdout:
                return None
            # Send raw PNG — browser decodes it fine
            return r.stdout
        except Exception:
            return None

    def tap(self, udid: str, nx: float, ny: float, dev_w: int, dev_h: int) -> None:
        # dev_w/h are physical pixels (screencap resolution) — no density conversion needed
        x = int(nx * dev_w)
        y = int(ny * dev_h)
        try:
            _adb(udid, "shell", "input", "tap", str(x), str(y))
        except Exception:
            pass

    def drag(self, udid: str, nx1: float, ny1: float, nx2: float, ny2: float, dev_w: int, dev_h: int) -> None:
        x1, y1 = int(nx1 * dev_w), int(ny1 * dev_h)
        x2, y2 = int(nx2 * dev_w), int(ny2 * dev_h)
        try:
            _adb(udid, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "300")
        except Exception:
            pass

    def key(self, udid: str, k: str) -> None:
        kc = _KEYMAP.get(k.lower())
        if kc:
            try:
                _adb(udid, "shell", "input", "keyevent", kc)
            except Exception:
                pass

    def text(self, udid: str, t: str) -> None:
        safe = t.replace("\\", "\\\\").replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        try:
            _adb(udid, "shell", "input", "text", safe)
        except Exception:
            pass

    def home(self, udid: str) -> None:
        try:
            _adb(udid, "shell", "input", "keyevent", "KEYCODE_HOME")
        except Exception:
            pass

    def rotate(self, udid: str) -> None:
        try:
            r = _adb(udid, "shell", "settings", "get", "system", "user_rotation", timeout=3)
            current = int(r.stdout.decode().strip() or "0")
            next_rot = (current + 1) % 4
            _adb(udid, "shell", "settings", "put", "system", "user_rotation", str(next_rot))
        except Exception:
            pass

    def appearance(self, udid: str, mode: str) -> None:
        # Android 10+ supports dark mode via UI mode
        night = "yes" if mode == "dark" else "no"
        try:
            _adb(udid, "shell", "cmd", "uimode", "night", night)
        except Exception:
            pass


_KEYMAP = {
    "home":    "KEYCODE_HOME",
    "back":    "KEYCODE_BACK",
    "return":  "KEYCODE_ENTER",
    "delete":  "KEYCODE_DEL",
    "escape":  "KEYCODE_ESCAPE",
    "space":   "KEYCODE_SPACE",
    "tab":     "KEYCODE_TAB",
}

