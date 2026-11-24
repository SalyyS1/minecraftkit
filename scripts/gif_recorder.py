#!/usr/bin/env python3
"""Multi-frame Bot Stage Storyboard PNG & Animated GIF Recorder (Zero Display / Zero Focus Lock).

Converts a sequence of autonomous bot QA stages (join -> auth -> command -> gui -> assert)
into:
  1. Individual crisp off-screen PNG frames via visual_capture.render_bot_snapshot_png()
  2. A stitched horizontal/grid PNG storyboard returned directly as base64 MCP image/png
  3. An optional animated GIF via ffmpeg palettegen+paletteuse when output_gif_path is provided
All AuthMe/nLogin/password strings are scrubbed before rendering any frame.
"""

from __future__ import annotations

import base64
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Any

import bot_engine
import visual_capture


def _read_png_rgb(raw: bytes) -> tuple[int, int, bytearray]:
    """Minimal pure-Python decoder for 8-bit RGB PNGs produced by visual_capture."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a PNG payload")
    pos = 8
    width = height = 0
    idat_parts: list[bytes] = []
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        ctype = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif ctype == b"IDAT":
            idat_parts.append(data)
        elif ctype == b"IEND":
            break
    decompressed = zlib.decompress(b"".join(idat_parts))
    stride = width * 3
    pixels = bytearray(width * height * 3)
    for y in range(height):
        row_start = y * (stride + 1) + 1
        pixels[y * stride : (y + 1) * stride] = decompressed[row_start : row_start + stride]
    return width, height, pixels


def _encode_png_rgb(width: int, height: int, pixels: bytearray) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    stride = width * 3
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)
        raw_rows.extend(pixels[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw_rows), 6))
        + chunk(b"IEND", b"")
    )


def _stitch_storyboard_png(frames_png: list[bytes], cols: int = 2, pad: int = 8) -> tuple[bytes, int, int]:
    decoded = [_read_png_rgb(f) for f in frames_png]
    fw, fh, _ = decoded[0]
    n = len(decoded)
    c = max(1, min(cols, n))
    rows = (n + c - 1) // c
    out_w = c * fw + (c + 1) * pad
    out_h = rows * fh + (rows + 1) * pad
    canvas = bytearray(out_w * out_h * 3)
    # Dark slate background #070d14
    for i in range(0, len(canvas), 3):
        canvas[i] = 7
        canvas[i + 1] = 13
        canvas[i + 2] = 20

    for idx, (w, h, pix) in enumerate(decoded):
        r = idx // c
        col = idx % c
        ox = pad + col * (fw + pad)
        oy = pad + r * (fh + pad)
        copy_w = min(w, fw)
        copy_h = min(h, fh)
        for y in range(copy_h):
            src_off = y * w * 3
            dst_off = ((oy + y) * out_w + ox) * 3
            canvas[dst_off : dst_off + copy_w * 3] = pix[src_off : src_off + copy_w * 3]

    return _encode_png_rgb(out_w, out_h, canvas), out_w, out_h


def record_stage_storyboard(
    *,
    bot_name: str = "MCKitQA",
    server_target: str = "127.0.0.1:25565",
    stages: list[dict[str, Any]] | None = None,
    fps: float = 1.0,
    output_gif_path: str = "",
) -> dict[str, Any]:
    stage_list = stages if stages else [
        {"name": "1. Join Server", "status": "PASS", "chat": ["Joined 127.0.0.1:25565 (18ms)"]},
        {"name": "2. Auto-Auth", "status": "PASS", "chat": ["/login [REDACTED]", "[AuthMe] Logged in!"]},
        {"name": "3. Open /shop", "status": "PASS", "gui_title": "RPG Shop", "chat": ["Opened GUI 9x3"]},
        {"name": "4. Verify Anti-Dupe", "status": "PASS", "gui_title": "RPG Shop", "chat": ["Slot #13 verified, 0 dupes"]},
    ]
    capped = stage_list[:8]
    frames_png: list[bytes] = []
    frame_summaries: list[dict[str, Any]] = []

    for idx, st in enumerate(capped, 1):
        title = bot_engine.redact_bot_text(str(st.get("name", f"Stage {idx}")))
        status = str(st.get("status", "PASS")).upper()
        gui_title = bot_engine.redact_bot_text(str(st.get("gui_title", "")))
        raw_chat = st.get("chat") if isinstance(st.get("chat"), list) else []
        chat_lines = [bot_engine.redact_bot_text(str(c)) for c in raw_chat]
        if not chat_lines:
            chat_lines = [f"[{status}] {title}"]
        state = {
            "status": status,
            "bot_name": bot_name,
            "server": server_target,
            "tps": float(st.get("tps", 20.0)),
            "chat_lines": chat_lines,
            "gui": {
                "title": gui_title or f"Stage {idx}: {title}",
                "slots": st.get("slots", {}),
            },
            "stage": title,
        }
        png_bytes = visual_capture.render_bot_snapshot_png(
            state,
            width=480,
            height=290,
            title=f"STAGE {idx}: {title}",
        )
        frames_png.append(png_bytes)
        frame_summaries.append({
            "frame": idx,
            "stage": title,
            "status": status,
            "bytes": len(png_bytes),
        })

    storyboard_png, sb_w, sb_h = _stitch_storyboard_png(frames_png, cols=2 if len(frames_png) > 1 else 1)
    storyboard_b64 = base64.b64encode(storyboard_png).decode("ascii")

    gif_written = ""
    gif_bytes = 0
    ffmpeg_bin = shutil.which("ffmpeg")
    if output_gif_path and ffmpeg_bin:
        out_path = Path(output_gif_path).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            for idx, fb in enumerate(frames_png, 1):
                (td_path / f"frame_{idx:03d}.png").write_bytes(fb)
            rate = max(0.5, min(float(fps), 10.0))
            cmd = [
                ffmpeg_bin, "-y", "-framerate", f"{rate:.2f}",
                "-i", str(td_path / "frame_%03d.png"),
                "-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                str(out_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
            if proc.returncode == 0 and out_path.is_file():
                gif_written = str(out_path)
                gif_bytes = out_path.stat().st_size

    return {
        "ok": True,
        "bot_name": bot_name,
        "server_target": server_target,
        "frame_count": len(frames_png),
        "storyboard_dimensions": {"width": sb_w, "height": sb_h},
        "storyboard_bytes": len(storyboard_png),
        "storyboard_png_base64": storyboard_b64,
        "ffmpeg_available": bool(ffmpeg_bin),
        "gif_written_path": gif_written,
        "gif_bytes": gif_bytes,
        "screen_lock_free": True,
        "secrets_redacted": True,
        "frames": frame_summaries,
    }
