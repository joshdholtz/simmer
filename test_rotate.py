#!/usr/bin/env python3
"""Run this from your terminal to test the Simulator rotate approach.
   python3 test_rotate.py
"""
import subprocess, json, time
import AppKit
import ApplicationServices as AS

# ── find a booted sim ─────────────────────────────────────────────────────────
result = subprocess.run(
    ["xcrun", "simctl", "list", "devices", "--json"],
    capture_output=True, text=True,
)
booted = []
for devices in json.loads(result.stdout).get("devices", {}).values():
    for dev in devices:
        if dev.get("state") == "Booted":
            booted.append(dev)

if not booted:
    print("No booted simulators found.")
    exit(1)

for i, d in enumerate(booted):
    print(f"  [{i}] {d['name']}  ({d['udid'][:8]})")

idx = int(input("Pick simulator index: ") or "0")
dev = booted[idx]
udid = dev["udid"]
dev_name = dev["name"]
print(f"\nTarget: {dev_name!r}  udid={udid[:8]}")

# ── get Simulator AX element ──────────────────────────────────────────────────
apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
    "com.apple.iphonesimulator"
)
if not apps:
    print("Simulator app not running.")
    exit(1)

apps[0].activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
time.sleep(0.2)

pid = apps[0].processIdentifier()
ax_app = AS.AXUIElementCreateApplication(pid)

# ── raise the right window ────────────────────────────────────────────────────
err, windows = AS.AXUIElementCopyAttributeValue(ax_app, "AXWindows", None)
print(f"\nAXWindows err={err}  count={len(windows or [])}")
for w in (windows or []):
    _, t = AS.AXUIElementCopyAttributeValue(w, "AXTitle", None)
    print(f"  window title: {t!r}")
    if t and dev_name in t:
        print("  → raising this window")
        AS.AXUIElementPerformAction(w, "AXRaise")
        time.sleep(0.15)

# ── walk Device menu ──────────────────────────────────────────────────────────
err, menu_bar = AS.AXUIElementCopyAttributeValue(ax_app, "AXMenuBar", None)
print(f"\nAXMenuBar err={err}")
if err:
    print("Cannot access menu bar — is Accessibility granted for Terminal/Python?")
    exit(1)

_, menus = AS.AXUIElementCopyAttributeValue(menu_bar, "AXChildren", None)
print("Top-level menus:", [AS.AXUIElementCopyAttributeValue(m, "AXTitle", None)[1] for m in (menus or [])])

for menu in (menus or []):
    _, title = AS.AXUIElementCopyAttributeValue(menu, "AXTitle", None)
    if title != "Device":
        continue
    print(f"\nFound 'Device' menu. Getting children…")
    _, sub_list = AS.AXUIElementCopyAttributeValue(menu, "AXChildren", None)
    if not sub_list:
        print("  No children (menu not open?)")
        break
    _, items = AS.AXUIElementCopyAttributeValue(sub_list[0], "AXChildren", None)
    print("  Device menu items:")
    for item in (items or []):
        _, item_title = AS.AXUIElementCopyAttributeValue(item, "AXTitle", None)
        _, enabled = AS.AXUIElementCopyAttributeValue(item, "AXEnabled", None)
        print(f"    {item_title!r}  enabled={enabled}")
        if item_title == "Rotate Left":
            print("  → pressing Rotate Left")
            err2 = AS.AXUIElementPerformAction(item, "AXPress")
            print(f"  AXPress err={err2}")
    break
else:
    print("'Device' menu not found in menu bar")
