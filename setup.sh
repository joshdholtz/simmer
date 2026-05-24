#!/usr/bin/env bash
set -e

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }

echo ""
echo -e "${BOLD}forward-sim setup${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Homebrew ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Homebrew${NC}"
if command -v brew &>/dev/null; then
  ok "brew found ($(brew --version | head -1))"
else
  fail "brew not found"
  info "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ok "brew installed"
fi

# ── idb-companion ──────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}idb-companion${NC}  (compat mode — no permissions needed)"
if brew list idb-companion &>/dev/null; then
  ok "idb-companion $(brew list --versions idb-companion | awk '{print $2}')"
else
  info "Installing idb-companion..."
  brew tap facebook/fb
  brew install idb-companion
  ok "idb-companion installed"
fi

# ── Python ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Python${NC}"
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
  fail "python3 not found — install via mise, pyenv, or Homebrew"
  exit 1
fi
PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  fail "Python $PY_VERSION found but 3.11+ required"
  exit 1
fi
ok "Python $PY_VERSION at $PYTHON"

# ── pip packages ───────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Python packages${NC}"

install_if_missing() {
  local module="$1"
  local package="$2"
  local label="${3:-$package}"
  if $PYTHON -c "import $module" &>/dev/null; then
    ok "$label already installed"
  else
    info "Installing $label..."
    $PYTHON -m pip install -q "$package"
    ok "$label installed"
  fi
}

install_if_missing "aiohttp"  "aiohttp"  "aiohttp"
install_if_missing "idb"      "fb-idb"   "fb-idb (idb CLI client)"
# pyobjc must be installed as the meta-package — individual packages fail on macOS 26+
install_if_missing "AppKit"   "pyobjc"   "pyobjc (fast mode)"

# ── Xcode / simctl ────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Xcode tools${NC}"
if command -v xcrun &>/dev/null && xcrun simctl list &>/dev/null 2>&1; then
  ok "xcrun simctl available"
else
  warn "xcrun simctl not found — install Xcode from the App Store"
fi

# ── Tailscale (optional) ──────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Tailscale${NC}  (recommended for remote access)"
if command -v tailscale &>/dev/null; then
  TS_IP=$(tailscale ip -4 2>/dev/null || true)
  if [ -n "$TS_IP" ]; then
    ok "Tailscale connected — this machine is at ${BOLD}$TS_IP${NC}"
  else
    warn "Tailscale installed but not connected"
  fi
else
  warn "Tailscale not installed — iPad access over internet won't work without it"
  info "Install: https://tailscale.com/download/mac"
fi

# ── Mode detection ────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Backend mode${NC}"
HAS_SCREEN=$($PYTHON -c "import Quartz; print(int(bool(Quartz.CGPreflightScreenCaptureAccess())))" 2>/dev/null || echo "0")
HAS_AX=$($PYTHON -c "import Quartz; print(int(bool(Quartz.AXIsProcessTrusted())))" 2>/dev/null || echo "0")
IDB_BIN="$(dirname $($PYTHON -c 'import sys; print(sys.executable)'))/idb"
HAS_IDB=$([ -x "$IDB_BIN" ] && echo "1" || echo "0")

if [ "$HAS_SCREEN" = "1" ] && [ "$HAS_AX" = "1" ]; then
  ok "${GREEN}fast mode${NC} — Quartz capture + CGEvent injection (~30fps)"
elif [ "$HAS_IDB" = "1" ]; then
  ok "${YELLOW}compat mode${NC} — simctl capture + idb injection (~10fps)"
  warn "For fast mode, grant permissions in:"
  warn "  System Settings → Privacy & Security → Screen Recording"
  warn "  System Settings → Privacy & Security → Accessibility"
  warn "  (add Terminal or your Python binary, then re-run this script)"
else
  fail "No working backend detected"
  fail "idb import failed even after install — try: $PYTHON -m pip install --force-reinstall fb-idb"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}Ready. Start the server:${NC}"
echo ""
echo -e "  ${BLUE}cd $(pwd) && python3 -m forward_sim${NC}"
echo ""
echo "Options:"
echo "  --port 8080        HTTP port"
echo "  --fps 15           Default frame rate"
echo "  --quality 70       JPEG quality (10-95)"
echo "  --mode auto        auto | fast | compat"
echo ""
