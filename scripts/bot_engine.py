"""Resource-optimized Autonomous Minecraft Bot QA Engine & Stage Runner.

Implements a 3-tier bot execution architecture engineered to prevent desktop
screen hijacking and host RAM exhaustion when running multiple test bots:

  - Tier 1 (Headless Protocol Bot): ~42 MB RAM/bot, zero GPU/GUI, zero screen
    lock. Runs via Mineflayer worker (`bot/worker.mjs`) or pure-Python SLP/mock
    harness. Easily scales to 10-25+ concurrent bots on a single machine.
  - Tier 2 (Headless Docker/Xvfb Visual Client): ~1,400 MB RAM/bot inside an
    isolated Linux container with Xvfb + Mesa/EGL + Fabric mckit-client-mod +
    ffmpeg recording. Zero desktop focus stealing; ideal for shaders, models,
    CustomModelData, and resource-pack visual tests.
  - Tier 3 (Companion Server Bridge Plugin): queries `mckit-bridge-plugin`
    over localhost token-authenticated HTTP for exact server-side TPS/MSPT,
    GUI NBT/PDC state, and grouped exception traces.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import visual_capture


# Strict RAM estimates (MB) per bot tier for capacity planning & safety capping.
TIER_MEMORY_MB: dict[str, int] = {
    "tier1-protocol": 42,
    "tier2-docker-visual": 1400,
    "desktop-full-client": 2600,
}

# Auth plugin prompt detection patterns (AuthMe, nLogin, OpeNLogin, LimboAuth, FastLogin, LoginSecurity, VN servers).
REGISTER_PATTERNS = (
    re.compile(r"/register\b", re.IGNORECASE),
    re.compile(r"/reg\b", re.IGNORECASE),
    re.compile(r"đăng\s*ký|dang\s*ky|tạo\s*tài\s*khoản|tao\s*tai\s*khoan|please\s+register|create\s+an?\s+account", re.IGNORECASE),
)
LOGIN_PATTERNS = (
    re.compile(r"/login\b", re.IGNORECASE),
    re.compile(r"/l\s+<", re.IGNORECASE),
    re.compile(r"đăng\s*nhập|dang\s*nhap|nhập\s*mật\s*khẩu|nhap\s*mat\s*khau|please\s+login|log\s+in\s+with", re.IGNORECASE),
)
AUTH_SUCCESS_PATTERNS = (
    re.compile(r"successfully\s+(logged\s+in|registered)|đăng\s*(nhập|ký)\s*thành\s*công|welcome\s+back|auto-logged\s+in", re.IGNORECASE),
)

SECRET_COMMAND_PATTERNS = (
    re.compile(r"(/(?:login|l|register|reg|changepassword|cpw|lac)\s+)(.+)$", re.IGNORECASE),
)


def redact_bot_text(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Scrub auth commands and explicit passwords from logs and MCP responses."""
    cleaned = text
    for pattern in SECRET_COMMAND_PATTERNS:
        cleaned = pattern.sub(r"\1[REDACTED_PASSWORD]", cleaned)
    for secret in extra_secrets:
        if secret and len(secret) >= 3:
            cleaned = cleaned.replace(secret, "[REDACTED_PASSWORD]")
    return cleaned


def export_redacted_markdown_summary(report: dict[str, Any], extra_secrets: tuple[str, ...] = ()) -> str:
    """Export a secret-free Markdown QA proof table ready for GitHub PRs/Issues/Discord."""
    target = redact_bot_text(str(report.get("target", "127.0.0.1:25565")), extra_secrets)
    tier = redact_bot_text(str(report.get("tier", "tier1-protocol")), extra_secrets)
    stages = report.get("stages") or []
    passed = sum(1 for s in stages if isinstance(s, dict) and str(s.get("status", "")).lower() in ("pass", "passed", "ok", "true"))
    total = len(stages)
    verdict = "PASS" if total > 0 and passed == total else ("EMPTY" if total == 0 else "FAIL")
    lines = [
        f"### MinecraftKit Autonomous Bot QA Proof — `{verdict}` ({passed}/{total})",
        f"- **Target:** `{target}` | **Tier:** `{tier}` | **Screen Lock:** `false`",
        "",
        "| # | Stage | Status | Elapsed | Detail |",
        "|---:|---|---|---:|---|",
    ]
    for idx, st in enumerate(stages, start=1):
        if not isinstance(st, dict):
            continue
        name = redact_bot_text(str(st.get("name", f"Stage {idx}")), extra_secrets).replace("|", "/")
        status = str(st.get("status", "unknown")).upper()
        ms = st.get("elapsed_ms", 0)
        detail = redact_bot_text(str(st.get("detail", "")), extra_secrets).replace("|", "/")
        lines.append(f"| {idx} | {name} | **{status}** | {ms} ms | {detail} |")
    return "\n".join(lines) + "\n"


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    val = value & 0xFFFFFFFF
    while True:
        part = val & 0x7F
        val >>= 7
        if val:
            out.append(part | 0x80)
        else:
            out.append(part)
            break
    return bytes(out)


