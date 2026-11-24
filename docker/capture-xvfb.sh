#!/usr/bin/env bash
# Off-screen Xvfb + ffmpeg recorder for Tier-2 MinecraftKit visual client tests.
# Never interacts with or steals focus from the host user's primary display.
set -euo pipefail

DISPLAY_NUM="${DISPLAY:-:99}"
RESOLUTION="${XVFB_WHD:-1280x720x24}"
CAPTURE_DIR="${CAPTURE_DIR:-/app/captures}"
CAPTURE_FPS="${CAPTURE_FPS:-2}"
DURATION_SEC="${CAPTURE_DURATION_SEC:-20}"

mkdir -p "$CAPTURE_DIR"

Xvfb "$DISPLAY_NUM" -screen 0 "$RESOLUTION" -ac +extension GLX +render -noreset &
XVFB_PID=$!
trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT

sleep 1
echo "[mckit-visual-bot] Virtual framebuffer ready on $DISPLAY_NUM ($RESOLUTION)"

if [ $# -gt 0 ]; then
  "$@" &
  APP_PID=$!
  ffmpeg -y -f x11grab -video_size "${RESOLUTION%x*}" -framerate "$CAPTURE_FPS" \
    -i "$DISPLAY_NUM" -t "$DURATION_SEC" -pix_fmt yuv420p \
    "$CAPTURE_DIR/session.mp4" >/dev/null 2>&1 &
  wait "$APP_PID" || true
  wait || true
else
  echo "[mckit-visual-bot] Pass a Fabric/Minecraft launch command to record off-screen."
fi
