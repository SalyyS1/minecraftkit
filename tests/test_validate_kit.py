from __future__ import annotations

import copy
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
        parsed = frontmatter("---\nname: minecraftkit\ndescription: Query APIs\n---\n# Skill\n")
        self.assertEqual(parsed["name"], "minecraftkit")
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

    def test_same_count_stale_ecosystem_payload_is_rejected(self) -> None:
        root = Path(__file__).resolve().parents[1]
        original = validate_kit.parse_assignment

        def stale(path: Path, prefix: str):
            payload = original(path, prefix)
            if path.name == "ecosystem.js":
                payload = copy.deepcopy(payload)
                payload["sources"][0]["github"]["default_branch_head"]["sha"] = "0" * 40
            return payload

        with mock.patch.object(validate_kit, "parse_assignment", side_effect=stale):
            errors = validate_kit.validate(root)
        self.assertIn(
            "ecosystem web payload is stale or differs from its source catalogs",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
