"""Verification tests for MinecraftKit v5.5.0 Docker hardening and off-screen Xvfb capture scripts."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ROOT / "docker"


class V55DockerHardeningTests(unittest.TestCase):
    def test_dockerfiles_use_non_root_user_and_healthchecks(self) -> None:
        for name in ("Dockerfile.protocol-bot", "Dockerfile.visual-bot"):
            text = (DOCKER / name).read_text(encoding="utf-8")
            self.assertIn("USER mckit", text, f"{name} must drop root privileges")
            self.assertIn("HEALTHCHECK", text, f"{name} must define HEALTHCHECK")

    def test_compose_testgrid_enforces_ram_limits_shm_init_and_host_gateway(self) -> None:
        text = (DOCKER / "docker-compose.testgrid.yml").read_text(encoding="utf-8")
        self.assertIn("init: true", text)
        self.assertIn("shm_size: '512m'", text)
        self.assertIn("host.docker.internal:host-gateway", text)
        self.assertIn("mem_limit: 512m", text)
        self.assertIn("mem_limit: 2048m", text)
        self.assertIn("BOT_MAX_RAM_MB", text)

    def test_capture_xvfb_script_passes_bash_syntax_and_emits_keyframe_and_gif(self) -> None:
        script = DOCKER / "capture-xvfb.sh"
        text = script.read_text(encoding="utf-8")
        self.assertIn("trap cleanup EXIT", text)
        self.assertIn("keyframe.png", text)
        self.assertIn("session.gif", text)
        bash = shutil.which("bash")
        if bash:
            res = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
