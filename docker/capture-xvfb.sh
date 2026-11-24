#!/usr/bin/env bash
# Off-screen Xvfb + ffmpeg recorder (PNG keyframe + MP4 + optional palettegen GIF)
# for Tier-2 MinecraftKit visual client tests.
# Never interacts with or steals focus from the host user's primary display.
set -euo pipefail

DISPLAY_NUM="${DISPLAY:-:99}"
RESOLUTION="${XVFB_WHD:-1280x720x24}"
VIDEO_SIZE="${RESOLUTION%x*}"
CAPTURE_DIR="${CAPTURE_DIR:-/app/captures}"
CAPTURE_FPS="${CAPTURE_FPS:-2}"
DURATION_SEC="${CAPTURE_DURATION_SEC:-20}"
EMIT_GIF="${CAPTURE_EMIT_GIF:-1}"

mkdir -p "$CAPTURE_DIR"

XVFB_PID=""
FFMPEG_PID=""
cleanup() {
  if [ -n "$FFMPEG_PID" ]; then
    kill -INT "$FFMPEG_PID" 2>/dev/null || true
    wait "$FFMPEG_PID" 2>/dev/null || true
  fi
  if [ -n "$XVFB_PID" ]; then
    kill "$XVFB_PID" 2>/dev/null || true
    wait "$XVFB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

Xvfb "$DISPLAY_NUM" -screen 0 "$RESOLUTION" -ac +extension GLX +render -noreset &
XVFB_PID=$!

sleep 1
echo "[mckit-visual-bot] Virtual framebuffer ready on $DISPLAY_NUM ($RESOLUTION, off-screen)"

if [ $# -gt 0 ]; then
  "$@" &
  APP_PID=$!
  ffmpeg -y -f x11grab -video_size "$VIDEO_SIZE" -framerate "$CAPTURE_FPS" \
    -i "$DISPLAY_NUM" -t "$DURATION_SEC" -c:v libx264 -preset ultrafast -crf 28 \
    -pix_fmt yuv420p "$CAPTURE_DIR/session.mp4" >/dev/null 2>&1 &
  FFMPEG_PID=$!
  wait "$APP_PID" || true
  wait "$FFMPEG_PID" || true
  FFMPEG_PID=""

  if [ -f "$CAPTURE_DIR/session.mp4" ]; then
    ffmpeg -y -i "$CAPTURE_DIR/session.mp4" -vframes 1 "$CAPTURE_DIR/keyframe.png" >/dev/null 2>&1 || true
    if [ "$EMIT_GIF" = "1" ]; then
      ffmpeg -y -i "$CAPTURE_DIR/session.mp4" \
        -vf "fps=2,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
        "$CAPTURE_DIR/session.gif" >/dev/null 2>&1 || true
    fi
  fi
else
  echo "[mckit-visual-bot] Pass a Fabric/Minecraft launch command to record off-screen PNG/MP4/GIF."
fi
