from __future__ import annotations

import copy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_manifest  # noqa: E402
import package_kit  # noqa: E402
import validate_kit  # noqa: E402


class ReleasePolicyTests(unittest.TestCase):
    def test_release_tree_rejects_unknown_and_decompiled_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unexpected.txt").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected top-level"):
                validate_kit.release_payload_files(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "Accidental.java").write_text("class Accidental {}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forbidden release payload"):
                validate_kit.release_payload_files(root)

    def test_release_tree_excludes_repository_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text("skill\n", encoding="utf-8")
            (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
            (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
            git = root / ".git"
            git.mkdir()
            (git / "config").write_text("repository metadata\n", encoding="utf-8")

            included = [path.relative_to(root).as_posix() for path in validate_kit.release_payload_files(root)]

            self.assertEqual(included, ["SKILL.md"])

    def test_safe_path_requires_normalized_posix_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(validate_kit.safe_posix_descendant(root, "data/file.json"), root / "data" / "file.json")
            for unsafe in ("../escape", "/absolute", "data\\file.json", "data//file.json", "C:/escape"):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    validate_kit.safe_posix_descendant(root, unsafe)

    def test_release_manifest_requires_exact_schema_and_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = {}
            for relative in build_manifest.TRACKED:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(relative.encode("utf-8"))
                artifacts[relative] = {"bytes": path.stat().st_size, "sha256": validate_kit.digest(path)}
            expected = {
                "schema_version": build_manifest.SCHEMA_VERSION,
                "name": build_manifest.KIT_NAME,
                "version": build_manifest.KIT_VERSION,
                "research_date": build_manifest.RESEARCH_DATE,
                "catalog": {"plugin_count": 10},
                "plugins": [{"name": "Example"}],
                "artifacts": artifacts,
                "install_targets": dict(build_manifest.INSTALL_TARGETS),
            }
            self.assertEqual(validate_kit.validate_release_manifest(root, copy.deepcopy(expected), expected), [])

            missing = copy.deepcopy(expected)
            missing["artifacts"] = {}
            self.assertIn("release manifest artifact set is invalid", validate_kit.validate_release_manifest(root, missing, expected))

            unsafe = copy.deepcopy(expected)
            descriptor = unsafe["artifacts"].pop(build_manifest.TRACKED[0])
            unsafe["artifacts"]["../escape"] = descriptor
            self.assertTrue(any("artifact path is invalid" in error for error in validate_kit.validate_release_manifest(root, unsafe, expected)))

            malformed = copy.deepcopy(expected)
            malformed["plugins"] = []
            malformed["extra"] = True
            errors = validate_kit.validate_release_manifest(root, malformed, expected)
            self.assertIn("release manifest plugins are invalid", errors)
            self.assertIn("release manifest top-level keys are invalid", errors)

            wrong_type = copy.deepcopy(expected)
            wrong_type["catalog"]["plugin_count"] = True
            self.assertIn("release manifest catalog is invalid", validate_kit.validate_release_manifest(root, wrong_type, expected))


class AtomicReleaseTests(unittest.TestCase):
    def test_atomic_manifest_write_preserves_old_file_on_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manifest.json"
            target.write_text("old", encoding="utf-8")
            with mock.patch.object(build_manifest.os, "replace", side_effect=OSError("blocked")):
                with self.assertRaises(OSError):
                    build_manifest.atomic_write_text(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(target.parent.glob(".manifest.json.*.tmp")), [])

    def test_zip_metadata_and_bytes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            (root / "SKILL.md").write_text("deterministic\n", encoding="utf-8")
            first = base / "first.zip"
            second = base / "second.zip"
            package_kit._write_archive(first, root)
            package_kit._write_archive(second, root)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                info = archive.infolist()[0]
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.external_attr, 0o100644 << 16)

    def test_package_filename_uses_validated_manifest_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            validator = scripts / "validate_kit.py"
            validator.write_text("", encoding="utf-8")
            with (
                mock.patch.object(sys, "argv", ["package_kit.py", str(root)]),
                mock.patch.object(package_kit.subprocess, "run", return_value=mock.Mock(returncode=0)),
                mock.patch.object(package_kit, "strict_json", return_value={"version": "2.3.4"}),
                mock.patch.object(package_kit, "_write_archive", side_effect=lambda path, _root: path.write_bytes(b"zip")),
            ):
                self.assertEqual(package_kit.main(), 0)
            self.assertTrue((root / "dist" / "minecraft-rpg-kit-2.3.4.zip").is_file())
            self.assertTrue((root / "dist" / "minecraft-rpg-kit-2.3.4.zip.sha256").is_file())

    def test_package_restores_previous_pair_when_second_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "validate_kit.py").write_text("", encoding="utf-8")
            dist = root / "dist"
            dist.mkdir()
            archive = dist / "minecraft-rpg-kit-2.3.4.zip"
            checksum = archive.with_suffix(".zip.sha256")
            archive.write_bytes(b"old-archive")
            checksum.write_bytes(b"old-checksum")
            real_replace = package_kit.os.replace
            calls = 0

            def fail_second_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated checksum promotion failure")
                return real_replace(source, destination)

            with (
                mock.patch.object(sys, "argv", ["package_kit.py", str(root)]),
                mock.patch.object(package_kit.subprocess, "run", return_value=mock.Mock(returncode=0)),
                mock.patch.object(package_kit, "strict_json", return_value={"version": "2.3.4"}),
                mock.patch.object(package_kit, "_write_archive", side_effect=lambda path, _root: path.write_bytes(b"new-archive")),
                mock.patch.object(package_kit.os, "replace", side_effect=fail_second_replace),
            ):
                with self.assertRaisesRegex(OSError, "checksum promotion"):
                    package_kit.main()
            self.assertEqual(archive.read_bytes(), b"old-archive")
            self.assertEqual(checksum.read_bytes(), b"old-checksum")
            self.assertEqual(list(dist.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
