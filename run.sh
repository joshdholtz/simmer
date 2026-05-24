#!/usr/bin/env bash
set -e

INVOCATION_DIR="$PWD"
cd "$(dirname "$0")"

PORT=4040
MODE=auto
FPS=15
QUALITY=70
PROJECT_DIR=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --port)         PORT="$2";        shift 2 ;;
    --mode)         MODE="$2";        shift 2 ;;
    --fps)          FPS="$2";         shift 2 ;;
    --quality)      QUALITY="$2";     shift 2 ;;
    --project-dir)  PROJECT_DIR="$2"; shift 2 ;;
    --kill)
      pkill -f "forward_sim" 2>/dev/null || true
      lsof -iTCP:$PORT -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $2}' | xargs -r kill -9 2>/dev/null || true
      echo "Stopped."
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Kill any existing instance on this port before starting
lsof -iTCP:$PORT -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $2}' | xargs -r kill -9 2>/dev/null || true

ARGS="--port $PORT --mode $MODE --fps $FPS --quality $QUALITY"
if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_DIR="$INVOCATION_DIR"
fi
ARGS="$ARGS --project-dir $PROJECT_DIR"

exec python3 -m forward_sim $ARGS
