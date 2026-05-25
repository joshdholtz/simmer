# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.0] - 2026-05-24

### Added
- Live iOS Simulator streaming to any browser at up to 30 fps
- Touch, swipe, and tap input forwarding
- Rotate simulator via Device menu
- Multi-sim: open multiple simulators side-by-side with draggable divider
- Built-in persistent terminal (PTY, survives page refresh, tmux-friendly)
- Terminal font size control (A−/A+), persisted via localStorage
- Boot shut-down simulators from the sidebar without opening Xcode
- Fast backend: Quartz window capture + CGEvent injection (~30 fps)
- Compat backend: `simctl screenshot` + `idb` input injection (~10 fps)
- Auto-selects best available backend on startup
- Keyboard bar for sending text and special keys to focused simulator
- Data Saver mode to reduce bandwidth on slow connections
- Safe area support for iPad/iPhone browser access
- Pinnable terminal panel (side or bottom drawer)
- Tailscale-friendly — binds to `0.0.0.0`, works over LAN and VPN
- Homebrew formula via `joshdholtz/tap`
