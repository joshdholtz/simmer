from __future__ import annotations
import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


@dataclasses.dataclass
class SimDevice:
    udid: str
    name: str
    width: int   # logical points
    height: int  # logical points

    def to_dict(self) -> dict:
        return {"id": self.udid, "name": self.name, "width": self.width, "height": self.height}


@runtime_checkable
class Backend(Protocol):
    name: str

    def list_sims(self) -> list[SimDevice]: ...
    def capture(self, udid: str, quality: int) -> Optional[bytes]: ...
    def tap(self, udid: str, nx: float, ny: float, dev_w: int, dev_h: int) -> None: ...
    def drag(self, udid: str, nx1: float, ny1: float, nx2: float, ny2: float, dev_w: int, dev_h: int) -> None: ...
    def key(self, udid: str, k: str) -> None: ...
    def text(self, udid: str, t: str) -> None: ...


def has_screen_recording() -> bool:
    try:
        import Quartz
        return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:
        return False


def has_accessibility() -> bool:
    try:
        import Quartz
        return bool(Quartz.AXIsProcessTrusted())
    except Exception:
        return False


def has_idb() -> bool:
    return shutil.which("idb") is not None

def has_adb() -> bool:
    return shutil.which("adb") is not None


def detect_bundle_id(project_dir: Optional[str] = None) -> Optional[str]:
    root = Path(project_dir).expanduser().resolve() if project_dir else Path.cwd()
    for pattern in ("*.xcodeproj", "*/*.xcodeproj"):
        for xcodeproj in sorted(root.glob(pattern)):
            pbxproj = xcodeproj / "project.pbxproj"
            if not pbxproj.exists():
                continue
            try:
                text = pbxproj.read_text(errors="ignore")
            except OSError:
                continue
            for m in re.finditer(r'PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;"\s]+)\s*;', text):
                bid = m.group(1).strip()
                if bid.startswith("$(") or "test" in bid.lower() or "extension" in bid.lower():
                    continue
                return bid
    return None


def list_available_devices() -> list[dict]:
    """Return shutdown simulator devices that can be booted."""
    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    devices = []
    for runtime, devs in json.loads(result.stdout).get("devices", {}).items():
        for dev in devs:
            if dev.get("state") != "Shutdown":
                continue
            if not dev.get("isAvailable", True):
                continue
            size = logical_size(dev["name"])
            if not size:
                continue
            devices.append({
                "id": dev["udid"],
                "name": dev["name"],
                "width": size[0],
                "height": size[1],
                "runtime": runtime.split(".")[-1].replace("-", " "),
            })
    return devices


def boot_sim(udid: str) -> None:
    subprocess.run(["xcrun", "simctl", "boot", udid], capture_output=True, timeout=60)


def sim_has_app(udid: str, bundle_id: str) -> bool:
    try:
        r = subprocess.run(
            ["xcrun", "simctl", "listapps", udid],
            capture_output=True, text=True, timeout=5,
        )
        return bundle_id in r.stdout
    except Exception:
        return False


# Logical screen sizes for common simulator devices
_LOGICAL_SIZES: dict[str, tuple[int, int]] = {
    "iphone se (1st": (320, 568),
    "iphone se": (375, 667),
    "iphone 6s plus": (414, 736), "iphone 7 plus": (414, 736), "iphone 8 plus": (414, 736),
    "iphone 6": (375, 667), "iphone 7": (375, 667), "iphone 8": (375, 667),
    "iphone x": (375, 812), "iphone xr": (414, 896),
    "iphone xs max": (414, 896), "iphone xs": (375, 812),
    "iphone 11 pro max": (414, 896), "iphone 11 pro": (375, 812), "iphone 11": (414, 896),
    "iphone 12 mini": (360, 780), "iphone 12 pro max": (428, 926), "iphone 12 pro": (390, 844), "iphone 12": (390, 844),
    "iphone 13 mini": (375, 812), "iphone 13 pro max": (428, 926), "iphone 13 pro": (390, 844), "iphone 13": (390, 844),
    "iphone 14 pro max": (430, 932), "iphone 14 pro": (393, 852), "iphone 14 plus": (428, 926), "iphone 14": (390, 844),
    "iphone 15 pro max": (430, 932), "iphone 15 pro": (393, 852), "iphone 15 plus": (430, 932), "iphone 15": (393, 852),
    "iphone 16 pro max": (440, 956), "iphone 16 pro": (402, 874), "iphone 16 plus": (430, 932), "iphone 16e": (393, 852), "iphone 16": (393, 852),
    "iphone 17 pro max": (440, 956), "iphone 17 pro": (402, 874), "iphone 17 air": (393, 852), "iphone air": (393, 852), "iphone 17e": (393, 852), "iphone 17": (393, 852),
    "ipad mini (6": (744, 1133), "ipad mini": (768, 1024),
    "ipad air (5": (820, 1180), "ipad air (4": (820, 1180), "ipad air": (768, 1024),
    "ipad pro (12.9": (1024, 1366), "ipad pro (11": (834, 1194),
    "ipad (10": (820, 1180), "ipad": (768, 1024),
}


def logical_size(device_name: str) -> Optional[tuple[int, int]]:
    n = device_name.lower()
    for key in sorted(_LOGICAL_SIZES, key=len, reverse=True):
        if key in n:
            return _LOGICAL_SIZES[key]
    return None
