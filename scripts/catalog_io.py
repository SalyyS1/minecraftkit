"""Shared deterministic I/O and validation helpers for MinecraftKit catalogs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


KEBAB_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
GITHUB_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def strict_json_bytes(payload: bytes, *, label: str) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Non-standard JSON constant {value} in {label}")
        ),
    )


def strict_json_file(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes(), label=str(path))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(document: Any) -> str:
    return json.dumps(
        document,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


def atomic_write_json(path: Path, document: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(document))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def require_kebab_id(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or KEBAB_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a kebab-case identifier")
    return value


def require_github_repository(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or GITHUB_REPOSITORY.fullmatch(value) is None:
        raise ValueError(f"{label} must be an owner/repository slug")
    return value


def require_string_list(value: Any, *, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty string array")
    normalized = sorted(set(value))
    if len(normalized) != len(value):
        raise ValueError(f"{label} contains duplicates or is not sorted")
    return normalized


def require_https_url(
    value: Any,
    *,
    label: str,
    allowed_hosts: Iterable[str] | None = None,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must be an HTTPS URL without credentials")
    if allowed_hosts is not None and parsed.hostname.lower() not in {
        host.lower() for host in allowed_hosts
    }:
        raise ValueError(f"{label} host is not allowlisted: {parsed.hostname}")
    return value