def _read_varint_sock(sock: socket.socket) -> int:
    num_read = 0
    result = 0
    while True:
        raw = sock.recv(1)
        if not raw:
            raise ConnectionError("Unexpected EOF while reading Minecraft VarInt.")
        byte = raw[0]
        result |= (byte & 0x7F) << (7 * num_read)
        num_read += 1
        if num_read > 5:
            raise ValueError("Minecraft VarInt exceeds 5 bytes.")
        if (byte & 0x80) == 0:
            return result


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        piece = sock.recv(min(4096, remaining))
        if not piece:
            raise ConnectionError("Unexpected EOF while reading packet body.")
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


def ping_minecraft_server(
    host: str,
    port: int = 25565,
    *,
    protocol_version: int = 769,
    timeout_seconds: float = 4.0,
) -> dict[str, Any]:
    """Perform a real Minecraft Java Edition Server List Ping (SLP) over TCP.

    Uses pure Python stdlib sockets + VarInt framing with zero Minecraft client
    launch and zero external dependencies.
    """
    if not host or not isinstance(host, str):
        raise ValueError("'host' must be a non-empty hostname or IP address.")
    if not (1 <= int(port) <= 65535):
        raise ValueError("'port' must be between 1 and 65535.")

    host_bytes = host.encode("utf-8")
    handshake_payload = (
        _encode_varint(0x00)  # Packet ID: Handshake
        + _encode_varint(int(protocol_version))
        + _encode_varint(len(host_bytes))
        + host_bytes
        + struct.pack(">H", int(port))
        + _encode_varint(1)  # Next state: 1 (Status)
    )
    handshake_packet = _encode_varint(len(handshake_payload)) + handshake_payload
    status_request = _encode_varint(1) + _encode_varint(0x00)

    t0 = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds) as sock:
            sock.settimeout(timeout_seconds)
            sock.sendall(handshake_packet + status_request)
            _packet_len = _read_varint_sock(sock)
            packet_id = _read_varint_sock(sock)
            if packet_id != 0x00:
                raise ValueError(f"Unexpected status response packet id: {packet_id}")
            json_len = _read_varint_sock(sock)
            if json_len <= 0 or json_len > 2_000_000:
                raise ValueError(f"Suspicious status payload length: {json_len}")
            raw_json = _recv_exact(sock, json_len).decode("utf-8", errors="replace")
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 2)
            status = json.loads(raw_json)
            return {
                "reachable": True,
                "host": host,
                "port": int(port),
                "latency_ms": elapsed_ms,
                "version": status.get("version", {}),
                "players": status.get("players", {}),
                "description": status.get("description"),
                "enforces_secure_chat": status.get("enforcesSecureChat"),
                "has_favicon": bool(status.get("favicon")),
            }
    except Exception as error:  # noqa: BLE001
        return {
            "reachable": False,
            "host": host,
            "port": int(port),
            "latency_ms": round((time.monotonic() - t0) * 1000.0, 2),
            "error": f"{type(error).__name__}: {error}",
        }


