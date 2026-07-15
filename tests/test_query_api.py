from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from query_api import iter_records, matches, text_line  # noqa: E402


class QueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = {
            "plugins": [{
                "name": "Example",
                "classes": [{
                    "id": "Example:demo.Owner",
                    "name": "demo.Owner",
                    "kind": "class",
                    "visibility": "public",
                    "origin": "plugin-owned",
                    "generic_signature": None,
                    "source_path": "demo/Owner.java",
                    "members": [{
                        "id": "Example:demo.Owner#run(Lorg/bukkit/command/CommandSender;)V",
                        "name": "run",
                        "kind": "method",
                        "visibility": "public",
                        "descriptor": "(Lorg/bukkit/command/CommandSender;)V",
                        "generic_signature": None,
                        "return_type": "void",
                        "parameters": ["org.bukkit.command.CommandSender"],
                        "throws": ["java.io.IOException"],
                    }],
                }],
            }],
        }

    def test_searches_decoded_parameters_and_throws(self) -> None:
        member = list(iter_records(self.index))[1]
        self.assertTrue(matches(member, ["org.bukkit.command.CommandSender"], "Example", "method", "plugin-owned"))
        self.assertTrue(matches(member, ["java.io.IOException"], None, None, "plugin-owned"))
        self.assertFalse(matches(member, ["missing"], None, None, "plugin-owned"))

    def test_origin_filter_and_text_output(self) -> None:
        member = list(iter_records(self.index))[1]
        self.assertFalse(matches(member, ["run"], None, None, "bundled-third-party"))
        self.assertIn("demo.Owner", text_line(member))


if __name__ == "__main__":
    unittest.main()
