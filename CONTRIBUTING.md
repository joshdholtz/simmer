# Contributing to simmer

Thanks for your interest! simmer is a small, focused tool — contributions that fit the scope are very welcome.

## Dev setup

```bash
git clone https://github.com/joshdholtz/simmer
cd simmer
pip install -e .
```

Build the Swift rotation helper (needed for fast mode rotate):

```bash
swiftc -O rotate_sim.swift -o rotate_sim
```

Start the server — static file changes (HTML/CSS/JS) take effect on browser refresh with no restart needed:

```bash
simmer
```

## Project structure

```
simmer/
  __main__.py          CLI entry point + backend selection
  server.py            aiohttp HTTP + WebSocket server
  backend_quartz.py    Fast backend: Quartz capture + CGEvent input
  backend_simctl.py    Compat backend: simctl capture + idb input
  backend_base.py      Shared helpers, device discovery, boot
  static/
    index.html
    css/               tokens.css, layout.css, components.css, terminal.css
    js/                app.js, stream.js, terminal.js, api.js
```

The frontend is plain ES modules — no bundler, no build step.

## Backends

| Mode | Capture | Input | Requires |
|------|---------|-------|----------|
| fast | Quartz | CGEvent | Screen Recording + Accessibility permissions |
| compat | simctl | idb | `idb-companion` |

Both backends implement the same interface in `backend_base.py`. If you're adding capture or input features, you'll likely need to touch both.

## Guidelines

- No bundler, no npm — keep the frontend dependency-free
- Match the existing code style (no formatter is enforced, just be consistent)
- Keep PRs focused — one thing per PR is easier to review
- If you're adding a feature, update the README

## Reporting bugs

Please open a [GitHub issue](https://github.com/joshdholtz/simmer/issues) with:
- macOS version
- Which backend mode simmer is using (shown on startup)
- Steps to reproduce
- What you expected vs. what happened
