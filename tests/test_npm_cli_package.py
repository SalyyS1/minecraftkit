from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPM_ROOT = ROOT / "npm"


class NpmCliPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.npm = shutil.which("npm")
        if cls.npm is None:
            raise unittest.SkipTest("npm is required to validate the npm CLI package")

    def run_npm(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.npm, *args],
            cwd=NPM_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def test_package_version_and_bootstrap_check_match_kit(self) -> None:
        root_version = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
        package = json.loads((NPM_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "minecraftkit")
        self.assertEqual(package["version"], root_version)
        self.assertEqual(package["bin"], {"minecraftkit": "bin/minecraftkit.js"})

        completed = subprocess.run(
            [self.npm, "run", "check"], cwd=NPM_ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_package_payload_is_small_and_explicit(self) -> None:
        completed = self.run_npm("pack", "--dry-run", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)[0]
        files = {entry["path"] for entry in payload["files"]}
        self.assertEqual(
            files,
            {
                "NOTICE.md", "README.md", "package.json", "bin/minecraftkit.js",
                "lib/arguments.js", "lib/cli.js", "lib/constants.js", "lib/doctor.js",
                "lib/install-from-github.ps1", "lib/powershell.js",
            },
        )
        self.assertLess(payload["unpackedSize"], 100_000)


if __name__ == "__main__":
    unittest.main()