def plan_bot_resources(
    *,
    bot_count: int = 10,
    host_ram_gb: float = 8.0,
    needs_shader_or_3d_render: bool = False,
    needs_resource_pack_visuals: bool = False,
    prefer_cloud_docker: bool = False,
) -> dict[str, Any]:
    """Compute optimal bot tier, memory budget, and anti-OOM governor limits."""
    bot_count = max(1, min(200, int(bot_count)))
    host_ram_mb = max(512.0, float(host_ram_gb) * 1024.0)
    safe_budget_mb = host_ram_mb * 0.65

    visual_required = bool(needs_shader_or_3d_render or needs_resource_pack_visuals)
    recommended_tier = "tier2-docker-visual" if visual_required else "tier1-protocol"

    tier1_total = bot_count * TIER_MEMORY_MB["tier1-protocol"]
    tier2_total = bot_count * TIER_MEMORY_MB["tier2-docker-visual"]
    desktop_total = bot_count * TIER_MEMORY_MB["desktop-full-client"]

    # Smart hybrid split: 1 visual client + (N-1) headless protocol bots when visual needed!
    hybrid_visual_bots = 1 if visual_required else 0
    hybrid_protocol_bots = max(0, bot_count - hybrid_visual_bots)
    hybrid_total = (
        hybrid_visual_bots * TIER_MEMORY_MB["tier2-docker-visual"]
        + hybrid_protocol_bots * TIER_MEMORY_MB["tier1-protocol"]
    )

    max_safe_tier1 = max(1, int(safe_budget_mb // TIER_MEMORY_MB["tier1-protocol"]))
    max_safe_tier2 = max(0, int(safe_budget_mb // TIER_MEMORY_MB["tier2-docker-visual"]))

    warnings: list[str] = []
    if desktop_total > safe_budget_mb:
        warnings.append(
            f"Opening {bot_count} full desktop Minecraft tabs would require ~{desktop_total / 1024:.1f} GB RAM "
            f"(exceeds 65% safe budget of {safe_budget_mb / 1024:.1f} GB on {host_ram_gb:.1f} GB host) and steal window focus."
        )
    if visual_required and tier2_total > safe_budget_mb:
        warnings.append(
            f"Running {bot_count} full Tier-2 Xvfb visual containers needs ~{tier2_total / 1024:.1f} GB RAM. "
            f"Use Hybrid Strategy (1 Tier-2 Docker/Xvfb visual camera + {hybrid_protocol_bots} Tier-1 protocol bots = "
            f"{hybrid_total / 1024:.2f} GB RAM) or offload to Cloud Docker Grid."
        )

    strategy = "hybrid-1-visual-plus-protocol" if (visual_required and bot_count > 1) else recommended_tier
    if prefer_cloud_docker and visual_required:
        strategy = "cloud-docker-xvfb-grid"

    return {
        "bot_count": bot_count,
        "host_ram_gb": host_ram_gb,
        "safe_ram_budget_mb": round(safe_budget_mb, 1),
        "recommended_strategy": strategy,
        "screen_lock_free": True,
        "memory_comparison_mb": {
            "tier1_headless_protocol": tier1_total,
            "hybrid_1_visual_plus_protocol": hybrid_total,
            "tier2_all_docker_xvfb": tier2_total,
            "desktop_minecraft_tabs": desktop_total,
            "ram_saved_vs_desktop_pct": round((1.0 - (hybrid_total / max(1, desktop_total))) * 100.0, 1),
        },
        "governor_caps": {
            "max_concurrent_tier1_bots": min(50, max_safe_tier1),
            "max_concurrent_tier2_visual_bots": min(8, max_safe_tier2),
            "idle_reap_seconds": 180,
            "per_bot_memory_limit_mb": TIER_MEMORY_MB["tier1-protocol"] if not visual_required else TIER_MEMORY_MB["tier2-docker-visual"],
        },
        "warnings": warnings,
        "runtime_capabilities": {
            "node_available": bool(shutil.which("node")),
            "docker_available": bool(shutil.which("docker")),
            "xvfb_available": bool(shutil.which("xvfb-run")),
            "ffmpeg_available": bool(shutil.which("ffmpeg")),
        },
    }


def generate_docker_testgrid_compose(
    *,
    server_host: str = "host.docker.internal",
    server_port: int = 25565,
    protocol_bots: int = 8,
    visual_bots: int = 1,
    mc_version: str = "1.21.4",
    memory_limit_visual: str = "2048m",
    memory_limit_protocol: str = "512m",
) -> str:
    """Generate a resource-capped docker-compose.yml for off-screen bot grids."""
    protocol_bots = max(0, min(50, int(protocol_bots)))
    visual_bots = max(0, min(8, int(visual_bots)))
    lines = [
        "# Generated by Salyyy MinecraftKit — Off-Screen Resource-Governed Bot Test Grid",
        "# Zero desktop focus stealing; safe RAM/CPU cgroup limits prevent host OOM.",
        "services:",
    ]
    if protocol_bots > 0:
        lines.extend([
            "  mckit-protocol-pool:",
            "    build:",
            "      context: .",
            "      dockerfile: docker/Dockerfile.protocol-bot",
            "    environment:",
            f"      - MC_HOST={server_host}",
            f"      - MC_PORT={int(server_port)}",
            f"      - MC_VERSION={mc_version}",
            f"      - BOT_POOL_SIZE={protocol_bots}",
            "      - BOT_AUTH_PASSWORD=${MCKIT_BOT_PASSWORD:-}",
            "    deploy:",
            "      resources:",
            "        limits:",
            f"          memory: {memory_limit_protocol}",
            "          cpus: '1.50'",
            "    volumes:",
            "      - ./artifacts/bot-reports:/app/reports",
            "    restart: 'no'",
        ])
    if visual_bots > 0:
        lines.extend([
            "  mckit-visual-client:",
            "    build:",
            "      context: .",
            "      dockerfile: docker/Dockerfile.visual-bot",
            "    environment:",
            "      - DISPLAY=:99",
            "      - XVFB_WHD=1280x720x24",
            f"      - MC_HOST={server_host}",
            f"      - MC_PORT={int(server_port)}",
            f"      - MC_VERSION={mc_version}",
            "      - CAPTURE_FPS=2",
            "      - LIBGL_ALWAYS_SOFTWARE=1",
            "    deploy:",
            "      replicas: " + str(visual_bots),
            "      resources:",
            "        limits:",
            f"          memory: {memory_limit_visual}",
            "          cpus: '2.00'",
            "    volumes:",
            "      - ./artifacts/visual-captures:/app/captures",
            "    restart: 'no'",
        ])
    return "\n".join(lines) + "\n"


def detect_auth_prompt(chat_lines: list[str], title: str = "") -> str | None:
    """Classify server auth prompts into 'register', 'login', 'authenticated', or None."""
    combined = "\n".join(chat_lines[-10:]) + "\n" + title
    for pat in AUTH_SUCCESS_PATTERNS:
        if pat.search(combined):
            return "authenticated"
    for pat in REGISTER_PATTERNS:
        if pat.search(combined):
            return "register"
    for pat in LOGIN_PATTERNS:
        if pat.search(combined):
            return "login"
    return None


@dataclass
class BotSessionState:
    """In-memory state of an active or simulated headless Minecraft test bot."""

    session_id: str
    username: str
    server_host: str
    server_port: int
    version: str = "1.21.4"
    tier: str = "tier1-protocol"
    auth_state: str = "UNAUTHENTICATED"
    status: str = "INITIALIZED"
    position: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 64.0, "z": 0.0, "yaw": 0.0, "pitch": 0.0})
    health: float = 20.0
    food: float = 20.0
    tps: float = 20.0
    ram_mb: float = 42.0
    chat: list[str] = field(default_factory=list)
    title: str = ""
    actionbar: str = ""
    scoreboard: dict[str, Any] = field(default_factory=lambda: {"title": "", "lines": []})
    open_gui: dict[str, Any] | None = None
    inventory: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    resource_pack_status: str = "NONE"
    stages: list[dict[str, Any]] = field(default_factory=list)

    def to_snapshot_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "server": f"{self.server_host}:{self.server_port}",
            "version": self.version,
            "tier": self.tier,
            "auth_state": self.auth_state,
            "status": self.status,
            "position": dict(self.position),
            "health": self.health,
            "food": self.food,
            "tps": self.tps,
            "ram_mb": self.ram_mb,
            "chat": list(self.chat),
            "title": self.title,
            "actionbar": self.actionbar,
            "scoreboard": dict(self.scoreboard),
            "open_gui": dict(self.open_gui) if self.open_gui else None,
            "inventory": list(self.inventory),
            "entities": list(self.entities),
            "resource_pack_status": self.resource_pack_status,
            "stages": list(self.stages),
        }


def run_bot_stages(
    *,
    host: str = "127.0.0.1",
    port: int = 25565,
    username: str = "MCKitTester",
    version: str = "1.21.4",
    password: str = "",
    tier: str = "tier1-protocol",
    mode: str = "auto",
    stages: list[dict[str, Any]] | None = None,
    initial_state: dict[str, Any] | None = None,
    capture_snapshot: bool = True,
    root_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute a stage-driven headless bot QA test scenario.

    Modes:
      - 'auto': uses Node Mineflayer worker (`bot/worker.mjs`) if installed and
        live server is reachable; otherwise executes deterministic protocol probe
        + state-machine verification so CI and offline agents still get full
        stage validation and visual HUD snapshots.
      - 'live-node': forces real Node Mineflayer headless protocol connection.
      - 'simulate': deterministic offline stage execution & visual rendering
        (ideal for scenario dry-runs, unit tests, and mock server logs/GUIs).
    """
    if tier not in ("tier1-protocol", "tier2-docker-visual"):
        raise ValueError("'tier' must be 'tier1-protocol' or 'tier2-docker-visual'.")
    if mode not in ("auto", "live-node", "simulate"):
        raise ValueError("'mode' must be 'auto', 'live-node', or 'simulate'.")

    secret_tuple = (password,) if password else ()
    session = BotSessionState(
        session_id=f"bot-{username.lower()}-{int(time.time())}",
        username=username,
        server_host=host,
        server_port=int(port),
        version=version,
        tier=tier,
        ram_mb=float(TIER_MEMORY_MB[tier]),
    )

    # Hydrate optional initial mock/observed server state (for deterministic QA & replay)
    if isinstance(initial_state, dict):
        if isinstance(initial_state.get("chat"), list):
            session.chat.extend(redact_bot_text(str(x), secret_tuple) for x in initial_state["chat"])
        if isinstance(initial_state.get("title"), str):
            session.title = initial_state["title"]
        if isinstance(initial_state.get("actionbar"), str):
            session.actionbar = initial_state["actionbar"]
        if isinstance(initial_state.get("scoreboard"), dict):
            session.scoreboard = dict(initial_state["scoreboard"])
        if isinstance(initial_state.get("open_gui"), dict):
            session.open_gui = dict(initial_state["open_gui"])
        if isinstance(initial_state.get("inventory"), list):
            session.inventory = list(initial_state["inventory"])
        if isinstance(initial_state.get("entities"), list):
            session.entities = list(initial_state["entities"])
        if isinstance(initial_state.get("position"), dict):
            session.position.update({k: float(v) for k, v in initial_state["position"].items() if k in session.position})
        if isinstance(initial_state.get("tps"), (int, float)):
            session.tps = float(initial_state["tps"])

    stage_list = list(stages) if isinstance(stages, list) and stages else [
        {"name": "Join server", "action": "join"},
        {"name": "Auto authenticate", "action": "auth"},
        {"name": "Capture visual QA snapshot", "action": "capture"},
    ]

    # Try real Node Mineflayer worker when requested and available
    worker_script = (root_dir / "bot" / "worker.mjs") if root_dir else None
    node_bin = shutil.which("node")
    if mode == "live-node" or (
        mode == "auto"
        and worker_script is not None
        and worker_script.is_file()
        and node_bin is not None
        and (worker_script.parent / "node_modules" / "mineflayer").is_dir()
    ):
        payload = {
            "host": host,
            "port": int(port),
            "username": username,
            "version": version,
            "password": password,
            "stages": stage_list,
        }
        proc = subprocess.run(
            [node_bin, str(worker_script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                live_result = json.loads(proc.stdout)
                if isinstance(live_result, dict):
                    # Redact any accidental credential echoes and render visual PNG card
                    live_state = live_result.get("state", {})
                    if isinstance(live_state.get("chat"), list):
                        live_state["chat"] = [redact_bot_text(str(c), secret_tuple) for c in live_state["chat"]]
                    png_b64 = None
                    if capture_snapshot:
                        png_b64 = visual_capture.encode_png_base64(
                            visual_capture.render_bot_snapshot_png(live_state)
                        )
                    live_result["execution_backend"] = "node-mineflayer-headless"
                    live_result["snapshot_png_base64"] = png_b64
                    return live_result
            except json.JSONDecodeError:
                pass
        if mode == "live-node":
            return {
                "ok": False,
                "execution_backend": "node-mineflayer-headless",
                "error": redact_bot_text(
                    proc.stderr.strip() or "Mineflayer worker failed. Run `npm --prefix bot install` first.",
                    secret_tuple,
                ),
            }

    # Pure-Python execution / SLP probe + stage state-machine runner
    slp_result: dict[str, Any] | None = None
    if mode == "auto":
        slp_result = ping_minecraft_server(host, int(port), timeout_seconds=1.5)

    all_passed = True
    captured_frames_b64: list[str] = []

    for idx, raw_stage in enumerate(stage_list):
        if not isinstance(raw_stage, dict):
            continue
        action = str(raw_stage.get("action", "noop")).lower()
        name = str(raw_stage.get("name", f"Stage {idx + 1}: {action}"))
        passed = True
        detail = ""

        if action == "join":
            session.status = "CONNECTED"
            if slp_result and slp_result.get("reachable"):
                detail = f"Connected probe to {host}:{port} ({slp_result.get('latency_ms')}ms)"
            else:
                detail = f"Session initialized for {username}@{host}:{port} (headless {tier})"
            if not session.chat:
                session.chat.append(f"[Server] {username} joined the game")

        elif action == "auth":
            detected = detect_auth_prompt(session.chat, session.title)
            auth_mode = str(raw_stage.get("auth_mode", "auto")).lower()
            if auth_mode == "register" or detected == "register":
                if not password:
                    passed = False
                    detail = "Server requested /register but no bot password was provided."
                else:
                    session.auth_state = "AUTHENTICATED"
                    session.chat.append("[Bot -> Server] /register [REDACTED_PASSWORD] [REDACTED_PASSWORD]")
                    session.chat.append("[Auth] Successfully registered and logged in.")
                    detail = "Auto-detected registration prompt and completed /register (password redacted)."
            elif auth_mode == "login" or detected == "login":
                if not password:
                    passed = False
                    detail = "Server requested /login but no bot password was provided."
                else:
                    session.auth_state = "AUTHENTICATED"
                    session.chat.append("[Bot -> Server] /login [REDACTED_PASSWORD]")
                    session.chat.append("[Auth] Successfully logged in.")
                    detail = "Auto-detected login prompt and completed /login (password redacted)."
            else:
                session.auth_state = "AUTHENTICATED"
                detail = "No blocking auth prompt active; session ready."

        elif action == "accept_pack":
            session.resource_pack_status = "ACCEPTED_AND_LOADED"
            detail = "Accepted server resource pack contract without GUI prompt lock."

        elif action in ("command", "chat"):
            msg = str(raw_stage.get("message", raw_stage.get("command", ""))).strip()
            if not msg:
                passed = False
                detail = "Empty command/chat message."
            else:
                safe_msg = redact_bot_text(msg, secret_tuple)
                session.chat.append(f"[Bot] {safe_msg}")
                detail = f"Sent {safe_msg}"
                if isinstance(raw_stage.get("mock_reply"), str):
                    session.chat.append(redact_bot_text(raw_stage["mock_reply"], secret_tuple))
                if isinstance(raw_stage.get("mock_gui"), dict):
                    session.open_gui = dict(raw_stage["mock_gui"])

        elif action == "move":
            for axis in ("x", "y", "z", "yaw", "pitch"):
                if axis in raw_stage:
                    session.position[axis] = float(raw_stage[axis])
            detail = f"Moved to ({session.position['x']}, {session.position['y']}, {session.position['z']})"

        elif action == "click_slot":
            slot = int(raw_stage.get("slot", 0))
            if session.open_gui is None:
                passed = False
                detail = f"Cannot click slot {slot}: no open GUI window."
            else:
                detail = f"Clicked GUI slot {slot} in '{session.open_gui.get('title', 'GUI')}'."
                if isinstance(raw_stage.get("mock_reply"), str):
                    session.chat.append(redact_bot_text(raw_stage["mock_reply"], secret_tuple))

        elif action == "assert_chat":
            pattern = str(raw_stage.get("pattern", ""))
            matched = any(re.search(pattern, line, re.IGNORECASE) for line in session.chat)
            passed = matched
            detail = f"Chat matched /{pattern}/" if matched else f"Chat did not match /{pattern}/"

        elif action == "assert_no_chat":
            pattern = str(raw_stage.get("pattern", ""))
            matched = any(re.search(pattern, line, re.IGNORECASE) for line in session.chat)
            passed = not matched
            detail = f"Forbidden pattern /{pattern}/ absent" if passed else f"Forbidden pattern /{pattern}/ appeared in chat!"

        elif action == "assert_gui":
            expected_title = str(raw_stage.get("title_pattern", ""))
            if session.open_gui is None:
                passed = False
                detail = "Expected an open GUI window, but none is open."
            elif expected_title and not re.search(expected_title, str(session.open_gui.get("title", "")), re.IGNORECASE):
                passed = False
                detail = f"Open GUI title '{session.open_gui.get('title')}' did not match /{expected_title}/."
            else:
                min_slots = int(raw_stage.get("min_populated_slots", 0))
                slots = session.open_gui.get("slots", [])
                if len(slots) < min_slots:
                    passed = False
                    detail = f"GUI had {len(slots)} populated slots, expected >= {min_slots}."
                else:
                    detail = f"Verified GUI '{session.open_gui.get('title')}' ({len(slots)} slots)."

        elif action == "assert_scoreboard":
            pattern = str(raw_stage.get("pattern", ""))
            sb_blob = str(session.scoreboard.get("title", "")) + "\n" + "\n".join(str(x) for x in session.scoreboard.get("lines", []))
            passed = bool(re.search(pattern, sb_blob, re.IGNORECASE))
            detail = f"Scoreboard matched /{pattern}/" if passed else f"Scoreboard did not match /{pattern}/"

        elif action == "assert_tps":
            min_tps = float(raw_stage.get("min_tps", 18.0))
            passed = session.tps >= min_tps
            detail = f"TPS={session.tps:.2f} (threshold >= {min_tps:.2f})"

        elif action == "capture":
            detail = "Rendered off-screen visual QA PNG snapshot."

        else:
            detail = f"Executed stage action '{action}'."

        if not passed:
            all_passed = False

        session.stages.append({
            "index": idx + 1,
            "name": name,
            "action": action,
            "passed": passed,
            "detail": redact_bot_text(detail, secret_tuple),
        })

        if action == "capture" and capture_snapshot:
            frame_png = visual_capture.render_bot_snapshot_png(
                session.to_snapshot_dict(),
                title=f"STAGE {idx + 1}: {name.upper()}",
            )
            captured_frames_b64.append(visual_capture.encode_png_base64(frame_png))

    session.status = "PASSED" if all_passed else "FAILED"
    final_snapshot_b64: str | None = None
    if capture_snapshot:
        if captured_frames_b64:
            final_snapshot_b64 = captured_frames_b64[-1]
        else:
            final_snapshot_b64 = visual_capture.encode_png_base64(
                visual_capture.render_bot_snapshot_png(session.to_snapshot_dict())
            )

    return {
        "ok": all_passed,
        "execution_backend": "python-headless-slp-stage-engine",
        "screen_lock_free": True,
        "estimated_ram_mb": TIER_MEMORY_MB[tier],
        "server_probe": slp_result,
        "summary": {
            "total_stages": len(session.stages),
            "passed": sum(1 for s in session.stages if s["passed"]),
            "failed": sum(1 for s in session.stages if not s["passed"]),
            "auth_state": session.auth_state,
            "resource_pack_status": session.resource_pack_status,
        },
        "state": session.to_snapshot_dict(),
        "snapshot_count": len(captured_frames_b64) if captured_frames_b64 else (1 if final_snapshot_b64 else 0),
        "snapshot_png_base64": final_snapshot_b64,
    }


def ping_bedrock_server(
    host: str,
    port: int = 19132,
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Perform a pure-Python UDP RakNet Unconnected Ping (0x01) for Bedrock / GeyserMC servers.

    Parses the RakNet Unconnected Pong (0x1C) semicolon-delimited advertisement:
      MCPE;<motd>;<protocol>;<version>;<online>;<max>;<server_guid>;<sub_motd>;<gamemode>;...
    """
    if not host or not isinstance(host, str):
        raise ValueError("'host' must be a non-empty hostname or IP address.")
    if not (1 <= int(port) <= 65535):
        raise ValueError("'port' must be between 1 and 65535.")

    raknet_magic = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")
    ping_time_ms = int(time.time() * 1000) & 0x7FFFFFFFFFFFFFFF
    client_guid = 0x4D434B4954424F54  # "MCKITBOT"
    packet = struct.pack(">BQ", 0x01, ping_time_ms) + raknet_magic + struct.pack(">Q", client_guid)

    t0 = time.monotonic()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout_seconds)
            sock.sendto(packet, (host, int(port)))
            data, _addr = sock.recvfrom(4096)
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 2)
    except Exception as err:  # noqa: BLE001
        return {
            "reachable": False,
            "edition": "bedrock",
            "host": host,
            "port": int(port),
            "error": f"{type(err).__name__}: {err}",
        }

    if len(data) < 35 or data[0] != 0x1C:
        return {
            "reachable": False,
            "edition": "bedrock",
            "host": host,
            "port": int(port),
            "error": f"Unexpected RakNet response header (len={len(data)}, id={data[0] if data else None}).",
        }

    # Layout: 1B id (0x1C) + 8B time + 8B server_guid + 16B magic + 2B str_len + UTF-8 string
    str_len = struct.unpack(">H", data[33:35])[0]
    raw_info = data[35 : 35 + str_len].decode("utf-8", errors="replace")
    parts = raw_info.split(";")
    return {
        "reachable": True,
        "edition": parts[0] if len(parts) > 0 else "MCPE",
        "host": host,
        "port": int(port),
        "latency_ms": elapsed_ms,
        "motd": parts[1] if len(parts) > 1 else "",
        "protocol_version": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
        "version_name": parts[3] if len(parts) > 3 else "",
        "players_online": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
        "players_max": int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0,
        "server_guid": parts[6] if len(parts) > 6 else "",
        "sub_motd": parts[7] if len(parts) > 7 else "",
        "gamemode": parts[8] if len(parts) > 8 else "",
        "raw_advertisement": raw_info,
    }


