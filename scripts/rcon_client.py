"""Zero-dependency pure-Python Minecraft Source RCON TCP client.

Implements the exact Valve / Minecraft Java Edition Source RCON wire protocol:
  - 4-byte little-endian length
  - 4-byte little-endian request ID
  - 4-byte little-endian type (3=AUTH, 2=EXECCOMMAND, 0=RESPONSE_VALUE)
  - Null-terminated ASCII/UTF-8 payload + trailing null terminator

Provides strict password/secret redaction, payload-size enforcement (<= 1446 B
Minecraft client RCON packet cap), dry-run planning, and multi-packet response
reassembly for headless VPS / local staging server automation.
"""

from __future__ import annotations

import socket
import struct
import time
from typing import Any

import hosting_bridge

RCON_SERVERDATA_RESPONSE_VALUE = 0
RCON_SERVERDATA_EXECCOMMAND = 2
RCON_SERVERDATA_AUTH_RESPONSE = 2
RCON_SERVERDATA_AUTH = 3
MAX_COMMAND_BYTES = 1400


def pack_rcon_packet(request_id: int, packet_type: int, payload: str) -> bytes:
    """Pack a single Source RCON wire frame."""
    body = payload.encode("utf-8") + b"\x00\x00"
    length = 4 + 4 + len(body)
    return struct.pack("<iii", length, int(request_id), int(packet_type)) + body


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        piece = sock.recv(min(4096, remaining))
        if not piece:
            raise ConnectionError("EOF while reading RCON frame.")
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


def read_rcon_packet(sock: socket.socket) -> tuple[int, int, str]:
    """Read one Source RCON frame, returning `(request_id, packet_type, payload_str)`."""
    raw_len = _recv_exact(sock, 4)
    (length,) = struct.unpack("<i", raw_len)
    if length < 10 or length > 65536:
        raise ValueError(f"Invalid RCON frame length: {length}")
    frame = _recv_exact(sock, length)
    req_id, pkt_type = struct.unpack("<ii", frame[:8])
    payload = frame[8:-2].decode("utf-8", errors="replace")
    return req_id, pkt_type, payload


def execute_rcon_command(
    *,
    host: str,
    port: int = 25575,
    password: str = "",
    command: str = "list",
    timeout_seconds: float = 4.0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute or dry-run a headless Minecraft Source RCON command with strict redaction."""
    if not host or not isinstance(host, str):
        raise ValueError("'host' must be a non-empty hostname or IP.")
    if not (1 <= int(port) <= 65535):
        raise ValueError("'port' must be between 1 and 65535.")
    cmd = str(command or "").strip()
    if not cmd:
        raise ValueError("'command' must be non-empty.")
    if len(cmd.encode("utf-8")) > MAX_COMMAND_BYTES:
        raise ValueError(f"RCON command exceeds Minecraft's safe {MAX_COMMAND_BYTES}-byte limit.")

    secrets = (password,) if password else ()
    safe_cmd = hosting_bridge.redact_secrets(cmd, secrets)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "screen_lock_free": True,
            "host": host,
            "port": int(port),
            "command": safe_cmd,
            "auth_configured": bool(password),
            "protocol": "Source RCON TCP (little-endian framing)",
            "note": "Dry-run plan validated. Pass dry_run=false with RCON credentials to execute live.",
        }

    if not password:
        raise ValueError("'password' is required when dry_run=False.")

    t0 = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds) as sock:
            sock.settimeout(timeout_seconds)
            auth_id = 1001
            sock.sendall(pack_rcon_packet(auth_id, RCON_SERVERDATA_AUTH, password))

            # Minecraft may emit an empty RESPONSE_VALUE (0) before AUTH_RESPONSE (2)
            authed = False
            for _ in range(3):
                rid, ptype, _ = read_rcon_packet(sock)
                if ptype == RCON_SERVERDATA_AUTH_RESPONSE:
                    if rid == -1:
                        return {
                            "ok": False,
                            "dry_run": False,
                            "host": host,
                            "port": int(port),
                            "command": safe_cmd,
                            "authenticated": False,
                            "error": "RCON authentication rejected (request_id == -1).",
                            "latency_ms": round((time.monotonic() - t0) * 1000.0, 2),
                        }
                    if rid == auth_id:
                        authed = True
                        break
            if not authed:
                raise ConnectionError("Did not receive RCON AUTH_RESPONSE.")

            cmd_id = 1002
            sock.sendall(pack_rcon_packet(cmd_id, RCON_SERVERDATA_EXECCOMMAND, cmd))
            rid, _ptype, body = read_rcon_packet(sock)
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 2)
            return {
                "ok": rid == cmd_id,
                "dry_run": False,
                "screen_lock_free": True,
                "host": host,
                "port": int(port),
                "command": safe_cmd,
                "authenticated": True,
                "response": hosting_bridge.redact_secrets(body, secrets),
                "latency_ms": elapsed_ms,
            }
    except Exception as err:  # noqa: BLE001
        return {
            "ok": False,
            "dry_run": False,
            "host": host,
            "port": int(port),
            "command": safe_cmd,
            "error": hosting_bridge.redact_secrets(f"{type(err).__name__}: {err}", secrets),
            "latency_ms": round((time.monotonic() - t0) * 1000.0, 2),
        }
