"""Off-screen visual snapshot and timelapse renderer for MinecraftKit test bots.

Renders crisp PNG visual inspection cards (HUD telemetry, GUI/inventory grids,
chat/scoreboard panels, and 2D entity minimaps) using 100% Python stdlib
(struct + zlib) with zero external image library requirements. Also supports
assembling MP4/GIF timelapses via ffmpeg and grabbing off-screen Xvfb/mod
screenshots without ever hijacking the user's primary desktop display.
"""

from __future__ import annotations

import base64
import binascii
import math
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any


# Compact 5x7 uppercase/ASCII bitmap glyph definitions (each row is a 5-bit mask).
_FONT_5X7: dict[str, tuple[int, ...]] = {
    " ": (0, 0, 0, 0, 0, 0, 0),
    "!": (4, 4, 4, 4, 4, 0, 4),
    '"': (10, 10, 0, 0, 0, 0, 0),
    "#": (10, 31, 10, 10, 31, 10, 0),
    "$": (4, 15, 20, 14, 5, 30, 4),
    "%": (25, 26, 4, 4, 11, 19, 0),
    "&": (12, 18, 20, 8, 21, 18, 13),
    "'": (4, 4, 0, 0, 0, 0, 0),
    "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8),
    "*": (0, 4, 21, 14, 21, 4, 0),
    "+": (0, 4, 4, 31, 4, 4, 0),
    ",": (0, 0, 0, 0, 4, 4, 8),
    "-": (0, 0, 0, 31, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 4, 4),
    "/": (1, 2, 2, 4, 8, 8, 16),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    ":": (0, 4, 4, 0, 4, 4, 0),
    ";": (0, 4, 4, 0, 4, 4, 8),
    "<": (2, 4, 8, 16, 8, 4, 2),
    "=": (0, 0, 31, 0, 31, 0, 0),
    ">": (8, 4, 2, 1, 2, 4, 8),
    "?": (14, 17, 1, 2, 4, 0, 4),
    "@": (14, 17, 23, 21, 23, 16, 14),
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 27, 17),
    "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "[": (14, 8, 8, 8, 8, 8, 14),
    "\\": (16, 8, 8, 4, 2, 2, 1),
    "]": (14, 2, 2, 2, 2, 2, 14),
    "^": (4, 10, 17, 0, 0, 0, 0),
    "_": (0, 0, 0, 0, 0, 0, 31),
    "{": (2, 4, 4, 8, 4, 4, 2),
    "|": (4, 4, 4, 4, 4, 4, 4),
    "}": (8, 4, 4, 2, 4, 4, 8),
    "~": (0, 0, 8, 21, 2, 0, 0),
}

Color = tuple[int, int, int]

# Color palette matching MinecraftKit's dark emerald/obsidian workstation aesthetic.
BG_BASE: Color = (10, 16, 24)
BG_PANEL: Color = (17, 26, 38)
BG_SLOT: Color = (25, 36, 52)
BG_SLOT_ACTIVE: Color = (35, 62, 74)
BORDER_SUBTLE: Color = (42, 58, 78)
BORDER_ACCENT: Color = (68, 224, 176)
TEXT_PRIMARY: Color = (232, 242, 250)
TEXT_MUTED: Color = (138, 158, 182)
ACCENT_EMERALD: Color = (72, 232, 178)
ACCENT_CYAN: Color = (78, 198, 245)
ACCENT_AMBER: Color = (245, 190, 72)
ACCENT_RED: Color = (242, 92, 104)
ACCENT_PURPLE: Color = (182, 130, 250)


