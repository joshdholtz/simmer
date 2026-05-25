from __future__ import annotations

import shutil
import subprocess


def press_home(udid: str) -> bool:
    """Press iOS Simulator Home without relying on macOS Accessibility.

    idb's HOME button is the closest simulator-level input. If idb is not
    available or its companion is not connected, launching SpringBoard is a
    practical simctl fallback that returns the device to the home screen.
    """
    idb = shutil.which("idb")
    if idb:
        try:
            result = subprocess.run(
                [idb, "ui", "button", "HOME", "--udid", udid],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["xcrun", "simctl", "launch", udid, "com.apple.springboard"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False
