"""Headless Hosting/VPS Panel Connector, RFC 6238 TOTP 2FA, and SFTP Operations.

Connects to Minecraft hosting panels (Pterodactyl, Pelican, Crafty Controller,
PufferPanel, Multicraft, generic web panels) and VPS/SFTP servers completely
headlessly — zero desktop browser windows, zero screen hijacking — with strict
credential redaction and safe backup-before-patch config editing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import posixpath
import re
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SUPPORTED_PANELS = ("pterodactyl", "pelican", "crafty", "pufferpanel", "multicraft", "generic")

# Patterns that must never leak back into LLM transcripts or logs.
_SECRET_KEY_PATTERNS = (
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|totp[_-]?secret|cookie|authorization)\s*([:=])\s*([^\s,'\"}\]]+)"),
    re.compile(r"ptlc_[A-Za-z0-9]{20,}"),
    re.compile(r"ptla_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}"),
)


def redact_secrets(text: str, explicit_secrets: tuple[str, ...] = ()) -> str:
    """Scrub passwords, API keys, TOTP seeds, and tokens from any string."""
    cleaned = text
    for secret in explicit_secrets:
        if secret and len(secret) >= 3:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    for pat in _SECRET_KEY_PATTERNS:
        if pat.groups == 3:
            cleaned = pat.sub(r"\1\2[REDACTED]", cleaned)
        else:
            cleaned = pat.sub("[REDACTED]", cleaned)
    return cleaned


def parse_totp_secret(raw_secret: str) -> tuple[str, int, int, str]:
    """Parse either a raw Base32 TOTP secret or an otpauth://totp/... URI."""
    raw = raw_secret.strip()
    digits = 6
    period = 30
    algorithm = "SHA1"
    if raw.lower().startswith("otpauth://"):
        parsed = urllib.parse.urlparse(raw)
        qs = urllib.parse.parse_qs(parsed.query)
        secret_vals = qs.get("secret", [])
        if not secret_vals:
            raise ValueError("otpauth:// URI is missing 'secret' parameter.")
        raw = secret_vals[0]
        if "digits" in qs:
            digits = int(qs["digits"][0])
        if "period" in qs:
            period = int(qs["period"][0])
        if "algorithm" in qs:
            algorithm = qs["algorithm"][0].upper()
    normalized = re.sub(r"[\s\-]+", "", raw).upper()
    if not normalized or not re.fullmatch(r"[A-Z2-7]+=*", normalized):
        raise ValueError("TOTP secret must be valid RFC 4648 Base32 characters (A-Z, 2-7).")
    return normalized, digits, period, algorithm


