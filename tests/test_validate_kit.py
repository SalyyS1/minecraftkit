from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import validate_kit  # noqa: E402
from validate_kit import frontmatter, parse_assignment  # noqa: E402


class ValidationHelperTests(unittest.TestCase):
    def test_frontmatter_requires_simple_mapping(self) -> None:
        parsed = frontmatter("---\nname: minecraft-rpg-kit\ndescription: Query APIs\n---\n# Skill\n")
        self.assertEqual(parsed["name"], "minecraft-rpg-kit")
        with self.assertRaises(ValueError):
            frontmatter("# Missing\n")

    def test_javascript_assignment_is_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.js"
            path.write_text('window.X={"ok":true};\n', encoding="utf-8")
            self.assertEqual(parse_assignment(path, "window.X="), {"ok": True})
            path.write_text("window.X={value:NaN};\n", encoding="utf-8")
            with self.assertRaises(Exception):
                parse_assignment(path, "window.X=")

    def test_malformed_catalog_shape_returns_error_instead_of_raising(self) -> None:
        root = Path(__file__).resolve().parents[1]
        original = validate_kit.strict_json

        def malformed(path: Path):
            if path.name == "api-index.json":
                return {"plugins": [{} for _ in range(10)]}
            return original(path)

        with mock.patch.object(validate_kit, "strict_json", side_effect=malformed):
            errors = validate_kit.validate(root)
        self.assertTrue(any("catalog schema invalid" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
