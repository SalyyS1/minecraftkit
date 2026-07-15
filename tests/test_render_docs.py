from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_docs.py"
sys.path.insert(0, str(SCRIPT.parent))

import render_docs  # noqa: E402


def sample_index() -> dict:
    return {
        "schema_version": 1,
        "plugins": [{
            "name": "Example.Plugin",
            "jar": "Example.jar",
            "namespace_prefixes": ["demo"],
            "classes": [{
                "id": "Example.Plugin:demo.Owner",
                "plugin": "Example.Plugin",
                "origin": "plugin-owned",
                "name": "demo.Owner",
                "package": "demo",
                "simple_name": "Owner",
                "kind": "class",
                "visibility": "public",
                "modifiers": ["public"],
                "major_version": 61,
                "java_release": 0,
                "super": "java.lang.Object",
                "interfaces": [],
                "generic_signature": None,
                "deprecated": False,
                "jar_entry": "demo/Owner.class",
                "source_path": "demo/Owner.java",
                "members": [],
            }],
        }],
    }


class RenderTests(unittest.TestCase):
    def run_render(self, data: Path, docs: Path, web: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--data", str(data), "--docs", str(docs), "--web", str(web)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_renders_staged_docs_and_web(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, docs, web = root / "data", root / "docs", root / "web"
            data.mkdir()
            (data / "api-index.json").write_text(json.dumps(sample_index()), encoding="utf-8")
            result = self.run_render(data, docs, web)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest_text = (web / "data" / "manifest.js").read_text(encoding="utf-8")
            self.assertIn("Example.Plugin", manifest_text)
            self.assertTrue((docs / "api" / "index.md").is_file())
            self.assertFalse(any(path.name.startswith(".api-stage") for path in docs.iterdir()))

    def test_rejects_overlap_without_deleting_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web, data, docs = root / "web", root / "web" / "data", root / "docs"
            data.mkdir(parents=True)
            source = data / "api-index.json"
            source.write_text(json.dumps(sample_index()), encoding="utf-8")
            result = self.run_render(data, docs, web)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(source.is_file())

    def assert_snapshot_restored(self, data: Path, docs: Path, web: Path) -> None:
        self.assertEqual((data / "docs-manifest.json").read_bytes(), b'{"snapshot":"old"}\n')
        self.assertEqual((docs / "api" / "old-api.txt").read_bytes(), b"old api\n")
        self.assertEqual((web / "data" / "old-web.txt").read_bytes(), b"old web\n")
        self.assertEqual(list((docs / "api").iterdir()), [docs / "api" / "old-api.txt"])
        self.assertEqual(list((web / "data").iterdir()), [web / "data" / "old-web.txt"])
        for parent in (data, docs, web):
            self.assertFalse(
                [path for path in parent.iterdir() if path.name.startswith(".")],
                f"transaction residue remained under {parent}",
            )

    def prepare_previous_snapshot(self, root: Path) -> tuple[Path, Path, Path]:
        data, docs, web = root / "data", root / "docs", root / "web"
        (docs / "api").mkdir(parents=True)
        (web / "data").mkdir(parents=True)
        data.mkdir()
        (data / "api-index.json").write_text(json.dumps(sample_index()), encoding="utf-8")
        (data / "docs-manifest.json").write_bytes(b'{"snapshot":"old"}\n')
        (docs / "api" / "old-api.txt").write_bytes(b"old api\n")
        (web / "data" / "old-web.txt").write_bytes(b"old web\n")
        return data, docs, web

    def run_in_process(self, data: Path, docs: Path, web: Path) -> int:
        argv = [str(SCRIPT), "--data", str(data), "--docs", str(docs), "--web", str(web)]
        with mock.patch.object(sys, "argv", argv):
            return render_docs.main()

    def test_second_directory_promotion_failure_restores_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data, docs, web = self.prepare_previous_snapshot(Path(directory))
            original_replace = Path.replace

            def fail_api_promotion(source: Path, target: Path) -> Path:
                if source.name.startswith(".api-stage-") and Path(target) == docs / "api":
                    raise OSError("injected api promotion failure")
                return original_replace(source, target)

            with mock.patch.object(Path, "replace", new=fail_api_promotion):
                with self.assertRaisesRegex(OSError, "injected api promotion failure"):
                    self.run_in_process(data, docs, web)

            self.assert_snapshot_restored(data, docs, web)

    def test_manifest_publication_failure_restores_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data, docs, web = self.prepare_previous_snapshot(Path(directory))
            original_replace = Path.replace

            def fail_manifest_publication(source: Path, target: Path) -> Path:
                if source.name.startswith(".docs-manifest-stage-") and Path(target) == data / "docs-manifest.json":
                    raise OSError("injected manifest publication failure")
                return original_replace(source, target)

            with mock.patch.object(Path, "replace", new=fail_manifest_publication):
                with self.assertRaisesRegex(OSError, "injected manifest publication failure"):
                    self.run_in_process(data, docs, web)

            self.assert_snapshot_restored(data, docs, web)


if __name__ == "__main__":
    unittest.main()
