import argparse
import asyncio
import os
import signal
import subprocess
import time

from .backend_base import (
    detect_bundle_id,
    has_accessibility,
    has_adb,
    has_idb,
    has_screen_recording,
)
from .server import run


def _select_backend(mode: str):
    if mode == "fast":
        from . import backend_quartz

        ios = backend_quartz
    elif mode == "compat":
        from . import backend_simctl

        ios = backend_simctl
    elif has_screen_recording() and has_accessibility():
        print("Permissions detected — using fast mode (Quartz)")
        from . import backend_quartz

        ios = backend_quartz
    elif has_idb():
        print("Using compat mode (simctl + idb)")
        from . import backend_simctl

        ios = backend_simctl
    else:
        print("Warning: Screen Recording/Accessibility not granted and idb not found.")
        print("  Fast mode:   grant permissions in System Settings → Privacy & Security")
        print("  Compat mode: brew tap facebook/fb && brew install idb-companion")
        print("Attempting compat mode anyway (capture may fail)...")
        from . import backend_simctl

        ios = backend_simctl

    backends = [ios]
    if has_adb():
        from . import backend_adb

        backends.append(backend_adb.AdbBackend())
    else:
        print("Android emulators: install Android Studio for adb support")

    if len(backends) == 1:
        return ios

    from .backend_multi import MultiBackend

    return MultiBackend(backends)


def _kill_port(port: int) -> int:
    try:
        result = subprocess.run(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return 0

    pids = [int(p) for p in result.stdout.split() if p.isdigit()]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    if pids:
        time.sleep(0.2)

    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    return len(pids)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stream iOS Simulator to iPad browser")
    parser.add_argument("--port", type=int, default=4040)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument("--kill", action="store_true", help="stop the simmer instance listening on --port")
    parser.add_argument(
        "--mode",
        choices=["auto", "fast", "compat"],
        default="auto",
        help="auto | fast: Quartz | compat: simctl+idb",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project directory for Xcode bundle ID detection and terminal CWD (default: CWD)",
    )
    args = parser.parse_args(argv)

    if args.kill:
        count = _kill_port(args.port)
        print(f"Stopped {count} simmer process{'es' if count != 1 else ''}.")
        return

    backend = _select_backend(args.mode)
    project_dir = args.project_dir or os.getcwd()
    bundle_id = detect_bundle_id(project_dir)
    if bundle_id:
        print(f"Project bundle ID detected: {bundle_id}")

    asyncio.run(
        run(
            backend=backend,
            port=args.port,
            fps=args.fps,
            quality=args.quality,
            project_dir=project_dir,
            bundle_id=bundle_id,
        )
    )


if __name__ == "__main__":
    main()