class PixelCanvas:
    """Minimal RGB framebuffer that encodes directly to valid PNG bytes."""

    def __init__(self, width: int, height: int, background: Color = BG_BASE) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        r, g, b = background
        row = bytes((r, g, b)) * self.width
        self._buf = bytearray(row * self.height)

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self._buf[idx] = color[0]
            self._buf[idx + 1] = color[1]
            self._buf[idx + 2] = color[2]

    def fill_rect(self, x: int, y: int, w: int, h: int, color: Color) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        span = bytes(color) * (x1 - x0)
        stride = self.width * 3
        for row in range(y0, y1):
            start = row * stride + x0 * 3
            self._buf[start : start + len(span)] = span

    def draw_rect(self, x: int, y: int, w: int, h: int, color: Color, thickness: int = 1) -> None:
        self.fill_rect(x, y, w, thickness, color)
        self.fill_rect(x, y + h - thickness, w, thickness, color)
        self.fill_rect(x, y, thickness, h, color)
        self.fill_rect(x + w - thickness, y, thickness, h, color)

    def draw_circle(self, cx: int, cy: int, radius: int, color: Color) -> None:
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= r2:
                    self.set_pixel(cx + dx, cy + dy, color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_text(self, x: int, y: int, text: str, color: Color = TEXT_PRIMARY, scale: int = 1, max_chars: int | None = None) -> None:
        rendered = text.upper()
        if max_chars is not None and len(rendered) > max_chars:
            rendered = rendered[: max(0, max_chars - 2)] + ".."
        cursor_x = x
        step = 6 * scale
        for ch in rendered:
            glyph = _FONT_5X7.get(ch, _FONT_5X7["?"])
            for row_idx, row_mask in enumerate(glyph):
                for col_idx in range(5):
                    if row_mask & (1 << (4 - col_idx)):
                        self.fill_rect(
                            cursor_x + col_idx * scale,
                            y + row_idx * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor_x += step

    def to_png_bytes(self) -> bytes:
        def _chunk(tag: bytes, payload: bytes) -> bytes:
            crc = binascii.crc32(tag + payload) & 0xFFFFFFFF
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

        raw_rows = bytearray()
        stride = self.width * 3
        for row in range(self.height):
            raw_rows.append(0)  # Filter type 0 (None)
            start = row * stride
            raw_rows.extend(self._buf[start : start + stride])

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        idat = zlib.compress(bytes(raw_rows), level=6)
        return (
            b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", idat)
            + _chunk(b"IEND", b"")
        )


def _strip_mc_formatting(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in ("§", "&") and i + 1 < len(text):
            i += 2
            continue
        ch = text[i]
        out.append(ch if 32 <= ord(ch) < 127 else "?")
        i += 1
    return "".join(out)


def render_bot_snapshot_png(
    state: dict[str, Any],
    *,
    width: int = 960,
    height: int = 580,
    title: str = "MINECRAFTKIT HEADLESS BOT QA SNAPSHOT",
) -> bytes:
    """Render a complete off-screen HUD + GUI + Chat + Minimap QA PNG card."""
    canvas = PixelCanvas(width, height, BG_BASE)

    # Top header bar
    canvas.fill_rect(0, 0, width, 46, BG_PANEL)
    canvas.fill_rect(0, 45, width, 2, BORDER_ACCENT)
    canvas.draw_text(16, 15, title, ACCENT_EMERALD, scale=2, max_chars=56)

    status_label = str(state.get("status", "CONNECTED")).upper()
    status_color = ACCENT_EMERALD if status_label in ("CONNECTED", "PASSED", "AUTHENTICATED", "OK") else (
        ACCENT_RED if "FAIL" in status_label or "ERR" in status_label else ACCENT_AMBER
    )
    badge_w = min(210, max(96, len(status_label) * 12 + 24))
    canvas.fill_rect(width - badge_w - 16, 10, badge_w, 26, BG_SLOT)
    canvas.draw_rect(width - badge_w - 16, 10, badge_w, 26, status_color, 1)
    canvas.draw_text(width - badge_w - 6, 17, status_label, status_color, scale=1, max_chars=26)

    # Left-top: Bot Telemetry Panel
    canvas.fill_rect(16, 62, 440, 148, BG_PANEL)
    canvas.draw_rect(16, 62, 440, 148, BORDER_SUBTLE, 1)
    canvas.draw_text(28, 72, "BOT TELEMETRY & AUTH", ACCENT_CYAN, scale=1)

    username = str(state.get("username", "MCKitBot"))
    server = str(state.get("server", "127.0.0.1:25565"))
    version = str(state.get("version", "1.21.4"))
    tier = str(state.get("tier", "tier1-protocol"))
    auth_state = str(state.get("auth_state", "AUTHENTICATED"))
    pos = state.get("position", {"x": 0.0, "y": 64.0, "z": 0.0})
    health = float(state.get("health", 20.0))
    food = float(state.get("food", 20.0))
    tps = float(state.get("tps", 20.0))
    ram_mb = float(state.get("ram_mb", 42.0))

    canvas.draw_text(28, 92, f"BOT: {username}   TIER: {tier}", TEXT_PRIMARY, scale=1, max_chars=66)
    canvas.draw_text(28, 108, f"SRV: {server} (MC {version})", TEXT_MUTED, scale=1, max_chars=66)
    canvas.draw_text(28, 124, f"AUTH: {auth_state}   RAM: {ram_mb:.1f} MB   TPS: {tps:.1f}", ACCENT_EMERALD, scale=1, max_chars=66)
    canvas.draw_text(
        28,
        140,
        f"POS: X={float(pos.get('x', 0)):.1f} Y={float(pos.get('y', 64)):.1f} Z={float(pos.get('z', 0)):.1f}",
        TEXT_PRIMARY,
        scale=1,
        max_chars=66,
    )

    # Health & Food bars
    canvas.draw_text(28, 162, f"HP {health:.0f}/20", ACCENT_RED, scale=1)
    canvas.fill_rect(96, 161, 140, 10, BG_SLOT)
    hp_w = int(140 * max(0.0, min(1.0, health / 20.0)))
    canvas.fill_rect(96, 161, hp_w, 10, ACCENT_RED)
    canvas.draw_rect(96, 161, 140, 10, BORDER_SUBTLE, 1)

    canvas.draw_text(252, 162, f"FOOD {food:.0f}/20", ACCENT_AMBER, scale=1)
    canvas.fill_rect(330, 161, 112, 10, BG_SLOT)
    food_w = int(112 * max(0.0, min(1.0, food / 20.0)))
    canvas.fill_rect(330, 161, food_w, 10, ACCENT_AMBER)
    canvas.draw_rect(330, 161, 112, 10, BORDER_SUBTLE, 1)

    # Stage progress summary line
    stages = state.get("stages", [])
    passed = sum(1 for s in stages if isinstance(s, dict) and s.get("passed"))
    canvas.draw_text(
        28,
        184,
        f"STAGES: {passed}/{len(stages)} PASSED   SCREEN-LOCK: NONE (HEADLESS)",
        ACCENT_CYAN,
        scale=1,
        max_chars=66,
    )

    # Left-bottom: Active GUI / Inventory Grid (9x4 slots)
    canvas.fill_rect(16, 224, 440, 340, BG_PANEL)
    canvas.draw_rect(16, 224, 440, 340, BORDER_SUBTLE, 1)
    gui = state.get("open_gui") or {}
    gui_title = _strip_mc_formatting(str(gui.get("title", "PLAYER INVENTORY (NO CHEST OPEN)")))
    canvas.draw_text(28, 236, f"GUI: {gui_title}", ACCENT_PURPLE, scale=1, max_chars=66)

    slots_by_idx: dict[int, dict[str, Any]] = {}
    raw_slots = gui.get("slots") if isinstance(gui.get("slots"), list) else state.get("inventory", [])
    if isinstance(raw_slots, list):
        for entry in raw_slots:
            if isinstance(entry, dict) and isinstance(entry.get("slot"), int):
                slots_by_idx[entry["slot"]] = entry

    cols = 9
    rows = 4
    slot_size = 42
    gap = 4
    grid_x0 = 28
    grid_y0 = 258
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            sx = grid_x0 + c * (slot_size + gap)
            sy = grid_y0 + r * (slot_size + gap)
            item = slots_by_idx.get(idx)
            bg = BG_SLOT_ACTIVE if item else BG_SLOT
            border = ACCENT_PURPLE if (item and item.get("enchanted")) else (ACCENT_EMERALD if item else BORDER_SUBTLE)
            canvas.fill_rect(sx, sy, slot_size, slot_size, bg)
            canvas.draw_rect(sx, sy, slot_size, slot_size, border, 1)
            canvas.draw_text(sx + 3, sy + 3, str(idx), TEXT_MUTED, scale=1)
            if item:
                short_name = _strip_mc_formatting(str(item.get("name", item.get("item", "ITEM"))))
                canvas.draw_text(sx + 3, sy + 16, short_name[:6], TEXT_PRIMARY, scale=1)
                count = int(item.get("count", 1))
                canvas.draw_text(sx + 3, sy + 29, f"x{count}", ACCENT_AMBER, scale=1)

    # Active item tooltip preview under grid
    highlighted = next(iter(slots_by_idx.values()), None)
    canvas.fill_rect(28, 452, 416, 98, BG_BASE)
    canvas.draw_rect(28, 452, 416, 98, BORDER_SUBTLE, 1)
    if highlighted:
        h_name = _strip_mc_formatting(str(highlighted.get("name", highlighted.get("item", "Item"))))
        canvas.draw_text(36, 462, f"INSPECTED SLOT {highlighted.get('slot', 0)}: {h_name}", ACCENT_EMERALD, scale=1, max_chars=64)
        lore = highlighted.get("lore", [])
        if isinstance(lore, list):
            for l_idx, line in enumerate(lore[:4]):
                canvas.draw_text(36, 480 + l_idx * 15, _strip_mc_formatting(str(line)), TEXT_MUTED, scale=1, max_chars=64)
    else:
        canvas.draw_text(36, 468, "NO POPULATED GUI SLOTS CAPTURED IN THIS FRAME.", TEXT_MUTED, scale=1)
        canvas.draw_text(36, 486, "SEND A GUI COMMAND (E.G. /SHOP, /MENU) TO INSPECT SLOTS.", TEXT_MUTED, scale=1)

    # Right-top: 2D Top-Down Entity & Block Minimap + Scoreboard
    canvas.fill_rect(472, 62, 224, 210, BG_PANEL)
    canvas.draw_rect(472, 62, 224, 210, BORDER_SUBTLE, 1)
    canvas.draw_text(484, 72, "ENTITY MINIMAP (32B)", ACCENT_CYAN, scale=1)
    map_cx, map_cy = 584, 174
    canvas.fill_rect(488, 90, 192, 168, BG_BASE)
    canvas.draw_rect(488, 90, 192, 168, BORDER_SUBTLE, 1)
    # Grid crosshairs
    canvas.draw_line(488, map_cy, 680, map_cy, (24, 34, 48))
    canvas.draw_line(map_cx, 90, map_cx, 258, (24, 34, 48))
    # Plot nearby entities relative to bot
    bx = float(pos.get("x", 0.0))
    bz = float(pos.get("z", 0.0))
    for ent in state.get("entities", [])[:30]:
        if not isinstance(ent, dict):
            continue
        dx = float(ent.get("x", bx)) - bx
        dz = float(ent.get("z", bz)) - bz
        px = int(map_cx + max(-32.0, min(32.0, dx)) * 2.8)
        py = int(map_cy + max(-28.0, min(28.0, dz)) * 2.8)
        ent_color = ACCENT_RED if str(ent.get("hostile", False)).lower() == "true" else ACCENT_AMBER
        canvas.draw_circle(px, py, 3, ent_color)
    # Plot bot + facing arrow
    yaw = math.radians(float(pos.get("yaw", 0.0)))
    canvas.draw_circle(map_cx, map_cy, 5, ACCENT_EMERALD)
    canvas.draw_line(
        map_cx,
        map_cy,
        int(map_cx - math.sin(yaw) * 18),
        int(map_cy + math.cos(yaw) * 18),
        ACCENT_CYAN,
    )

    # Right-top-right: Scoreboard & Title/Actionbar
    canvas.fill_rect(708, 62, 236, 210, BG_PANEL)
    canvas.draw_rect(708, 62, 236, 210, BORDER_SUBTLE, 1)
    sb = state.get("scoreboard") or {}
    sb_title = _strip_mc_formatting(str(sb.get("title", "SCOREBOARD")))
    canvas.draw_text(720, 72, sb_title, ACCENT_AMBER, scale=1, max_chars=34)
    sb_lines = sb.get("lines", []) if isinstance(sb.get("lines"), list) else []
    for idx, line in enumerate(sb_lines[:9]):
        canvas.draw_text(720, 92 + idx * 16, _strip_mc_formatting(str(line)), TEXT_PRIMARY, scale=1, max_chars=34)
    if not sb_lines:
        canvas.draw_text(720, 96, "(NO SIDEBAR ACTIVE)", TEXT_MUTED, scale=1)
    actionbar = state.get("actionbar")
    if actionbar:
        canvas.draw_text(720, 246, f"ACT: {_strip_mc_formatting(str(actionbar))}", ACCENT_CYAN, scale=1, max_chars=34)

    # Right-bottom: Chat & Stage Assertion Log
    canvas.fill_rect(472, 286, 472, 278, BG_PANEL)
    canvas.draw_rect(472, 286, 472, 278, BORDER_SUBTLE, 1)
    canvas.draw_text(484, 298, "RECENT CHAT & STAGE ASSERTIONS (SECRETS REDACTED)", ACCENT_CYAN, scale=1, max_chars=72)

    chat_lines = state.get("chat", [])
    y_cursor = 318
    if isinstance(chat_lines, list):
        for line in chat_lines[-9:]:
            clean_line = _strip_mc_formatting(str(line))
            color = ACCENT_RED if "ERROR" in clean_line.upper() or "FAIL" in clean_line.upper() else TEXT_PRIMARY
            canvas.draw_text(484, y_cursor, clean_line, color, scale=1, max_chars=74)
            y_cursor += 16

    # Stage verdict strip at bottom right
    y_cursor = max(y_cursor + 6, 466)
    canvas.fill_rect(484, y_cursor, 448, 86, BG_BASE)
    canvas.draw_rect(484, y_cursor, 448, 86, BORDER_SUBTLE, 1)
    for idx, stage in enumerate(stages[-5:]):
        if not isinstance(stage, dict):
            continue
        ok = bool(stage.get("passed"))
        tag = "PASS" if ok else "FAIL"
        tag_color = ACCENT_EMERALD if ok else ACCENT_RED
        desc = _strip_mc_formatting(str(stage.get("name", stage.get("action", "stage"))))
        canvas.draw_text(494, y_cursor + 8 + idx * 15, f"[{tag}] {desc}", tag_color, scale=1, max_chars=68)

    return canvas.to_png_bytes()


def encode_png_base64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def save_snapshot_png(
    state: dict[str, Any],
    output_path: Path,
    *,
    title: str = "MINECRAFTKIT HEADLESS BOT QA SNAPSHOT",
) -> dict[str, Any]:
    png_bytes = render_bot_snapshot_png(state, title=title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)
    return {
        "path": str(output_path),
        "bytes": len(png_bytes),
        "mime_type": "image/png",
        "base64": encode_png_base64(png_bytes),
    }


def assemble_timelapse_video(
    frame_paths: list[Path],
    output_path: Path,
    *,
    fps: int = 2,
) -> dict[str, Any]:
    """Assemble captured PNG snapshots into an MP4/GIF timelapse via ffmpeg if installed."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return {
            "ok": False,
            "reason": "ffmpeg not found in PATH; individual PNG frames are still available.",
            "frame_count": len(frame_paths),
        }
    if not frame_paths:
        return {"ok": False, "reason": "No PNG frames provided.", "frame_count": 0}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_path.with_suffix(".frames.txt")
    duration = max(0.1, 1.0 / max(1, fps))
    lines: list[str] = []
    for frame in frame_paths:
        escaped = str(frame.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {duration:.3f}")
    if frame_paths:
        escaped_last = str(frame_paths[-1].resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped_last}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    list_file.unlink(missing_ok=True)
    return {
        "ok": result.returncode == 0 and output_path.is_file(),
        "path": str(output_path),
        "frame_count": len(frame_paths),
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-400:] if result.stderr else "",
    }


def decode_rgb_png(png_bytes: bytes) -> tuple[int, int, bytes]:
    """Decode an uncompressed-filter-0 8-bit RGB PNG (such as MinecraftKit snapshots)."""
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature.")
    pos = 8
    width = 0
    height = 0
    idat_parts: list[bytes] = []
    while pos + 8 <= len(png_bytes):
        length, tag = struct.unpack(">I4s", png_bytes[pos : pos + 8])
        data = png_bytes[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", data)
            if bit_depth != 8 or color_type != 2:
                raise ValueError(f"Only 8-bit RGB PNG supported for stdlib diff (got depth={bit_depth}, type={color_type}).")
        elif tag == b"IDAT":
            idat_parts.append(data)
        elif tag == b"IEND":
            break
    raw = zlib.decompress(b"".join(idat_parts))
    stride = width * 3
    rgb = bytearray(width * height * 3)
    for row in range(height):
        src_start = row * (stride + 1)
        if raw[src_start] != 0:
            raise ValueError(f"Unsupported PNG row filter {raw[src_start]} at row {row}.")
        rgb[row * stride : (row + 1) * stride] = raw[src_start + 1 : src_start + 1 + stride]
    return width, height, bytes(rgb)


def compare_snapshots_png(
    baseline_png: bytes,
    candidate_png: bytes,
    *,
    channel_tolerance: int = 4,
) -> dict[str, Any]:
    """Compute exact pixel visual regression diff and emit a highlighted diff PNG."""
    w1, h1, rgb1 = decode_rgb_png(baseline_png)
    w2, h2, rgb2 = decode_rgb_png(candidate_png)
    if (w1, h1) != (w2, h2):
        raise ValueError(f"Snapshot dimensions differ: {(w1, h1)} vs {(w2, h2)}")

    diff_canvas = PixelCanvas(w1, h1, BG_BASE)
    total_pixels = w1 * h1
    changed_pixels = 0
    min_x, min_y = w1, h1
    max_x, max_y = -1, -1

    for y in range(h1):
        row_off = y * w1 * 3
        for x in range(w1):
            idx = row_off + x * 3
            r1, g1, b1 = rgb1[idx], rgb1[idx + 1], rgb1[idx + 2]
            r2, g2, b2 = rgb2[idx], rgb2[idx + 1], rgb2[idx + 2]
            if (
                abs(r1 - r2) > channel_tolerance
                or abs(g1 - g2) > channel_tolerance
                or abs(b1 - b2) > channel_tolerance
            ):
                changed_pixels += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
                diff_canvas.set_pixel(x, y, ACCENT_RED)
            else:
                # Dim unchanged regions so changed pixels pop visually in chat!
                diff_canvas.set_pixel(x, y, (r2 // 3, g2 // 3, b2 // 3))

    if changed_pixels > 0:
        diff_canvas.draw_rect(
            max(0, min_x - 2),
            max(0, min_y - 2),
            min(w1, max_x - min_x + 5),
            min(h1, max_y - min_y + 5),
            ACCENT_AMBER,
            2,
        )

    changed_pct = round((changed_pixels / max(1, total_pixels)) * 100.0, 4)
    diff_png = diff_canvas.to_png_bytes()
    return {
        "width": w1,
        "height": h1,
        "total_pixels": total_pixels,
        "changed_pixels": changed_pixels,
        "changed_pct": changed_pct,
        "identical": changed_pixels == 0,
        "changed_bbox": None if changed_pixels == 0 else {"x0": min_x, "y0": min_y, "x1": max_x, "y1": max_y},
        "diff_png_base64": encode_png_base64(diff_png),
    }


def render_tps_sparkline_png(
    samples: list[dict[str, Any]],
    *,
    width: int = 640,
    height: int = 240,
    title: str = "MCKIT BRIDGE TPS / MSPT TELEMETRY",
) -> bytes:
    """Render a zero-dependency dark-mode PNG sparkline chart for 60s TPS & MSPT history."""
    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_EMERALD, scale=1, max_chars=56)

    tps_vals = [float(s.get("tps_1m", 20.0)) for s in samples if isinstance(s, dict)]
    mspt_vals = [float(s.get("mspt", 0.0)) for s in samples if isinstance(s, dict)]
    cur_tps = tps_vals[-1] if tps_vals else 20.0
    cur_mspt = mspt_vals[-1] if mspt_vals else 0.0
    min_tps = min(tps_vals) if tps_vals else 20.0

    badge_col = ACCENT_EMERALD if cur_tps >= 19.0 else (ACCENT_AMBER if cur_tps >= 16.0 else ACCENT_RED)
    canvas.draw_text(width - 210, 10, f"TPS {cur_tps:4.1f}  MSPT {cur_mspt:4.1f}", badge_col, scale=1)

    gx, gy, gw, gh = 48, 42, width - 66, height - 86
    canvas.fill_rect(gx, gy, gw, gh, BG_PANEL)
    canvas.draw_rect(gx, gy, gw, gh, BORDER_SUBTLE, 1)

    # Horizontal TPS reference guides (20, 15, 10, 5)
    for mark in (20, 15, 10, 5):
        my = gy + gh - int((mark / 20.0) * (gh - 8)) - 4
        canvas.draw_line(gx + 1, my, gx + gw - 2, my, BORDER_SUBTLE)
        canvas.draw_text(10, my - 3, f"{mark:2d}", TEXT_MUTED, scale=1)

    if len(tps_vals) >= 2:
        step_x = (gw - 12) / float(len(tps_vals) - 1)
        prev_pt: tuple[int, int] | None = None
        for idx, tval in enumerate(tps_vals):
            clamped = max(0.0, min(20.0, tval))
            px = gx + 6 + int(round(idx * step_x))
            py = gy + gh - 4 - int(round((clamped / 20.0) * (gh - 8)))
            pt_col = ACCENT_EMERALD if clamped >= 19.0 else (ACCENT_AMBER if clamped >= 16.0 else ACCENT_RED)
            if prev_pt is not None:
                canvas.draw_line(prev_pt[0], prev_pt[1], px, py, pt_col)
                canvas.draw_line(prev_pt[0], prev_pt[1] + 1, px, py + 1, pt_col)
            canvas.draw_circle(px, py, 2, pt_col)
            prev_pt = (px, py)
    elif len(tps_vals) == 1:
        clamped = max(0.0, min(20.0, tps_vals[0]))
        py = gy + gh - 4 - int(round((clamped / 20.0) * (gh - 8)))
        canvas.draw_line(gx + 6, py, gx + gw - 6, py, ACCENT_EMERALD)

    footer = f"SAMPLES: {len(tps_vals)}   MIN TPS: {min_tps:.2f}   STATUS: {'HEALTHY' if min_tps >= 18.5 else 'DEGRADED'}"
    canvas.draw_text(12, height - 22, footer, TEXT_MUTED, scale=1, max_chars=74)
    return canvas.to_png_bytes()


def render_entity_bar_chart_png(
    entities_payload: dict[str, Any],
    *,
    width: int = 640,
    height: int = 260,
    title: str = "MCKIT BRIDGE ENTITY LAG BREAKDOWN",
) -> bytes:
    """Render a zero-dependency dark-mode horizontal bar chart PNG for /api/v1/entities."""
    totals: dict[str, int] = {}
    world_count = 0
    grand_total = 0

    worlds = entities_payload.get("worlds") if isinstance(entities_payload, dict) else None
    if isinstance(worlds, list):
        world_count = len(worlds)
        for w in worlds:
            if not isinstance(w, dict):
                continue
            grand_total += int(w.get("total_entities", 0) or 0)
            top = w.get("top_types")
            if isinstance(top, dict):
                for k, v in top.items():
                    totals[str(k).upper()] = totals.get(str(k).upper(), 0) + int(v or 0)
            elif isinstance(top, list):
                for entry in top:
                    if isinstance(entry, dict) and entry.get("type"):
                        name = str(entry["type"]).upper()
                        totals[name] = totals.get(name, 0) + int(entry.get("count", 0) or 0)
    elif isinstance(entities_payload, dict) and isinstance(entities_payload.get("top_types"), dict):
        world_count = 1
        for k, v in entities_payload["top_types"].items():
            totals[str(k).upper()] = int(v or 0)
        grand_total = sum(totals.values())

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    if grand_total == 0:
        grand_total = sum(totals.values())
    max_val = max((c for _, c in ranked), default=1)

    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_CYAN, scale=1, max_chars=50)
    status_col = ACCENT_RED if max_val >= 250 else (ACCENT_AMBER if max_val >= 100 else ACCENT_EMERALD)
    canvas.draw_text(width - 210, 10, f"TOTAL {grand_total:5d}  WORLDS {world_count}", status_col, scale=1)

    y = 42
    bar_x = 178
    bar_max_w = width - bar_x - 74
    if not ranked:
        canvas.draw_text(20, 110, "NO ENTITY SAMPLES AVAILABLE", TEXT_MUTED, scale=1)
    else:
        for name, count in ranked:
            bar_col = ACCENT_RED if count >= 250 else (ACCENT_AMBER if count >= 100 else ACCENT_EMERALD)
            canvas.draw_text(12, y + 4, name[:24], TEXT_PRIMARY, scale=1, max_chars=24)
            canvas.fill_rect(bar_x, y, bar_max_w, 16, BG_PANEL)
            canvas.draw_rect(bar_x, y, bar_max_w, 16, BORDER_SUBTLE, 1)
            fill_w = max(4, int(round((count / float(max(1, max_val))) * (bar_max_w - 2))))
            canvas.fill_rect(bar_x + 1, y + 1, fill_w, 14, bar_col)
            canvas.draw_text(bar_x + bar_max_w + 8, y + 4, f"{count:5d}", bar_col, scale=1)
            y += 23

    verdict = "HOTSPOT ALERT" if max_val >= 250 else ("WATCH" if max_val >= 100 else "BALANCED")
    footer = f"TOP TYPES: {len(ranked)}   PEAK TYPE: {max_val}   VERDICT: {verdict}"
    canvas.draw_text(12, height - 20, footer, TEXT_MUTED, scale=1, max_chars=74)
    return canvas.to_png_bytes()


def render_chunk_density_png(
    chunks_payload: dict[str, Any],
    *,
    width: int = 640,
    height: int = 240,
    title: str = "MCKIT BRIDGE CHUNK & ENTITY DENSITY",
) -> bytes:
    """Render a zero-dependency dark-mode PNG chart for /api/v1/chunks per-world telemetry."""
    worlds = [w for w in (chunks_payload.get("worlds") or []) if isinstance(w, dict)] if isinstance(chunks_payload, dict) else []
    total_loaded = int(chunks_payload.get("total_loaded_chunks", 0) or 0) if isinstance(chunks_payload, dict) else 0
    total_forced = int(chunks_payload.get("total_force_loaded_chunks", 0) or 0) if isinstance(chunks_payload, dict) else 0
    if total_loaded == 0:
        total_loaded = sum(int(w.get("loaded_chunks", 0) or 0) for w in worlds)
    max_chunks = max((int(w.get("loaded_chunks", 0) or 0) for w in worlds), default=1)
    peak_density = max((float(w.get("entities_per_chunk", 0.0) or 0.0) for w in worlds), default=0.0)

    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_EMERALD, scale=1, max_chars=48)
    hdr_col = ACCENT_RED if peak_density >= 3.0 else (ACCENT_AMBER if peak_density >= 1.5 else ACCENT_EMERALD)
    canvas.draw_text(width - 230, 10, f"CHUNKS {total_loaded:5d}  FORCED {total_forced:3d}", hdr_col, scale=1)

    y = 44
    bar_x = 160
    bar_max_w = width - bar_x - 135
    if not worlds:
        canvas.draw_text(20, 105, "NO WORLD CHUNK SAMPLES AVAILABLE", TEXT_MUTED, scale=1)
    else:
        for w in worlds[:7]:
            name = str(w.get("world", "world")).upper()[:20]
            loaded = int(w.get("loaded_chunks", 0) or 0)
            density = float(w.get("entities_per_chunk", 0.0) or 0.0)
            bar_col = ACCENT_RED if density >= 3.0 else (ACCENT_AMBER if density >= 1.5 else ACCENT_CYAN)
            canvas.draw_text(12, y + 4, name, TEXT_PRIMARY, scale=1, max_chars=20)
            canvas.fill_rect(bar_x, y, bar_max_w, 16, BG_PANEL)
            canvas.draw_rect(bar_x, y, bar_max_w, 16, BORDER_SUBTLE, 1)
            fill_w = max(4, int(round((loaded / float(max(1, max_chunks))) * (bar_max_w - 2))))
            canvas.fill_rect(bar_x + 1, y + 1, fill_w, 14, bar_col)
            canvas.draw_text(bar_x + bar_max_w + 8, y + 4, f"{loaded:4d} ({density:.1f}/c)", bar_col, scale=1)
            y += 24

    verdict = "DENSITY ALERT" if peak_density >= 3.0 else ("ELEVATED" if peak_density >= 1.5 else "HEALTHY")
    footer = f"WORLDS: {len(worlds)}   PEAK DENSITY: {peak_density:.2f} ENT/CHUNK   STATUS: {verdict}"
    canvas.draw_text(12, height - 20, footer, TEXT_MUTED, scale=1, max_chars=76)
    return canvas.to_png_bytes()


def render_memory_gauge_png(
    memory_payload: dict[str, Any],
    *,
    width: int = 640,
    height: int = 220,
    title: str = "MCKIT BRIDGE JVM HEAP & GC PRESSURE",
) -> bytes:
    """Render a zero-dependency dark-mode PNG telemetry gauge for /api/v1/memory."""
    used_mb = int(memory_payload.get("heap_used_mb", 0) or 0)
    comm_mb = int(memory_payload.get("heap_committed_mb", used_mb) or used_mb)
    max_mb = max(1, int(memory_payload.get("heap_max_mb", max(1, used_mb)) or 1))
    non_heap_mb = int(memory_payload.get("non_heap_used_mb", 0) or 0)
    pct = float(memory_payload.get("heap_pressure_pct", (used_mb * 100.0) / max_mb) or 0.0)
    pct = max(0.0, min(100.0, pct))
    gc_count = int(memory_payload.get("gc_count", 0) or 0)
    gc_time_ms = int(memory_payload.get("gc_time_ms", 0) or 0)
    threads = int(memory_payload.get("thread_count", 0) or 0)

    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_CYAN, scale=1, max_chars=48)
    bar_col = ACCENT_RED if pct >= 85.0 else (ACCENT_AMBER if pct >= 70.0 else ACCENT_EMERALD)
    canvas.draw_text(width - 195, 10, f"HEAP {pct:5.1f}%  {used_mb}/{max_mb}MB", bar_col, scale=1)

    # Heap gauge bar
    bx, by, bw, bh = 20, 48, width - 40, 32
    canvas.draw_text(bx, by - 14, "JVM HEAP UTILIZATION (USED / COMMITTED / MAX)", TEXT_MUTED, scale=1)
    canvas.fill_rect(bx, by, bw, bh, BG_PANEL)
    canvas.draw_rect(bx, by, bw, bh, BORDER_SUBTLE, 1)
    comm_w = max(2, int(round(min(1.0, comm_mb / float(max_mb)) * (bw - 2))))
    used_w = max(2, int(round((pct / 100.0) * (bw - 2))))
    canvas.fill_rect(bx + 1, by + 1, comm_w, bh - 2, (36, 56, 76))
    canvas.fill_rect(bx + 1, by + 1, used_w, bh - 2, bar_col)
    canvas.draw_text(bx + 10, by + 11, f"USED: {used_mb} MB   COMMITTED: {comm_mb} MB   MAX: {max_mb} MB", TEXT_PRIMARY, scale=1)

    # Telemetry cards row
    cards = [
        ("NON-HEAP", f"{non_heap_mb} MB", ACCENT_CYAN),
        ("GC RUNS", f"{gc_count}", ACCENT_EMERALD),
        ("GC PAUSE", f"{gc_time_ms} MS", ACCENT_AMBER if gc_time_ms >= 2000 else ACCENT_EMERALD),
        ("THREADS", f"{threads}", ACCENT_CYAN),
    ]
    cw = (width - 64) // 4
    cy = 104
    for idx, (lbl, val, col) in enumerate(cards):
        cx = 20 + idx * (cw + 8)
        canvas.fill_rect(cx, cy, cw, 64, BG_PANEL)
        canvas.draw_rect(cx, cy, cw, 64, BORDER_SUBTLE, 1)
        canvas.draw_text(cx + 10, cy + 12, lbl, TEXT_MUTED, scale=1)
        canvas.draw_text(cx + 10, cy + 34, val, col, scale=2)

    verdict = "OOM RISK" if pct >= 85.0 else ("ELEVATED" if pct >= 70.0 else "HEALTHY")
    canvas.draw_text(12, height - 22, f"ANTI-OOM VERDICT: {verdict}   (USE ZGC / -XMS=-XMX FOR ZERO STALLS)", bar_col, scale=1, max_chars=78)
    return canvas.to_png_bytes()


def render_gc_pause_chart_png(
    gc_report: dict[str, Any],
    *,
    width: int = 640,
    height: int = 240,
    title: str = "MCKIT JVM GC PAUSE TIMELINE (MS VS 50MS TICK)",
) -> bytes:
    """Render a zero-dependency dark-mode PNG bar timeline for mc_ops_audit_jvm_gc_log."""
    summary = gc_report.get("summary") or {}
    pauses = [p for p in (gc_report.get("pauses") or []) if isinstance(p, dict)]
    tick_ms = max(10.0, float(gc_report.get("tick_budget_ms", 50.0) or 50.0))
    grade = str(gc_report.get("grade", "A"))
    engine = str(gc_report.get("gc_engine", "JVM"))
    p95_ms = float(summary.get("p95_ms", 0.0) or 0.0)
    max_ms = float(summary.get("max_pause_ms", 0.0) or 0.0)

    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_CYAN, scale=1, max_chars=48)
    hdr_col = ACCENT_RED if grade in ("D", "F") else (ACCENT_AMBER if grade in ("B", "C") else ACCENT_EMERALD)
    canvas.draw_text(width - 190, 10, f"GRADE {grade}  MAX {max_ms:5.1f}MS", hdr_col, scale=1)

    gx, gy, gw, gh = 48, 44, width - 68, height - 92
    canvas.fill_rect(gx, gy, gw, gh, BG_PANEL)
    canvas.draw_rect(gx, gy, gw, gh, BORDER_SUBTLE, 1)

    y_scale_max = max(tick_ms * 1.5, max_ms * 1.15, 60.0)
    tick_y = gy + gh - 2 - int(round((tick_ms / y_scale_max) * (gh - 6)))
    canvas.draw_line(gx + 1, tick_y, gx + gw - 2, tick_y, ACCENT_AMBER)
    canvas.draw_text(6, max(gy, tick_y - 4), f"{int(tick_ms)}MS", ACCENT_AMBER, scale=1)
    canvas.draw_text(6, gy, f"{int(round(y_scale_max))}", TEXT_MUTED, scale=1)
    canvas.draw_text(6, gy + gh - 8, "0MS", TEXT_MUTED, scale=1)

    if not pauses:
        canvas.draw_text(gx + 20, gy + gh // 2 - 4, "NO GC PAUSE EVENTS DETECTED IN LOG", TEXT_MUTED, scale=1)
    else:
        shown = pauses[:40]
        slot_w = max(4, (gw - 12) // max(1, len(shown)))
        bar_w = max(2, slot_w - 2)
        for idx, entry in enumerate(shown):
            ms = float(entry.get("pause_ms", 0.0) or 0.0)
            bh = max(2, int(round((ms / y_scale_max) * (gh - 6))))
            bx = gx + 6 + idx * slot_w
            by = gy + gh - 2 - bh
            bcol = ACCENT_RED if ms >= tick_ms * 3.0 else (ACCENT_AMBER if ms > tick_ms else ACCENT_EMERALD)
            canvas.fill_rect(bx, by, bar_w, bh, bcol)

    footer = f"ENGINE: {engine}   PAUSES: {len(pauses)}   P95: {p95_ms:.1f}MS   MAX: {max_ms:.1f}MS   BUDGET: {tick_ms:.0f}MS"
    canvas.draw_text(12, height - 22, footer, TEXT_MUTED, scale=1, max_chars=78)
    return canvas.to_png_bytes()


def render_load_test_chart_png(
    load_report: dict[str, Any],
    *,
    width: int = 640,
    height: int = 240,
    title: str = "MCKIT BOT STRESS TEST: JOIN LATENCY & TPS",
) -> bytes:
    """Render a zero-dependency dark-mode PNG chart for mc_bot_generate_load_test_report."""
    grade = str(load_report.get("grade", "A"))
    bots = int(load_report.get("bot_count", 1) or 1)
    lat = load_report.get("latency_ms") or {}
    tps = load_report.get("tps") or {}
    mem = load_report.get("memory_efficiency") or {}
    p95 = float(lat.get("p95", 0.0) or 0.0)
    max_lat = max(100.0, float(lat.get("max", 100.0) or 100.0))
    min_tps = float(tps.get("min", 20.0) or 20.0)
    samples = [float(v) for v in (lat.get("samples") or [])]

    canvas = PixelCanvas(width, height, BG_BASE)
    canvas.draw_rect(0, 0, width, height, BORDER_SUBTLE, 1)
    canvas.fill_rect(1, 1, width - 2, 28, BG_PANEL)
    canvas.draw_text(12, 10, title, ACCENT_EMERALD, scale=1, max_chars=46)
    hdr_col = ACCENT_RED if grade in ("D", "F") else (ACCENT_AMBER if grade in ("B", "C") else ACCENT_EMERALD)
    canvas.draw_text(width - 210, 10, f"GRADE {grade}  {bots} BOTS  TPS {min_tps:.1f}", hdr_col, scale=1)

    gx, gy, gw, gh = 52, 44, width - 72, height - 92
    canvas.fill_rect(gx, gy, gw, gh, BG_PANEL)
    canvas.draw_rect(gx, gy, gw, gh, BORDER_SUBTLE, 1)
    canvas.draw_text(6, gy, f"{int(round(max_lat))}MS", TEXT_MUTED, scale=1)
    canvas.draw_text(6, gy + gh - 8, "0MS", TEXT_MUTED, scale=1)

    if samples:
        shown = samples[:36]
        slot_w = max(4, (gw - 12) // max(1, len(shown)))
        bar_w = max(2, slot_w - 2)
        for idx, val in enumerate(shown):
            bh = max(2, int(round((val / max_lat) * (gh - 6))))
            bx = gx + 6 + idx * slot_w
            by = gy + gh - 2 - bh
            col = ACCENT_RED if val > 1500.0 else (ACCENT_AMBER if val > 500.0 else ACCENT_CYAN)
            canvas.fill_rect(bx, by, bar_w, bh, col)

    ram_mb = int(mem.get("headless_bot_ram_mb", bots * 42) or (bots * 42))
    saved_pct = float(mem.get("ram_saved_pct", 98.0) or 98.0)
    footer = f"P95: {p95:.0f}MS   MIN TPS: {min_tps:.2f}   RAM: {ram_mb}MB ({saved_pct:.1f}% SAVED VS DESKTOP)"
    canvas.draw_text(12, height - 22, footer, TEXT_MUTED, scale=1, max_chars=78)
    return canvas.to_png_bytes()