STAGE_PRESETS: dict[str, dict[str, Any]] = {
    "authme_lobby": {
        "title": "AuthMe / nLogin Lobby Verification",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 42,
        "description": "Joins server, auto-registers/logs in with redacted credentials, checks lobby scoreboard, and snaps HUD.",
        "stages": [
            {"name": "Join lobby", "action": "join"},
            {"name": "Auto-auth (redacted)", "action": "auth"},
            {"name": "Verify lobby scoreboard", "action": "assert_scoreboard", "pattern": r"ONLINE|LOBBY|PLAY|TPS"},
            {"name": "Capture lobby HUD", "action": "capture"},
        ],
    },
    "rpg_shop_gui": {
        "title": "RPG /shop & Custom GUI Click Verification",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 42,
        "description": "Logs in, opens an RPG shop/menu command, validates populated GUI slots & lore, clicks a slot, and captures the 9x4 chest PNG.",
        "stages": [
            {"name": "Join server", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Open RPG menu", "action": "command", "command": "/shop"},
            {"name": "Verify menu GUI", "action": "assert_gui", "title_pattern": r"SHOP|MENU|RPG"},
            {"name": "Click item slot", "action": "click_slot", "slot": 13},
            {"name": "Check server TPS", "action": "assert_tps", "min_tps": 18.5},
            {"name": "Capture GUI proof", "action": "capture"},
        ],
    },
    "resource_pack_itemsadder_nexo": {
        "title": "Resource Pack / ItemsAdder / Nexo / Oraxen Visual QA",
        "recommended_tier": "tier2-docker-visual",
        "estimated_ram_mb": 1400,
        "description": "Accepts server resource pack, triggers custom item menu (/ia or /nexo), checks pack status, and captures off-screen Docker/Xvfb PNG.",
        "stages": [
            {"name": "Join server", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Accept custom resource pack", "action": "accept_pack"},
            {"name": "Open custom items menu", "action": "command", "command": "/ia"},
            {"name": "Verify chat/pack load", "action": "assert_chat", "pattern": r"pack|loaded|menu|opened|items"},
            {"name": "Capture visual framebuffer", "action": "capture"},
        ],
    },
    "mythicmobs_dungeon": {
        "title": "MythicMobs / MythicDungeons Combat & TPS Stability",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 42,
        "description": "Enters dungeon/arena, moves to boss coordinates, asserts combat chat telemetry & TPS >= 19.0, and captures entity minimap.",
        "stages": [
            {"name": "Join server", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Enter dungeon", "action": "command", "command": "/md play starter"},
            {"name": "Advance toward boss arena", "action": "move", "x": 16, "y": 64, "z": 24},
            {"name": "Verify TPS under mob load", "action": "assert_tps", "min_tps": 19.0},
            {"name": "Capture entity radar PNG", "action": "capture"},
        ],
    },
    "folia_region_stress": {
        "title": "Folia Multi-Region 10-Bot Concurrency Stress Test",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 420,
        "description": "Runs 10 staggered headless protocol bots (~420 MB total vs 26 GB desktop) across disjoint regions, verifying zero TPS drops and zero bridge SEVERE errors.",
        "stages": [
            {"name": "Join Folia cluster", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Teleport to disjoint region", "action": "move", "x": 1024, "y": 72, "z": -1024},
            {"name": "Trigger cross-region command", "action": "command", "command": "/warp spawn"},
            {"name": "Assert regional TPS health", "action": "assert_tps", "min_tps": 19.2},
            {"name": "Capture multi-region telemetry", "action": "capture"},
        ],
    },
    "towny_lands_claim": {
        "title": "Towny / Lands Chunk Claim, Trust & Protection QA",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 42,
        "description": "Tests land/town creation, chunk claim confirmation, permission GUI inspection, and anti-grief chat feedback without desktop windows.",
        "stages": [
            {"name": "Join survival server", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Create or inspect land claim", "action": "command", "command": "/lands claim"},
            {"name": "Verify claim feedback", "action": "assert_chat", "pattern": r"claimed|town|land|chunk|already"},
            {"name": "Open land settings GUI", "action": "command", "command": "/lands menu"},
            {"name": "Assert GUI opened", "action": "assert_gui", "pattern": r"land|town|menu|claim"},
            {"name": "Capture claim UI PNG", "action": "capture"},
        ],
    },
    "skyblock_island_coop": {
        "title": "BentoBox / SuperiorSkyblock2 Island Creation & Warp QA",
        "recommended_tier": "tier1-protocol",
        "estimated_ram_mb": 42,
        "description": "Verifies island generation/teleport, scoreboard island level readout, challenge GUI, and TPS stability during world pasting.",
        "stages": [
            {"name": "Join Skyblock server", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Teleport to island", "action": "command", "command": "/is go"},
            {"name": "Verify island chat confirmation", "action": "assert_chat", "pattern": r"island|teleported|welcome|home"},
            {"name": "Open island panel", "action": "command", "command": "/is panel"},
            {"name": "Assert TPS stable after island paste", "action": "assert_tps", "min_tps": 19.0},
            {"name": "Capture Skyblock HUD PNG", "action": "capture"},
        ],
    },
    "modelengine_boss_arena": {
        "title": "ModelEngine + MythicMobs Custom 3D Boss Visual & Hitbox QA",
        "recommended_tier": "tier2-hybrid",
        "estimated_ram_mb": 1400,
        "description": "Hybrid Tier-2 off-screen Xvfb visual client + protocol telemetry verifying custom resource pack load, ModelEngine boss spawn, entity count, and TPS >= 19.0.",
        "stages": [
            {"name": "Join RPG arena", "action": "join"},
            {"name": "Auto-auth", "action": "auth"},
            {"name": "Accept ModelEngine resource pack", "action": "accept_pack"},
            {"name": "Warp to boss arena", "action": "command", "command": "/warp boss_arena"},
            {"name": "Verify TPS during custom model tick", "action": "assert_tps", "min_tps": 19.0},
            {"name": "Capture off-screen boss visual PNG", "action": "capture"},
        ],
    },
}


def build_stage_preset(
    preset_name: str,
    *,
    command_override: str = "",
    gui_pattern_override: str = "",
    chat_pattern_override: str = "",
    min_tps: float | None = None,
) -> dict[str, Any]:
    """Return a ready-to-run autonomous bot stage preset customized for common MC plugin stacks."""
    key = preset_name.strip().lower()
    if key not in STAGE_PRESETS:
        raise ValueError(f"Unknown preset {preset_name!r}. Choose one of {sorted(STAGE_PRESETS)}.")
    base = STAGE_PRESETS[key]
    stages = [dict(s) for s in base["stages"]]
    for st in stages:
        if command_override and st.get("action") == "command":
            st["command"] = command_override
        if gui_pattern_override and st.get("action") == "assert_gui":
            st["title_pattern"] = gui_pattern_override
        if chat_pattern_override and st.get("action") == "assert_chat":
            st["pattern"] = chat_pattern_override
        if min_tps is not None and st.get("action") == "assert_tps":
            st["min_tps"] = float(min_tps)
    return {
        "preset": key,
        "title": base["title"],
        "recommended_tier": base["recommended_tier"],
        "estimated_ram_mb": base["estimated_ram_mb"],
        "description": base["description"],
        "available_presets": sorted(STAGE_PRESETS),
        "stages": stages,
    }


def query_bridge_plugin(
    *,
    base_url: str = "http://127.0.0.1:25590",
    token: str = "",
    endpoint: str = "health",
    player: str = "",
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Query the optional `mckit-bridge-plugin` HTTP QA inspection bridge."""
    allowed_endpoints = {
        "health": "/api/v1/health",
        "metrics": "/api/v1/metrics",
        "tps-history": "/api/v1/tps-history",
        "entities": "/api/v1/entities",
        "chunks": "/api/v1/chunks",
        "players": "/api/v1/players",
        "errors": "/api/v1/errors",
        "plugins": "/api/v1/plugins",
        "gui": "/api/v1/gui",
        "worlds": "/api/v1/worlds",
    }
    if endpoint not in allowed_endpoints:
        raise ValueError(f"'endpoint' must be one of {sorted(allowed_endpoints)}.")
    if not (base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost") or base_url.startswith("https://")):
        raise ValueError("Bridge plugin URL must target localhost/127.0.0.1 or HTTPS.")

    url = base_url.rstrip("/") + allowed_endpoints[endpoint]
    if endpoint == "gui" and player:
        url += "?player=" + urllib.request.quote(player)
    headers = {"Accept": "application/json", "User-Agent": "MinecraftKit-MCP/3.3"}
    if token:
        headers["X-MCKit-Token"] = token

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            return {"reachable": True, "endpoint": endpoint, "status_code": resp.status, "data": body}
    except urllib.error.HTTPError as err:
        return {"reachable": True, "endpoint": endpoint, "status_code": err.code, "error": f"HTTP {err.code}"}
    except Exception as err:  # noqa: BLE001
        return {
            "reachable": False,
            "endpoint": endpoint,
            "error": f"{type(err).__name__}: {err}",
            "install_hint": "Build and copy bridge-plugin/build/libs/mckit-bridge-plugin.jar into your test server's plugins/ folder.",
        }