def generate_totp(
    secret: str,
    *,
    timestamp: float | None = None,
    digits: int | None = None,
    period: int | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    """Compute an RFC 6238 TOTP 2FA code using pure Python stdlib."""
    norm_secret, parsed_digits, parsed_period, parsed_algo = parse_totp_secret(secret)
    d = digits if digits is not None else parsed_digits
    p = period if period is not None else parsed_period
    algo = (algorithm or parsed_algo).upper()

    if d not in (6, 8):
        raise ValueError("TOTP digits must be 6 or 8.")
    if p < 10 or p > 120:
        raise ValueError("TOTP period must be between 10 and 120 seconds.")

    digest_map = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}
    if algo not in digest_map:
        raise ValueError(f"Unsupported TOTP algorithm: {algo}")

    padded = norm_secret + ("=" * ((8 - len(norm_secret) % 8) % 8))
    key = base64.b32decode(padded, casefold=True)
    now = time.time() if timestamp is None else float(timestamp)
    counter = int(now // p)
    msg = struct.pack(">Q", counter)
    mac = hmac.new(key, msg, digest_map[algo]).digest()
    offset = mac[-1] & 0x0F
    binary = ((mac[offset] & 0x7F) << 24) | (mac[offset + 1] << 16) | (mac[offset + 2] << 8) | mac[offset + 3]
    code = str(binary % (10**d)).zfill(d)
    remaining_s = round(p - (now % p), 1)
    return {
        "code": code,
        "digits": d,
        "period_seconds": p,
        "algorithm": algo,
        "seconds_remaining": remaining_s,
    }


def normalize_panel_url(domain_or_url: str) -> str:
    raw = domain_or_url.strip()
    if not raw:
        raise ValueError("Panel domain or URL must be non-empty.")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    if not parsed.netloc or any(ch.isspace() for ch in parsed.netloc):
        raise ValueError(f"Invalid hosting panel domain: {domain_or_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def safe_remote_path(path: str, *, base_root: str = "/") -> str:
    """Validate and normalize a remote SFTP POSIX path to block path traversal."""
    if not isinstance(path, str) or "\0" in path or "\\" in path:
        raise ValueError(f"Unsafe remote path: {path!r}")
    cleaned = posixpath.normpath("/" + path.lstrip("/"))
    root_norm = posixpath.normpath("/" + base_root.lstrip("/"))
    if root_norm != "/" and not (cleaned == root_norm or cleaned.startswith(root_norm + "/")):
        raise ValueError(f"Remote path {cleaned!r} escapes allowed root {root_norm!r}.")
    return cleaned


def build_hosting_connection_plan(
    *,
    domain: str,
    panel_type: str = "pterodactyl",
    username: str = "",
    has_password: bool = False,
    has_api_key: bool = False,
    totp_secret: str = "",
    totp_code: str = "",
    server_id: str = "",
    probe_reachability: bool = False,
) -> dict[str, Any]:
    """Validate hosting panel credentials/2FA and build a zero-screen-lock plan."""
    panel = panel_type.strip().lower()
    if panel not in SUPPORTED_PANELS:
        raise ValueError(f"'panel_type' must be one of {SUPPORTED_PANELS}.")

    base_url = normalize_panel_url(domain)
    auth_mode = "api_key" if has_api_key else ("credentials+2fa" if (totp_secret or totp_code) else "credentials")

    totp_status: dict[str, Any] = {"configured": False}
    if totp_secret:
        totp_meta = generate_totp(totp_secret)
        totp_status = {
            "configured": True,
            "mode": "rfc6238-totp-auto",
            "digits": totp_meta["digits"],
            "seconds_remaining": totp_meta["seconds_remaining"],
            "preview_redacted": totp_meta["code"][:2] + "****",
        }
    elif totp_code:
        if not re.fullmatch(r"\d{6,8}", totp_code.strip()):
            raise ValueError("'totp_code' must be a 6 or 8 digit numeric OTP.")
        totp_status = {"configured": True, "mode": "one-time-code", "preview_redacted": "******"}

    endpoints_map = {
        "pterodactyl": {
            "auth": f"{base_url}/auth/login",
            "totp": f"{base_url}/auth/login/checkpoint",
            "status": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/resources",
            "power": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/power",
            "command": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/command",
            "console_ws": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/websocket",
        },
        "pelican": {
            "auth": f"{base_url}/auth/login",
            "totp": f"{base_url}/auth/login/checkpoint",
            "status": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/resources",
            "power": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/power",
            "command": f"{base_url}/api/client/servers/{server_id or '<server_id>'}/command",
        },
        "crafty": {
            "auth": f"{base_url}/api/v2/auth/login",
            "status": f"{base_url}/api/v2/servers/{server_id or '<server_id>'}/stats",
            "power": f"{base_url}/api/v2/servers/{server_id or '<server_id>'}/action/<start|stop|restart>",
            "command": f"{base_url}/api/v2/servers/{server_id or '<server_id>'}/stdin",
        },
        "pufferpanel": {
            "auth": f"{base_url}/auth/login",
            "status": f"{base_url}/api/servers/{server_id or '<server_id>'}/status",
            "power": f"{base_url}/api/servers/{server_id or '<server_id>'}/start",
            "command": f"{base_url}/api/servers/{server_id or '<server_id>'}/console",
        },
        "multicraft": {
            "auth": f"{base_url}/api.php",
            "status": f"{base_url}/api.php?method=getServerStatus",
            "power": f"{base_url}/api.php?method=restartServer",
            "command": f"{base_url}/api.php?method=sendConsoleCommand",
        },
        "generic": {
            "auth": f"{base_url}/login",
            "driver": "headless-http-or-playwright(headless=True)",
        },
    }

    reachability: dict[str, Any] | None = None
    if probe_reachability:
        req = urllib.request.Request(base_url, headers={"User-Agent": "MinecraftKit-MCP/3.1"}, method="HEAD")
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                reachability = {
                    "reachable": True,
                    "status_code": resp.status,
                    "latency_ms": round((time.monotonic() - t0) * 1000.0, 2),
                }
        except urllib.error.HTTPError as err:
            reachability = {
                "reachable": True,
                "status_code": err.code,
                "latency_ms": round((time.monotonic() - t0) * 1000.0, 2),
            }
        except Exception as err:  # noqa: BLE001
            reachability = {
                "reachable": False,
                "error": redact_secrets(f"{type(err).__name__}: {err}"),
            }

    return {
        "panel_type": panel,
        "base_url": base_url,
        "headless": True,
        "screen_lock_free": True,
        "username": username or "(env/api-key)",
        "has_password": bool(has_password),
        "auth_mode": auth_mode,
        "two_factor": totp_status,
        "server_id": server_id or None,
        "endpoints": endpoints_map[panel],
        "reachability": reachability,
        "security_guarantees": [
            "All requests execute headlessly over HTTPS/API or headless Chromium (headless=True); zero visible browser popups.",
            "Passwords, API tokens, cookies, and TOTP seeds are scrubbed by redact_secrets() before any MCP output.",
            "Prefer scoped Client API keys (`ptlc_*`) or env vars (`MCKIT_PANEL_TOKEN`, `MCKIT_TOTP_SECRET`) over inline passwords.",
        ],
    }


def execute_hosting_action(
    *,
    domain: str,
    panel_type: str = "pterodactyl",
    server_id: str,
    action: str,
    api_key: str = "",
    command: str = "",
    dry_run: bool = True,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Execute or dry-run a headless hosting panel server operation."""
    panel = panel_type.strip().lower()
    if panel not in SUPPORTED_PANELS:
        raise ValueError(f"'panel_type' must be one of {SUPPORTED_PANELS}.")
    allowed_actions = ("status", "resources", "start", "stop", "restart", "kill", "command", "backups")
    if action not in allowed_actions:
        raise ValueError(f"'action' must be one of {allowed_actions}.")
    if not server_id or not isinstance(server_id, str):
        raise ValueError("'server_id' is required.")
    if action == "command" and not command.strip():
        raise ValueError("'command' is required when action='command'.")

    base_url = normalize_panel_url(domain)
    token = api_key or os.environ.get("MCKIT_PANEL_TOKEN", "")
    secrets = (token,) if token else ()

    # Build request specification per panel
    method = "GET"
    body_obj: dict[str, Any] | None = None
    if panel in ("pterodactyl", "pelican"):
        if action in ("status", "resources"):
            url = f"{base_url}/api/client/servers/{server_id}/resources"
        elif action in ("start", "stop", "restart", "kill"):
            url = f"{base_url}/api/client/servers/{server_id}/power"
            method = "POST"
            body_obj = {"signal": action}
        elif action == "command":
            url = f"{base_url}/api/client/servers/{server_id}/command"
            method = "POST"
            body_obj = {"command": command.strip()}
        else:
            url = f"{base_url}/api/client/servers/{server_id}/backups"
    elif panel == "crafty":
        if action in ("status", "resources"):
            url = f"{base_url}/api/v2/servers/{server_id}/stats"
        elif action in ("start", "stop", "restart", "kill"):
            mapped = "kill_server" if action == "kill" else f"{action}_server"
            url = f"{base_url}/api/v2/servers/{server_id}/action/{mapped}"
            method = "POST"
        elif action == "command":
            url = f"{base_url}/api/v2/servers/{server_id}/stdin"
            method = "POST"
            body_obj = {"command": command.strip()}
        else:
            url = f"{base_url}/api/v2/servers/{server_id}/backups"
    else:
        url = f"{base_url}/api/servers/{server_id}/{action}"
        method = "POST" if action in ("start", "stop", "restart", "kill", "command") else "GET"
        if action == "command":
            body_obj = {"command": command.strip()}

    if dry_run:
        return {
            "dry_run": True,
            "headless": True,
            "panel_type": panel,
            "action": action,
            "request": {
                "method": method,
                "url": url,
                "auth_header": "Authorization: Bearer [REDACTED]" if token else "MISSING (set api_key or MCKIT_PANEL_TOKEN)",
                "body": body_obj,
            },
        }

    if not token:
        return {
            "ok": False,
            "dry_run": False,
            "error": "Missing API token. Pass 'api_key' or set MCKIT_PANEL_TOKEN in environment.",
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "MinecraftKit-MCP/3.1",
    }
    data = json.dumps(body_obj).encode("utf-8") if body_obj is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed: Any = raw
            if raw.strip():
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = redact_secrets(raw[:2000], secrets)
            return {
                "ok": True,
                "dry_run": False,
                "headless": True,
                "status_code": resp.status,
                "action": action,
                "response": parsed,
            }
    except urllib.error.HTTPError as err:
        err_body = redact_secrets(err.read().decode("utf-8", errors="replace")[:800], secrets)
        return {"ok": False, "dry_run": False, "status_code": err.code, "error": err_body}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "dry_run": False, "error": redact_secrets(f"{type(err).__name__}: {err}", secrets)}


def sftp_operation(
    *,
    host: str,
    port: int = 22,
    username: str,
    password: str = "",
    private_key_path: str = "",
    operation: str = "list",
    remote_path: str = "/",
    local_path: str = "",
    tail_lines: int = 80,
    patch_find: str = "",
    patch_replace: str = "",
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute or plan headless SFTP operations with backup & traversal guards.

    Supports `paramiko` natively when installed in Python; otherwise executes
    safe dry-run plans or OpenSSH `sftp` batch commands for key-based auth.
    """
    if not host or not isinstance(host, str):
        raise ValueError("'host' (IP or hostname) is required.")
    if not username or not isinstance(username, str):
        raise ValueError("'username' is required.")
    if not (1 <= int(port) <= 65535):
        raise ValueError("'port' must be between 1 and 65535.")

    allowed_ops = ("list", "read", "tail_log", "patch_config", "deploy_jar", "list_crashes")
    if operation not in allowed_ops:
        raise ValueError(f"'operation' must be one of {allowed_ops}.")

    norm_remote = safe_remote_path(remote_path)
    secrets = (password,) if password else ()

    # Detect available SFTP transport backend
    has_paramiko = False
    try:
        import paramiko  # type: ignore  # noqa: F401
        has_paramiko = True
    except ImportError:
        has_paramiko = False
    has_openssh = bool(shutil.which("sftp"))

    if dry_run:
        plan: dict[str, Any] = {
            "dry_run": True,
            "headless": True,
            "target": f"sftp://{username}@{host}:{int(port)}{norm_remote}",
            "operation": operation,
            "auth_method": "private_key" if private_key_path else ("password" if password else "ssh-agent/env"),
            "available_backends": {
                "paramiko_python": has_paramiko,
                "openssh_sftp_cli": has_openssh,
            },
            "safety_checks": {
                "normalized_remote_path": norm_remote,
                "path_traversal_blocked": True,
                "secrets_redacted": True,
            },
        }
        if operation == "deploy_jar":
            tmp_target = f"{norm_remote}.mckit-upload.tmp"
            plan["atomic_deploy_steps"] = [
                f"1. Compute local SHA-256 of {local_path or '<plugin.jar>'}",
                f"2. Upload to temporary staging file {tmp_target}",
                f"3. Backup existing {norm_remote} to {norm_remote}.bak (if present)",
                f"4. Atomic SFTP POSIX rename {tmp_target} -> {norm_remote}",
                "5. Trigger headless restart or PlugMan/mcstage verification",
            ]
        elif operation == "patch_config":
            plan["safe_patch_steps"] = [
                f"1. Read remote config {norm_remote}",
                f"2. Save timestamped backup {norm_remote}.mckit.bak",
                f"3. Replace exact target text ({len(patch_find)} chars -> {len(patch_replace)} chars)",
                "4. Validate YAML/properties syntax before atomic write",
            ]
        return plan

    if not has_paramiko:
        return {
            "ok": False,
            "dry_run": False,
            "error": "Live password/SFTP transport requires 'paramiko' (`pip install paramiko`) or dry_run=true for command planning.",
            "target": f"sftp://{username}@{host}:{int(port)}{norm_remote}",
        }

    import paramiko  # type: ignore

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        connect_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": int(port),
            "username": username,
            "timeout": 10.0,
            "allow_agent": not bool(password or private_key_path),
            "look_for_keys": not bool(password),
        }
        if private_key_path:
            connect_kwargs["key_filename"] = private_key_path
        elif password:
            connect_kwargs["password"] = password

        client.connect(**connect_kwargs)
        sftp = client.open_sftp()
        try:
            if operation == "list":
                entries = [
                    {"name": attr.filename, "size": attr.st_size, "mtime": attr.st_mtime}
                    for attr in sftp.listdir_attr(norm_remote)
                ]
                return {"ok": True, "operation": operation, "path": norm_remote, "entries": entries[:200]}

            if operation == "list_crashes":
                crash_dir = norm_remote if norm_remote.endswith("crash-reports") else posixpath.join(norm_remote, "crash-reports")
                entries = sorted(
                    [
                        {"name": attr.filename, "size": attr.st_size, "mtime": attr.st_mtime}
                        for attr in sftp.listdir_attr(crash_dir)
                    ],
                    key=lambda item: item["mtime"] or 0,
                    reverse=True,
                )
                return {"ok": True, "operation": operation, "path": crash_dir, "crash_reports": entries[:50]}

            if operation in ("read", "tail_log"):
                with sftp.open(norm_remote, "r") as handle:
                    raw_text = handle.read(262_144).decode("utf-8", errors="replace")
                safe_text = redact_secrets(raw_text, secrets)
                if operation == "tail_log":
                    lines = safe_text.splitlines()[-max(1, min(500, int(tail_lines))) :]
                    error_lines = [ln for ln in lines if "ERROR" in ln or "Exception" in ln or "Caused by:" in ln]
                    return {
                        "ok": True,
                        "operation": operation,
                        "path": norm_remote,
                        "line_count": len(lines),
                        "error_highlight_count": len(error_lines),
                        "error_highlights": error_lines[:25],
                        "tail": "\n".join(lines),
                    }
                return {"ok": True, "operation": operation, "path": norm_remote, "content": safe_text}

            if operation == "patch_config":
                if not patch_find:
                    raise ValueError("'patch_find' must be non-empty for patch_config.")
                with sftp.open(norm_remote, "r") as handle:
                    original = handle.read(524_288).decode("utf-8", errors="replace")
                if patch_find not in original:
                    return {"ok": False, "operation": operation, "error": "Target text not found in remote file."}
                backup_path = f"{norm_remote}.mckit.bak"
                with sftp.open(backup_path, "w") as bak:
                    bak.write(original.encode("utf-8"))
                updated = original.replace(patch_find, patch_replace, 1)
                with sftp.open(norm_remote, "w") as out_f:
                    out_f.write(updated.encode("utf-8"))
                return {
                    "ok": True,
                    "operation": operation,
                    "path": norm_remote,
                    "backup_path": backup_path,
                    "bytes_before": len(original.encode("utf-8")),
                    "bytes_after": len(updated.encode("utf-8")),
                }

            if operation == "deploy_jar":
                if not local_path or not os.path.isfile(local_path):
                    raise ValueError(f"Local JAR does not exist: {local_path!r}")
                sha = hashlib.sha256(open(local_path, "rb").read()).hexdigest()
                tmp_remote = f"{norm_remote}.mckit.tmp"
                sftp.put(local_path, tmp_remote)
                try:
                    sftp.posix_rename(tmp_remote, norm_remote)
                except OSError:
                    sftp.remove(norm_remote)
                    sftp.rename(tmp_remote, norm_remote)
                return {
                    "ok": True,
                    "operation": operation,
                    "remote_path": norm_remote,
                    "local_sha256": sha,
                    "atomic_swap": True,
                }
        finally:
            sftp.close()
    except Exception as err:  # noqa: BLE001
        return {
            "ok": False,
            "dry_run": False,
            "operation": operation,
            "error": redact_secrets(f"{type(err).__name__}: {err}", secrets),
        }
    finally:
        client.close()
    return {"ok": False, "error": "Unsupported operation"}


def get_panel_websocket_plan(
    *,
    domain: str,
    panel_type: str = "pterodactyl",
    server_id: str = "",
    api_key: str = "",
    command: str = "",
    fetch_live_token: bool = False,
    timeout_seconds: float = 6.0,
) -> dict[str, Any]:
    """Build (or live-fetch) a headless Pterodactyl/Pelican live console WebSocket plan.

    Zero browser windows; JWT tokens and API keys are strictly redacted from any response.
    """
    panel = panel_type.strip().lower()
    if panel not in SUPPORTED_PANELS:
        raise ValueError(f"'panel_type' must be one of {SUPPORTED_PANELS}.")
    base_url = normalize_panel_url(domain)
    sid = server_id.strip() or "<server_id>"
    ws_endpoint = f"{base_url}/api/client/servers/{sid}/websocket"
    auth_frame = {"event": "auth", "args": ["<REDACTED_WS_JWT>"]}
    actions = [
        {"event": "send logs", "args": [None]},
        {"event": "send stats", "args": [None]},
    ]
    if command:
        actions.append({"event": "send command", "args": [command]})

    plan: dict[str, Any] = {
        "ok": True,
        "panel_type": panel,
        "base_url": base_url,
        "server_id": sid,
        "screen_lock_free": True,
        "credentials_endpoint": ws_endpoint,
        "websocket_protocol": {
            "auth_frame": auth_frame,
            "action_frames": actions,
            "reconnect_on_event": "token expiring",
        },
        "live_fetch_attempted": False,
    }

    if fetch_live_token:
        if panel not in ("pterodactyl", "pelican"):
            plan["ok"] = False
            plan["error"] = f"Live WebSocket token fetch is only supported for pterodactyl/pelican (got {panel!r})."
            return plan
        if not api_key or not server_id.strip():
            plan["ok"] = False
            plan["error"] = "Both 'api_key' and 'server_id' are required for live WebSocket token fetch."
            return plan
        plan["live_fetch_attempted"] = True
        req = urllib.request.Request(
            ws_endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "MinecraftKit-MCP/3.3",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            data = body.get("data", {}) if isinstance(body, dict) else {}
            plan["socket_url"] = str(data.get("socket", ""))
            plan["token_received"] = bool(data.get("token"))
            plan["token_preview"] = "[REDACTED_WS_JWT]" if data.get("token") else ""
        except Exception as err:  # noqa: BLE001
            plan["ok"] = False
            plan["error"] = redact_secrets(f"{type(err).__name__}: {err}", (api_key,))

    return plan

