"""Interactive Multi-Turn Freeform Headless Bot Session Hub.

Allows AI agents to spawn a persistent headless test bot session, send freeform
commands/movement/GUI clicks across multiple MCP tool turns, capture visual PNG
snapshots and multi-frame timelapses, and cleanly reap idle sessions under strict
RAM/concurrency caps.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import bot_engine
import visual_capture


class BotSessionHub:
    """In-memory governed registry of interactive headless test bot sessions."""

    def __init__(self, max_sessions: int = 16, idle_timeout_seconds: float = 300.0) -> None:
        self.max_sessions = max(1, max_sessions)
        self.idle_timeout_seconds = max(30.0, idle_timeout_seconds)
        self._sessions: dict[str, dict[str, Any]] = {}

    def reap_idle(self) -> list[str]:
        now = time.monotonic()
        reaped: list[str] = []
        for sid, entry in list(self._sessions.items()):
            if now - entry["last_active"] > self.idle_timeout_seconds:
                self._sessions.pop(sid, None)
                reaped.append(sid)
        return reaped

    def start_session(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 25565,
        username: str = "MCKitFreeBot",
        version: str = "1.21.4",
        password: str = "",
        tier: str = "tier1-protocol",
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.reap_idle()
        if len(self._sessions) >= self.max_sessions:
            raise RuntimeError(
                f"Bot session governor cap reached ({self.max_sessions} active sessions). Stop an idle session first."
            )
        if tier not in bot_engine.TIER_MEMORY_MB:
            raise ValueError(f"Unsupported tier: {tier}")

        sid = f"sess-{username.lower()}-{len(self._sessions) + 1}-{int(time.time()) % 10000}"
        state = bot_engine.BotSessionState(
            session_id=sid,
            username=username,
            server_host=host,
            server_port=int(port),
            version=version,
            tier=tier,
            status="CONNECTED",
            ram_mb=float(bot_engine.TIER_MEMORY_MB[tier]),
        )
        secret_tuple = (password,) if password else ()
        if isinstance(initial_state, dict):
            if isinstance(initial_state.get("chat"), list):
                state.chat.extend(bot_engine.redact_bot_text(str(x), secret_tuple) for x in initial_state["chat"])
            if isinstance(initial_state.get("open_gui"), dict):
                state.open_gui = dict(initial_state["open_gui"])
            if isinstance(initial_state.get("scoreboard"), dict):
                state.scoreboard = dict(initial_state["scoreboard"])
            if isinstance(initial_state.get("entities"), list):
                state.entities = list(initial_state["entities"])
            if isinstance(initial_state.get("tps"), (int, float)):
                state.tps = float(initial_state["tps"])

        if not state.chat:
            state.chat.append(f"[Server] {username} joined {host}:{port}")

        # Auto-auth immediately if prompt already present in initial chat and password given
        detected = bot_engine.detect_auth_prompt(state.chat, state.title)
        if detected in ("register", "login") and password:
            state.auth_state = "AUTHENTICATED"
            cmd_tag = "/register [REDACTED_PASSWORD] [REDACTED_PASSWORD]" if detected == "register" else "/login [REDACTED_PASSWORD]"
            state.chat.append(f"[Bot -> Server] {cmd_tag}")
            state.chat.append("[Auth] Auto-authenticated cleanly.")
        elif detected is None:
            state.auth_state = "AUTHENTICATED"

        png_bytes = visual_capture.render_bot_snapshot_png(
            state.to_snapshot_dict(),
            title=f"FREEFORM SESSION: {sid.upper()}",
        )
        self._sessions[sid] = {
            "state": state,
            "password": password,
            "last_active": time.monotonic(),
            "frames": [png_bytes],
        }
        return {
            "session_id": sid,
            "active_sessions": len(self._sessions),
            "estimated_total_ram_mb": self.total_ram_mb(),
            "screen_lock_free": True,
            "state": state.to_snapshot_dict(),
            "snapshot_png_base64": visual_capture.encode_png_base64(png_bytes),
        }

    def execute_action(
        self,
        *,
        session_id: str,
        action: str,
        message: str = "",
        slot: int | None = None,
        position: dict[str, float] | None = None,
        mock_reply: str = "",
        mock_gui: dict[str, Any] | None = None,
        capture_snapshot: bool = True,
    ) -> dict[str, Any]:
        self.reap_idle()
        entry = self._sessions.get(session_id)
        if entry is None:
            raise ValueError(f"Unknown or reaped session_id: {session_id!r}")
        entry["last_active"] = time.monotonic()
        state: bot_engine.BotSessionState = entry["state"]
        secret_tuple = (entry["password"],) if entry["password"] else ()

        act = action.strip().lower()
        detail = ""
        if act in ("command", "chat"):
            if not message.strip():
                raise ValueError("'message' is required for command/chat actions.")
            safe_msg = bot_engine.redact_bot_text(message.strip(), secret_tuple)
            state.chat.append(f"[Bot] {safe_msg}")
            detail = f"Executed {safe_msg}"
        elif act == "move":
            if isinstance(position, dict):
                for axis in ("x", "y", "z", "yaw", "pitch"):
                    if axis in position:
                        state.position[axis] = float(position[axis])
            detail = f"Moved to ({state.position['x']}, {state.position['y']}, {state.position['z']})"
        elif act == "click_slot":
            if state.open_gui is None:
                raise ValueError("Cannot click_slot: no GUI window is currently open.")
            idx = int(slot or 0)
            detail = f"Clicked GUI slot {idx} in '{state.open_gui.get('title', 'GUI')}'"
            state.chat.append(f"[Bot GUI] Clicked slot #{idx}")
        elif act == "close_gui":
            state.open_gui = None
            detail = "Closed active GUI window."
        elif act == "snapshot":
            detail = "Captured current off-screen visual HUD snapshot."
        else:
            raise ValueError(f"Unsupported freeform action: {action!r}")

        if mock_reply:
            state.chat.append(bot_engine.redact_bot_text(mock_reply, secret_tuple))
        if isinstance(mock_gui, dict):
            state.open_gui = dict(mock_gui)

        state.stages.append({
            "index": len(state.stages) + 1,
            "name": detail,
            "action": act,
            "passed": True,
            "detail": detail,
        })

        b64_png: str | None = None
        if capture_snapshot:
            png_bytes = visual_capture.render_bot_snapshot_png(
                state.to_snapshot_dict(),
                title=f"FREEFORM {session_id.upper()}: {act.upper()}",
            )
            entry["frames"].append(png_bytes)
            if len(entry["frames"]) > 24:
                entry["frames"] = entry["frames"][-24:]
            b64_png = visual_capture.encode_png_base64(png_bytes)

        return {
            "session_id": session_id,
            "action": act,
            "detail": detail,
            "frame_count": len(entry["frames"]),
            "state": state.to_snapshot_dict(),
            "snapshot_png_base64": b64_png,
        }

    def export_timelapse(self, session_id: str, output_dir: Path, *, fps: int = 2) -> dict[str, Any]:
        entry = self._sessions.get(session_id)
        if entry is None:
            raise ValueError(f"Unknown session_id: {session_id!r}")
        frames: list[bytes] = entry["frames"]
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        for idx, raw in enumerate(frames):
            p = output_dir / f"{session_id}-frame-{idx:03d}.png"
            p.write_bytes(raw)
            frame_paths.append(p)
        mp4_path = output_dir / f"{session_id}-timelapse.mp4"
        video_res = visual_capture.assemble_timelapse_video(frame_paths, mp4_path, fps=fps)
        return {
            "session_id": session_id,
            "frame_count": len(frame_paths),
            "frames_dir": str(output_dir),
            "video": video_res,
            "latest_png_base64": visual_capture.encode_png_base64(frames[-1]) if frames else None,
        }

    def stop_session(self, session_id: str) -> dict[str, Any]:
        removed = self._sessions.pop(session_id, None)
        return {
            "stopped": removed is not None,
            "session_id": session_id,
            "active_sessions": len(self._sessions),
            "estimated_total_ram_mb": self.total_ram_mb(),
        }

    def pool_status(self) -> dict[str, Any]:
        reaped = self.reap_idle()
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self.max_sessions,
            "estimated_total_ram_mb": self.total_ram_mb(),
            "reaped_idle_sessions": reaped,
            "sessions": [
                {
                    "session_id": sid,
                    "username": e["state"].username,
                    "server": f"{e['state'].server_host}:{e['state'].server_port}",
                    "tier": e["state"].tier,
                    "auth_state": e["state"].auth_state,
                    "frame_count": len(e["frames"]),
                }
                for sid, e in sorted(self._sessions.items())
            ],
        }

    def total_ram_mb(self) -> float:
        return round(sum(e["state"].ram_mb for e in self._sessions.values()), 1)
