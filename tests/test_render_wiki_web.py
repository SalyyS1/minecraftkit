from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_wiki_web.py"
CONTENT = ROOT / "data" / "wiki-content.json"
ASSIGNMENT = b"window.SalyyyMinecraftKitWiki="
ROUTES = {"build", "client", "core", "dialog", "model", "nms", "pack", "protocol", "rpg", "shader"}
ROUTE_FIELDS = {"title", "what", "when", "inputs", "workflow", "outputs", "guardrails", "examples"}


def payload_from_javascript(path: Path) -> dict:
    encoded = path.read_bytes()
    if not encoded.startswith(ASSIGNMENT) or not encoded.endswith(b";\n"):
        raise AssertionError("unexpected wiki JavaScript envelope")
    return json.loads(encoded[len(ASSIGNMENT):-2])


class WikiWebRenderTests(unittest.TestCase):
    def test_renderer_is_deterministic_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "web" / "data" / "wiki.js"
            command = [sys.executable, str(SCRIPT), "--input", str(CONTENT), "--output", str(output)]
            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = output.read_bytes()
            second = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(output.read_bytes(), first_bytes)
            self.assertFalse(list(output.parent.glob(".wiki.js.*.tmp")))
            payload = payload_from_javascript(output)
            self.assertEqual({route["id"] for route in payload["routes"]}, ROUTES)
            self.assertEqual({item["target"] for item in payload["installers"]}, {"codex", "claude", "both"})

    def test_content_is_complete_in_vietnamese_and_english(self) -> None:
        content = json.loads(CONTENT.read_text(encoding="utf-8"))
        self.assertEqual(content["product"]["name"], "Salyyy Minecraft Kit")
        self.assertEqual(content["product"]["author"], "SalyVn")
        self.assertEqual({route["id"] for route in content["routes"]}, ROUTES)
        for route in content["routes"]:
            self.assertEqual(set(route["content"]), {"vi", "en"})
            for language in ("vi", "en"):
                translation = route["content"][language]
                self.assertTrue(ROUTE_FIELDS.issubset(translation))
                for field in ROUTE_FIELDS:
                    self.assertTrue(translation[field])
        self.assertGreaterEqual(len(content["chapters"]), 8)
        for chapter in content["chapters"]:
            self.assertEqual(set(chapter["content"]), {"vi", "en"})
            self.assertTrue(chapter["content"]["vi"]["points"])
            self.assertTrue(chapter["content"]["en"]["points"])

    def test_installers_use_three_explicit_raw_main_targets(self) -> None:
        content = json.loads(CONTENT.read_text(encoding="utf-8"))
        installers = {item["target"]: item for item in content["installers"]}
        self.assertEqual(set(installers), {"codex", "claude", "both"})
        raw_entry = "https://raw.githubusercontent.com/SalyyS1/minecraftkit/main/scripts/install-from-github.ps1"
        for target, installer in installers.items():
            self.assertEqual(
                installer["command"],
                f"& ([scriptblock]::Create((Invoke-RestMethod '{raw_entry}'))) -Target {target}",
            )

    def test_validation_failure_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = json.loads(CONTENT.read_text(encoding="utf-8"))
            invalid["routes"] = invalid["routes"][:-1]
            input_path = root / "wiki.json"
            output = root / "wiki.js"
            input_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            output.write_bytes(b"previous\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(input_path), "--output", str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"previous\n")

    def test_static_wiki_is_offline_accessible_and_uses_safe_dom(self) -> None:
        html = (ROOT / "web" / "wiki.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "wiki.css").read_text(encoding="utf-8")
        runtime = (ROOT / "web" / "wiki-app.js").read_text(encoding="utf-8")
        version = json.loads(CONTENT.read_text(encoding="utf-8"))["product"]["version"]
        self.assertGreaterEqual(html.count(version), 3)
        self.assertIn('src="data/wiki.js"', html)
        self.assertIn('src="wiki-app.js"', html)
        self.assertIn('class="skip-link"', html)
        self.assertGreaterEqual(html.count('data-i18n-aria-label='), 4)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn("URLSearchParams", runtime)
        self.assertIn("textContent", runtime)
        self.assertIn("focusRouteCard", runtime)
        self.assertNotIn('behavior: "smooth"', runtime)
        self.assertNotRegex(html, r'<(?:script|link)[^>]+(?:src|href)="https?://')
        self.assertNotRegex(css, r"@import|url\(\s*['\"]?https?://")
        self.assertNotRegex(runtime, r"\bfetch\s*\(|XMLHttpRequest|WebSocket")
        self.assertNotRegex(runtime, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function")
        self.assertNotRegex(runtime, r"\.src\s*=\s*['\"]https?://")

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_runtime_javascript_syntax(self) -> None:
        for path in (ROOT / "web" / "wiki-app.js", ROOT / "web" / "data" / "wiki.js"):
            result = subprocess.run(
                [shutil.which("node") or "node", "--check", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
