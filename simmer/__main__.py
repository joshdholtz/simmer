import argparse
import asyncio
import os

from .backend_base import detect_bundle_id, has_accessibility, has_idb, has_screen_recording, has_adb
from .server import run


def _select_backend(mode: str):
    if mode == "android":
        from . import backend_adb
        return backend_adb.AdbBackend()
    if mode == "fast":
        from . import backend_quartz
        return backend_quartz
    if mode == "compat":
        from . import backend_simctl
        return backend_simctl

    if has_screen_recording() and has_accessibility():
        print("Permissions detected — using fast mode (Quartz)")
        from . import backend_quartz
        return backend_quartz

    if has_idb():
        print("Using compat mode (simctl + idb)")
        from . import backend_simctl
        return backend_simctl

    print("Warning: Screen Recording/Accessibility not granted and idb not found.")
    print("  Fast mode:   grant permissions in System Settings → Privacy & Security")
    print("  Compat mode: brew tap facebook/fb && brew install idb-companion")
    print("Attempting compat mode anyway (capture may fail)...")
    from . import backend_simctl
    return backend_simctl


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream iOS Simulator to iPad browser")
    parser.add_argument("--port", type=int, default=4040)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument(
        "--mode",
        choices=["auto", "fast", "compat", "android"],
        default="auto",
        help="auto | fast: Quartz | compat: simctl+idb | android: adb emulators",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project directory for Xcode bundle ID detection and terminal CWD (default: CWD)",
    )
    args = parser.parse_args()

    backend = _select_backend(args.mode)
    project_dir = args.project_dir or os.getcwd()
    bundle_id = detect_bundle_id(project_dir)
    if bundle_id:
        print(f"Project bundle ID detected: {bundle_id}")

    asyncio.run(run(
        backend=backend,
        port=args.port,
        fps=args.fps,
        quality=args.quality,
        project_dir=project_dir,
        bundle_id=bundle_id,
    ))


if __name__ == "__main__":
    main()
