from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-from-github.ps1"
VERSION = "2.2.1"
ARCHIVE_NAME = f"minecraftkit-{VERSION}.zip"


BUNDLED_INSTALLER = r"""[CmdletBinding()]
param(
    [string]$SourceRoot,
    [ValidateSet('codex', 'claude', 'both')]
    [string]$Target = 'both',
    [string]$CodexSkillsRoot,
    [string]$ClaudeSkillsRoot,
    [string]$ClaudeCommandsRoot,
    [string]$Python,
    [switch]$PlanOnly
)
if ($env:MINECRAFTKIT_TEST_MARKER) {
    [IO.File]::WriteAllText($env:MINECRAFTKIT_TEST_MARKER, $Target, [Text.Encoding]::UTF8)
}
[ordered]@{
    target = $Target
    sourceRoot = $SourceRoot
    codexSkillsRoot = $CodexSkillsRoot
    claudeSkillsRoot = $ClaudeSkillsRoot
    claudeCommandsRoot = $ClaudeCommandsRoot
    python = $Python
    planOnly = [bool]$PlanOnly
} | ConvertTo-Json -Compress
"""


class GitHubBootstrapInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = shutil.which("pwsh") or shutil.which("powershell")
        if cls.powershell is None:
            raise unittest.SkipTest("PowerShell is required for bootstrap installer tests")

    def make_fixture(
        self,
        base: Path,
        *,
        entries: list[tuple[str, bytes]] | None = None,
        checksum: str | None = None,
        draft: bool = False,
        prerelease: bool = False,
    ) -> Path:
        fixture = base / "release-fixture"
        fixture.mkdir()
        archive = fixture / ARCHIVE_NAME
        archive_entries = entries or [
            ("minecraftkit/SKILL.md", b"---\nname: minecraftkit\n---\n"),
            ("minecraftkit/scripts/install-global.ps1", BUNDLED_INSTALLER.encode("utf-8")),
        ]
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, content in archive_entries:
                output.writestr(name, content)

        actual_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        sidecar_hash = actual_hash if checksum is None else checksum
        sidecar = fixture / f"{ARCHIVE_NAME}.sha256"
        sidecar.write_text(
            f"{sidecar_hash}  {ARCHIVE_NAME}\n",
            encoding="ascii",
            newline="\n",
        )
        (fixture / "ignored.txt").write_text("decoy", encoding="utf-8")
        metadata = {
            "tag_name": f"v{VERSION}",
            "name": f"MinecraftKit v{VERSION}",
            "draft": draft,
            "prerelease": prerelease,
            "assets": [
                {"name": "ignored.txt"},
                {"name": ARCHIVE_NAME, "size": archive.stat().st_size},
                {"name": f"{ARCHIVE_NAME}.sha256", "size": sidecar.stat().st_size},
                {"name": "minecraftkit-not-a-version.zip"},
            ],
        }
        (fixture / "release.json").write_text(json.dumps(metadata), encoding="utf-8")
        return fixture

    def run_installer(
        self,
        base: Path,
        fixture: Path,
        *,
        target: str | None = None,
        version: str | None = None,
        allow_test_source: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temp_root = base / "bootstrap-temp"
        temp_root.mkdir(exist_ok=True)
        marker = base / "installer-invoked.txt"
        command = [
            str(self.powershell),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
        ]
        if allow_test_source:
            command.append("-AllowTestSource")
        command.extend(
            [
                "-TestReleaseDirectory",
                str(fixture),
                "-CodexSkillsRoot",
                str(base / "codex"),
                "-ClaudeSkillsRoot",
                str(base / "claude"),
                "-ClaudeCommandsRoot",
                str(base / "commands"),
                "-Python",
                sys.executable,
                "-PlanOnly",
            ]
        )
        if target is not None:
            command.extend(["-Target", target])
        if version is not None:
            command.extend(["-Version", version])
        environment = os.environ.copy()
        environment.update(
            {
                "TEMP": str(temp_root),
                "TMP": str(temp_root),
                "MINECRAFTKIT_TEST_MARKER": str(marker),
            }
        )
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        return result, marker, temp_root

    def assert_temp_clean(self, temp_root: Path) -> None:
        self.assertEqual(list(temp_root.glob("mk-*")), [])

    def test_release_longest_allowlisted_path_fits_windows_temp_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            longest_release_entry = (
                "minecraftkit/docs/api/mythicdungeons-575406b3ce57/"
                "net-playavalon-mythicdungeons-compatibility-betonquest-objectives-"
                "f41af2b131a8-part-01.md"
            )
            fixture = self.make_fixture(
                base,
                entries=[
                    ("minecraftkit/SKILL.md", b"skill"),
                    ("minecraftkit/scripts/install-global.ps1", BUNDLED_INSTALLER.encode("utf-8")),
                    (longest_release_entry, b"api shard"),
                ],
            )

            result, marker, temp_root = self.run_installer(base, fixture, target="codex")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8-sig"), "codex")
            self.assert_temp_clean(temp_root)

    def test_defaults_use_expected_repository_and_latest_release_api(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("[string]$Repository = 'SalyyS1/minecraftkit'", script)
        self.assertIn('releases/latest"', script)
        self.assertIn("[ValidateSet('codex', 'claude', 'both')]", script)
        self.assertIn("$MaximumArchiveBytes = 64MB", script)
        self.assertIn("$MaximumChecksumBytes = 64KB", script)
        self.assertIn("$MaximumArchiveEntries = 20000", script)
        self.assertIn("$MaximumExpandedBytes = 512MB", script)
        self.assertIn("$MaximumRedirects = 5", script)
        self.assertIn("$request.AllowAutoRedirect = $false", script)
        self.assertIn("release-assets.githubusercontent.com", script)
        public_headers = script[
            script.index("function Get-PublicAssetHeaders") : script.index("function Get-BoundedAssetSize")
        ]
        self.assertNotIn("Authorization", public_headers)
        self.assertIn("-PublicHeaders $assetHeaders", script)

    def test_selects_verified_assets_and_passes_through_each_target(self) -> None:
        for requested, expected in ((None, "both"), ("codex", "codex"), ("claude", "claude"), ("both", "both")):
            with self.subTest(target=requested), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                fixture = self.make_fixture(base)

                result, marker, temp_root = self.run_installer(base, fixture, target=requested)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["target"], expected)
                self.assertTrue(payload["planOnly"])
                self.assertEqual(payload["python"], sys.executable)
                self.assertEqual(marker.read_text(encoding="utf-8-sig"), expected)
                self.assert_temp_clean(temp_root)

    def test_in_memory_bootstrap_runs_verified_installer_under_restricted_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(base)
            temp_root = base / "bootstrap-temp"
            temp_root.mkdir()
            marker = base / "installer-invoked.txt"

            def quote(value: Path | str) -> str:
                return str(value).replace("'", "''")

            command_text = (
                f"$bootstrap=[IO.File]::ReadAllText('{quote(INSTALLER)}',[Text.Encoding]::UTF8);"
                "& ([scriptblock]::Create($bootstrap)) "
                f"-AllowTestSource -TestReleaseDirectory '{quote(fixture)}' "
                f"-CodexSkillsRoot '{quote(base / 'codex')}' "
                f"-ClaudeSkillsRoot '{quote(base / 'claude')}' "
                f"-ClaudeCommandsRoot '{quote(base / 'commands')}' "
                f"-Python '{quote(sys.executable)}' -PlanOnly -Target codex"
            )
            encoded = base64.b64encode(command_text.encode("utf-16-le")).decode("ascii")
            environment = os.environ.copy()
            environment.update(
                {
                    "TEMP": str(temp_root),
                    "TMP": str(temp_root),
                    "MINECRAFTKIT_TEST_MARKER": str(marker),
                }
            )
            result = subprocess.run(
                [
                    str(self.powershell),
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Restricted",
                    "-EncodedCommand",
                    encoded,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["target"], "codex")
            self.assertEqual(marker.read_text(encoding="utf-8-sig"), "codex")
            self.assert_temp_clean(temp_root)

    def test_checksum_mismatch_stops_before_execution_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(base, checksum="0" * 64)

            result, marker, temp_root = self.run_installer(base, fixture, target="codex")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 checksum mismatch", result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)

    def test_missing_or_oversized_asset_metadata_is_rejected_before_download(self) -> None:
        for mutation, expected in (("missing", "missing size"), ("oversized", "metadata exceeds")):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                fixture = self.make_fixture(base)
                metadata_path = fixture / "release.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                archive_asset = next(item for item in metadata["assets"] if item["name"] == ARCHIVE_NAME)
                if mutation == "missing":
                    archive_asset.pop("size")
                else:
                    archive_asset["size"] = 64 * 1024 * 1024 + 1
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

                result, marker, temp_root = self.run_installer(base, fixture)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, (result.stdout + result.stderr).lower())
                self.assertFalse(marker.exists())
                self.assert_temp_clean(temp_root)

    def test_actual_asset_bytes_are_capped_independently_of_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(base)
            (fixture / f"{ARCHIVE_NAME}.sha256").write_bytes(b"x" * (64 * 1024 + 1))

            result, marker, temp_root = self.run_installer(base, fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("byte limit", (result.stdout + result.stderr).lower())
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)

    def test_archive_entry_count_limit_stops_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            entries = [
                ("minecraftkit/SKILL.md", b"skill"),
                ("minecraftkit/scripts/install-global.ps1", BUNDLED_INSTALLER.encode("utf-8")),
            ]
            entries.extend((f"minecraftkit/empty/{index}.txt", b"") for index in range(20_000))
            fixture = self.make_fixture(base, entries=entries)

            result, marker, temp_root = self.run_installer(base, fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("too many entries", (result.stdout + result.stderr).lower())
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)

    def test_traversal_entry_is_rejected_before_execution_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(
                base,
                entries=[
                    ("minecraftkit/SKILL.md", b"skill"),
                    ("minecraftkit/scripts/install-global.ps1", BUNDLED_INSTALLER.encode("utf-8")),
                    ("minecraftkit/../../escape.txt", b"escape"),
                ],
            )

            result, marker, temp_root = self.run_installer(base, fixture, target="claude")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path traversal", (result.stdout + result.stderr).lower())
            self.assertFalse(marker.exists())
            self.assertFalse((base / "escape.txt").exists())
            self.assert_temp_clean(temp_root)

    def test_deep_overlong_entry_is_rejected_before_prefix_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            deep_entry = "minecraftkit/" + "/".join(["a"] * 300)
            fixture = self.make_fixture(
                base,
                entries=[
                    ("minecraftkit/SKILL.md", b"skill"),
                    ("minecraftkit/scripts/install-global.ps1", BUNDLED_INSTALLER.encode("utf-8")),
                    (deep_entry, b""),
                ],
            )

            result, marker, temp_root = self.run_installer(base, fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path exceeds", (result.stdout + result.stderr).lower())
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)

    def test_prerelease_requires_an_explicit_named_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(base, prerelease=True)

            latest, marker, temp_root = self.run_installer(base, fixture)

            self.assertNotEqual(latest.returncode, 0)
            self.assertIn("refuses draft or prerelease", latest.stdout + latest.stderr)
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)

            named, marker, temp_root = self.run_installer(base, fixture, version=VERSION)
            self.assertEqual(named.returncode, 0, named.stdout + named.stderr)
            self.assertTrue(marker.exists())
            self.assert_temp_clean(temp_root)

    def test_fixture_override_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fixture = self.make_fixture(base)

            result, marker, temp_root = self.run_installer(base, fixture, allow_test_source=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("disabled unless -AllowTestSource", result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            self.assert_temp_clean(temp_root)


if __name__ == "__main__":
    unittest.main()
