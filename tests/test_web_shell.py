"""Regression checks for the unified Minecraft Kit web shell."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class UnifiedWebShellTests(unittest.TestCase):
    def test_every_explorer_uses_the_local_shell_and_logo(self) -> None:
        for name, page in {
            "wiki.html": "wiki",
            "ecosystem.html": "ecosystem",
            "index.html": "api",
        }.items():
            document = (WEB / name).read_text(encoding="utf-8")
            self.assertIn('href="shell.css"', document)
            self.assertIn('src="shell.js" defer', document)
            self.assertIn(f'<body data-page="{page}">', document)
        self.assertGreater((WEB / "assets" / "salyyy-minecraft-kit-logo.webp").stat().st_size, 1_000)

    def test_shell_is_local_safe_and_syntax_valid(self) -> None:
        shell = (WEB / "shell.js").read_text(encoding="utf-8")
        styles = (WEB / "shell.css").read_text(encoding="utf-8")
        self.assertIn("localStorage", shell)
        self.assertIn("mk-loader", shell)
        self.assertNotRegex(shell + styles, r"https?://|innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(")
        result = subprocess.run(
            ["node", "--check", str(WEB / "shell.js")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
