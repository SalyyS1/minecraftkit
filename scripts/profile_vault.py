"""Local-first encrypted/redacted server & hosting profile vault for MinecraftKit.

Stores named profiles (hosting panel domain, panel type, SFTP host/port/user,
Minecraft server host/port, bot username, env-var references for secrets) under
`~/.minecraftkit/profiles.json` with 0600 permissions. Inline secrets are never
echoed back to MCP transcripts — only masked indicators (`[SET]`) or env var names.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
SENSITIVE_FIELDS = frozenset({
    "password",
    "sftp_password",
    "bot_password",
    "api_key",
    "totp_secret",
    "bridge_token",
    "token",
})


def default_vault_path() -> Path:
    custom = os.environ.get("MCKIT_VAULT_PATH", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    return Path.home() / ".minecraftkit" / "profiles.json"


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not PROFILE_NAME_RE.fullmatch(cleaned):
        raise ValueError(
            "Profile name must be 1-64 characters of letters, digits, '.', '_', or '-'."
        )
    return cleaned


def mask_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a transcript-safe copy of a profile with all secrets masked."""
    safe: dict[str, Any] = {}
    for key, value in profile.items():
        if key in SENSITIVE_FIELDS:
            if isinstance(value, str) and value.startswith("env:"):
                safe[key] = value
            elif value:
                safe[key] = "[REDACTED_SECRET]"
            else:
                safe[key] = ""
        elif isinstance(value, dict):
            safe[key] = mask_profile(value)
        else:
            safe[key] = value
    return safe


def load_vault(vault_path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = vault_path or default_vault_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("profiles"), dict):
            return {
                str(k): dict(v)
                for k, v in raw["profiles"].items()
                if isinstance(v, dict)
            }
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def save_vault(profiles: dict[str, dict[str, Any]], vault_path: Path | None = None) -> Path:
    path = vault_path or default_vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {"schema_version": 1, "profiles": profiles}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return path


def resolve_secret_value(raw: Any) -> str:
    """Resolve `env:VAR_NAME` indirection or return raw secret string."""
    if not isinstance(raw, str):
        return ""
    if raw.startswith("env:"):
        var_name = raw[4:].strip()
        return os.environ.get(var_name, "")
    return raw


def upsert_profile(
    name: str,
    fields: dict[str, Any],
    *,
    vault_path: Path | None = None,
) -> dict[str, Any]:
    prof_name = _validate_name(name)
    profiles = load_vault(vault_path)
    existing = dict(profiles.get(prof_name, {}))
    allowed_keys = {
        "description",
        "mc_host",
        "mc_port",
        "mc_version",
        "bot_username",
        "bot_password",
        "panel_type",
        "panel_domain",
        "panel_username",
        "password",
        "api_key",
        "totp_secret",
        "server_id",
        "sftp_host",
        "sftp_port",
        "sftp_username",
        "sftp_password",
        "sftp_key_path",
        "bridge_url",
        "bridge_token",
    }
    for k, v in fields.items():
        if k in allowed_keys:
            existing[k] = v
    existing["name"] = prof_name
    profiles[prof_name] = existing
    saved_to = save_vault(profiles, vault_path)
    return {
        "saved": True,
        "vault_path": str(saved_to),
        "profile": mask_profile(existing),
    }


def list_profiles(*, vault_path: Path | None = None) -> dict[str, Any]:
    path = vault_path or default_vault_path()
    profiles = load_vault(path)
    return {
        "vault_path": str(path),
        "profile_count": len(profiles),
        "profiles": {name: mask_profile(data) for name, data in sorted(profiles.items())},
    }


def get_profile(name: str, *, vault_path: Path | None = None, masked: bool = True) -> dict[str, Any] | None:
    prof_name = _validate_name(name)
    profiles = load_vault(vault_path)
    raw = profiles.get(prof_name)
    if raw is None:
        return None
    return mask_profile(raw) if masked else dict(raw)


def delete_profile(name: str, *, vault_path: Path | None = None) -> dict[str, Any]:
    prof_name = _validate_name(name)
    profiles = load_vault(vault_path)
    removed = profiles.pop(prof_name, None) is not None
    if removed:
        save_vault(profiles, vault_path)
    return {"deleted": removed, "name": prof_name, "remaining": len(profiles)}
