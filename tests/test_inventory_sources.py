from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from inventory_sources import build_inventory, is_reparse, record, validate_inventory, verify  # noqa: E402


def make_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    decompiled = bundle / "decompiled"
    decompiled.mkdir(parents=True)
    for index in range(10):
        (bundle / f"plugin-{index}.jar").write_bytes(f"jar-{index}".encode())
        plugin = decompiled / f"plugin-{index}"
        plugin.mkdir()
        (plugin / "Source.java").write_text(f"class Source{index} {{}}\n", encoding="utf-8")
    return bundle


class InventoryTests(unittest.TestCase):
    def test_inventory_is_deterministic_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = make_bundle(Path(directory))
            first = build_inventory(bundle)
            second = build_inventory(bundle)
            self.assertEqual(first, second)
            self.assertNotIn("generated_at", first)
            self.assertEqual(first["decompiled_file_count"], 10)
            self.assertEqual(verify(bundle, first), (True, []))

    def test_schema_mismatch_has_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = build_inventory(make_bundle(Path(directory)))
            inventory["schema_version"] = 2
            self.assertIn("schema_version", validate_inventory(inventory)[0])

    def test_outside_record_and_reparse_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = root / "inside"
            inside.mkdir()
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaises(ValueError):
                record(outside, inside)
            with mock.patch.object(Path, "is_symlink", return_value=True):
                self.assertTrue(is_reparse(inside))


if __name__ == "__main__":
    unittest.main()
