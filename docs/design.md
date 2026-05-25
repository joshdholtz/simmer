# simmer design guide

Dark, dense, Apple-native. Feels at home next to Xcode and macOS system UI. Not a web app that happens to run on a Mac.

---

## Principles

**Subtle over loud.** Information should be present when needed, invisible when not. Warnings don't shout — they whisper. If something can be communicated with color alone, don't also add an icon and bold text.

**Positive framing.** "Enable fast mode" not "Missing permissions". "Available" not "Offline". Guide toward the good state rather than labeling the bad one.

**Density without clutter.** The sidebar fits a lot of information in 232px. Achieve this through tight spacing and small type, not by removing information. Every pixel of padding is intentional.

**Apple conventions.** Follow macOS patterns: disclosure rows expand downward, status dots are 5–6px, chevrons rotate 90°, grouped lists have subtle borders between items not around each one.

---

## Color tokens

Defined in `css/tokens.css`. Never hardcode a hex value in a component.

| Token | Value | Use |
|-------|-------|-----|
| `--bg-base` | `#09090b` | App background |
| `--bg-elevated` | `#18181b` | Sidebar, panels |
| `--bg-overlay` | `#27272a` | Cards, inputs, hover states |
| `--bg-active` | `#3f3f46` | Pressed states |
| `--text-primary` | `#fafafa` | Main content |
| `--text-secondary` | `#a1a1aa` | Labels, secondary info |
| `--text-tertiary` | `#71717a` | Hints, placeholders, metadata |
| `--accent` | `#0a84ff` | Selected state, focus rings, active elements |
| `--success` | `#30d158` | Booted indicator, fast mode badge |
| `--warning` | `#ff9f0a` | Compat mode badge, subtle indicators |
| `--error` | `#ff453a` | Errors only — use sparingly |

Status colors (`--success`, `--warning`, `--error`) should appear at low opacity for backgrounds — use `rgba()` not the token directly. Example: `rgba(255, 159, 10, 0.12)` for a warning badge background.

---

## Typography

Font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif`  
Mono stack: `"SF Mono", "Menlo", "Monaco", "Courier New", monospace`

| Size | Weight | Use |
|------|--------|-----|
| 15px | 600 | Logo / primary heading |
| 13px | 500 | Device names, button labels |
| 12px | 400 | Section labels, list items |
| 11px | 400–500 | Metadata, badges, ctrl labels |
| 10px | 400 | Detail text inside expanded rows |

Use `font-variant-numeric: tabular-nums` for any numeric values that update (fps, quality, counters).

---

## Spacing

8-point grid via `--sp-*` tokens.

| Token | Value |
|-------|-------|
| `--sp-1` | 4px |
| `--sp-2` | 8px |
| `--sp-3` | 12px |
| `--sp-4` | 16px |
| `--sp-6` | 24px |
| `--sp-8` | 32px |

Standard sidebar row padding: `var(--sp-2) var(--sp-4)` (8px top/bottom, 16px left/right).

---

## Radii

| Token | Value | Use |
|-------|-------|-----|
| `--r-sm` | 6px | Badges, small buttons |
| `--r-md` | 10px | Cards, inputs, grouped rows |
| `--r-lg` | 14px | Large cards |
| `--r-xl` | 20px | Device frames |
| `--r-pill` | 999px | Pill buttons, status dots |

---

## Component patterns

### Sidebar rows
Standard interactive rows use `.device-item`. Height is determined by padding (`--sp-2` top/bottom), not a fixed height. Active state: `--accent-bg` background + `--accent` text on the label.

### Badges
Small inline labels. Use `--r-sm`, `font-size: 9–11px`, `font-weight: 600 or 700`, uppercase or lowercase depending on context. Background is always a low-opacity version of the status color.

### Disclosure rows
A button row with a label and a `›` chevron. Chevron rotates 90° when open (CSS transform, `var(--dur-fast)` transition). Expanded body is a grouped card: `--bg-overlay` background, `--border-subtle` border, `--r-md` radius. Items within the card are separated by `1px solid var(--border-subtle)` borders, not individual card borders.

### Status dots
5–6px circle, `border-radius: 50%`. Colors: `--bg-active` (neutral), `--success` (connected/booted), `--warning` (reconnecting). Never larger than 6px inline — they're ambient signals, not primary UI.

### Pill controls (per-sim overlay)
`rgba(24, 24, 27, 0.92)` background with `backdrop-filter: blur(12px)`. Buttons are 40×40px touch targets. Use `--r-pill` on the container.

---

## Motion

| Token | Value | Use |
|-------|-------|-----|
| `--dur-fast` | 120ms | Hover states, color transitions |
| `--dur-mid` | 200ms | Panel reveals, overlay fades |
| `--dur-slow` | 320ms | Large layout changes |

Easing: `--ease` (`cubic-bezier(0.16, 1, 0.3, 1)`) for entrances. Standard `ease` or `ease-in-out` for hovers.

Avoid animating layout properties (width, height, top, left) — use `transform` and `opacity` for performance.

---

## What not to do

- Don't hardcode hex colors — use tokens
- Don't use emoji in UI chrome (only in empty states as decoration)
- Don't use red/orange for anything that isn't genuinely an error/warning
- Don't add borders around every element — use space to separate, borders sparingly
- Don't animate more than one property at a time unless intentional
- Don't use `font-weight: 700` or heavier outside of badges
