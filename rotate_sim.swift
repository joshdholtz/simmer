// Rotates the iOS Simulator by sending Cmd+Left Arrow (Hardware > Rotate Left).
// Works when called from a process in the user's GUI session (e.g. the server).
// Usage: rotate_sim <device-name> [cx cy]
//   cx, cy — optional window center (pass to ensure the right window is key).
import Cocoa
import ApplicationServices

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: rotate_sim <device-name> [cx cy]\n", stderr)
    exit(1)
}
let devName = CommandLine.arguments[1]

var clickPoint: CGPoint? = nil
if CommandLine.arguments.count >= 4,
   let cx = Double(CommandLine.arguments[2]),
   let cy = Double(CommandLine.arguments[3]) {
    clickPoint = CGPoint(x: cx, y: cy)
}

let runningApps = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.iphonesimulator")
guard let app = runningApps.first else {
    fputs("rotate_sim: Simulator.app not running\n", stderr)
    exit(1)
}

// Bring Simulator to front so keyboard events reach it.
if #available(macOS 14.0, *) {
    app.activate()
} else {
    app.activate(options: .activateIgnoringOtherApps)
}
Thread.sleep(forTimeInterval: 0.25)

// If we know the window center, click it to make it the key window.
if let pt = clickPoint {
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
    Thread.sleep(forTimeInterval: 0.05)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseUp,   mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
    Thread.sleep(forTimeInterval: 0.15)
} else {
    // No coords — try to find the window via Quartz and click its title bar.
    let pid = app.processIdentifier
    if let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] {
        for win in list {
            guard let ownerPid = win["kCGWindowOwnerPID"] as? Int32, ownerPid == pid else { continue }
            guard let bounds = win["kCGWindowBounds"] as? [String: Any] else { continue }
            let x = bounds["X"] as? CGFloat ?? 0
            let y = bounds["Y"] as? CGFloat ?? 0
            let w = bounds["Width"] as? CGFloat ?? 0
            let h = bounds["Height"] as? CGFloat ?? 0
            guard w > 100 && h > 100 else { continue }
            let titleBarPt = CGPoint(x: x + w / 2, y: y + 8)
            let src = CGEventSource(stateID: .hidSystemState)
            CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: titleBarPt, mouseButton: .left)?.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.05)
            CGEvent(mouseEventSource: src, mouseType: .leftMouseUp,   mouseCursorPosition: titleBarPt, mouseButton: .left)?.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.15)
            break
        }
    }
}

// Send Cmd+Left Arrow — the Rotate Left keyboard shortcut.
let src = CGEventSource(stateID: .hidSystemState)
let keyDown = CGEvent(keyboardEventSource: src, virtualKey: 123, keyDown: true)!
keyDown.flags = .maskCommand
keyDown.post(tap: .cghidEventTap)
Thread.sleep(forTimeInterval: 0.05)
let keyUp = CGEvent(keyboardEventSource: src, virtualKey: 123, keyDown: false)!
keyUp.flags = .maskCommand
keyUp.post(tap: .cghidEventTap)

Thread.sleep(forTimeInterval: 0.3)
print("rotated")
exit(0)
