"""Create a deterministic MinecraftRPG Kit ZIP and SHA-256 checksum."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
from validate_kit import release_payload_files, strict_json  # noqa: E402

def included_files(root: Path) -> list[Path]:
    return release_payload_files(root)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _temporary_path(directory: Path, destination_name: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{destination_name}.", suffix=".tmp", dir=directory)
    os.close(descriptor)
    return Path(name)


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = _temporary_path(path.parent, f"{path.name}.backup")
    try:
        with path.open("rb") as source, backup.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())
        return backup
    except Exception:
        backup.unlink(missing_ok=True)
        raise


def _replace_pair(
    temporary_archive: Path,
    archive: Path,
    temporary_checksum: Path,
    checksum: Path,
    archive_backup: Path | None,
    checksum_backup: Path | None,
) -> None:
    archive_replaced = checksum_replaced = False
    try:
        os.replace(temporary_archive, archive)
        archive_replaced = True
        os.replace(temporary_checksum, checksum)
        checksum_replaced = True
    except Exception:
        if archive_replaced:
            if archive_backup is None:
                archive.unlink(missing_ok=True)
            else:
                os.replace(archive_backup, archive)
        if checksum_replaced:
            if checksum_backup is None:
                checksum.unlink(missing_ok=True)
            else:
                os.replace(checksum_backup, checksum)
        raise


def _write_archive(path: Path, root: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        output.comment = b""
        for source in included_files(root):
            relative = Path("minecraft-rpg-kit") / source.relative_to(root)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits = 0
            info.internal_attr = 0
            info.external_attr = 0o100644 << 16
            info.extra = b""
            info.comment = b""
            output.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    validator = root / "scripts" / "validate_kit.py"
    result = subprocess.run([sys.executable, "-B", str(validator), str(root)], check=False)
    if result.returncode:
        return result.returncode

    release = strict_json(root / "manifest.json")
    version = release.get("version") if isinstance(release, dict) else None
    if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("Validated manifest contains an unsafe package version")
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / f"minecraft-rpg-kit-{version}.zip"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    for target in (archive, checksum):
        resolved = target.resolve()
        if resolved.parent != dist.resolve():
            raise ValueError(f"Unsafe package output: {resolved}")

    temporary_archive: Path | None = None
    temporary_checksum: Path | None = None
    archive_backup: Path | None = None
    checksum_backup: Path | None = None
    try:
        temporary_archive = _temporary_path(dist, archive.name)
        temporary_checksum = _temporary_path(dist, checksum.name)
        _write_archive(temporary_archive, root)
        value = sha256(temporary_archive)
        with temporary_checksum.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(f"{value}  {archive.name}\n")
            handle.flush()
            os.fsync(handle.fileno())
        archive_backup = _backup_file(archive)
        checksum_backup = _backup_file(checksum)
        _replace_pair(temporary_archive, archive, temporary_checksum, checksum, archive_backup, checksum_backup)
    finally:
        for temporary in (temporary_archive, temporary_checksum, archive_backup, checksum_backup):
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(f"Packaged {archive} ({archive.stat().st_size} bytes)")
    print(f"SHA-256 {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
