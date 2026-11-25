"""Real Java 21 loopback E2E test for McKitVisualClientMod + v6.0.0 cloud templates."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cloud_grid_templates  # noqa: E402


HARNESS_JAVA = r"""
import com.salyvn.mckit.client.McKitVisualClientMod;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;

public final class VisualModRuntimeHarness {
    public static void main(String[] args) throws Exception {
        McKitVisualClientMod mod = new McKitVisualClientMod();
        String token = "mckit-loopback-secret-v60";
        Path capDir = java.nio.file.Files.createTempDirectory("mckit-visual-cap-");
        java.nio.file.Files.write(capDir.resolve("stage-01-shop.png"), new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A});
        mod.startBridge(0, token, capDir);
        try {
            int port = mod.getBoundPort();
            if (port <= 0) throw new AssertionError("Expected ephemeral bound port > 0");
            mod.recordScreen("ShopInventoryScreen");
            mod.recordPackStatus(java.util.List.of("vanilla", "SalyRPG_Pack_v2"), "ComplementaryUnbound_r5.2", 0, 1);
            mod.recordRenderMetrics(58, 17.24);
            mod.recordRenderMetrics(74, 13.51);
            mod.recordPackError("Shader uniform u_FogColor missing");

            HttpClient client = HttpClient.newHttpClient();
            HttpResponse<String> unauth = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/status"))
                    .header("X-MCKit-Token", "wrong-token")
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            if (unauth.statusCode() != 401) {
                throw new AssertionError("Expected 401 on wrong token, got " + unauth.statusCode());
            }

            HttpResponse<String> status = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/status"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            HttpResponse<String> packStatus = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/pack-status"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            HttpResponse<String> renderMetrics = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/render-metrics"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            HttpResponse<String> captures = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/captures"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            HttpResponse<String> errors = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/errors"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            HttpResponse<String> shot = client.send(
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/screenshot"))
                    .header("X-MCKit-Token", token)
                    .GET().build(),
                HttpResponse.BodyHandlers.ofString()
            );
            if (status.statusCode() != 200 || packStatus.statusCode() != 200 || renderMetrics.statusCode() != 200 || captures.statusCode() != 200 || errors.statusCode() != 200 || shot.statusCode() != 200) {
                throw new AssertionError("Expected 200 from all authorized endpoints");
            }
            System.out.println("{\"status\":" + status.body() + ",\"pack_status\":" + packStatus.body() + ",\"render_metrics\":" + renderMetrics.body() + ",\"captures\":" + captures.body() + ",\"errors\":" + errors.body() + ",\"shot\":" + shot.body() + "}");
        } finally {
            mod.stopBridge();
            java.nio.file.Files.deleteIfExists(capDir.resolve("stage-01-shop.png"));
            java.nio.file.Files.deleteIfExists(capDir);
        }
    }
}
"""


class VisualClientModAndCloudV60Tests(unittest.TestCase):
    def test_oracle_free_arm64_and_hetzner_cloud_templates(self) -> None:
        oracle = cloud_grid_templates.generate_cloud_bot_deploy(
            target="oracle_free_arm64",
            server_host="play.salyvn.net",
            bot_count=10,
            mc_version="1.21.4",
            include_visual_xvfb=True,
        )
        self.assertTrue(oracle["ok"])
        self.assertEqual(oracle["filename"], "oracle-arm64-mckit-setup.sh")
        self.assertIn("Oracle Cloud Always-Free ARM64", oracle["content"])
        self.assertIn("mem_limit:", oracle["content"])

        hetzner = cloud_grid_templates.generate_cloud_bot_deploy(
            target="hetzner_docker_vps",
            server_host="play.salyvn.net",
            bot_count=6,
            mc_version="1.21.4",
            include_visual_xvfb=True,
        )
        self.assertTrue(hetzner["ok"])
        self.assertEqual(hetzner["filename"], "docker-compose.hetzner-mckit.yml")
        self.assertIn("mckit-visual-xvfb", hetzner["content"])
        self.assertIn("shm_size: \"512m\"", hetzner["content"])

    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK required for live client-mod E2E")
    def test_visual_client_mod_live_loopback_http_bridge(self) -> None:
        mod_src = ROOT / "client-mod" / "src" / "main" / "java" / "com" / "salyvn" / "mckit" / "client" / "McKitVisualClientMod.java"
        self.assertTrue(mod_src.is_file())
        with tempfile.TemporaryDirectory(prefix="mckit-v60-clientmod-") as tmp:
            out_dir = Path(tmp) / "classes"
            out_dir.mkdir(parents=True, exist_ok=True)
            harness_src = Path(tmp) / "VisualModRuntimeHarness.java"
            harness_src.write_text(HARNESS_JAVA, encoding="utf-8")

            comp = subprocess.run(
                ["javac", "-d", str(out_dir), str(mod_src), str(harness_src)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(comp.returncode, 0, msg=comp.stderr)

            run = subprocess.run(
                ["java", "-cp", str(out_dir), "VisualModRuntimeHarness"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)
            payload = json.loads(run.stdout.strip())
            self.assertEqual(payload["status"]["screen"], "ShopInventoryScreen")
            self.assertEqual(payload["status"]["error_count"], 1)
            self.assertEqual(payload["pack_status"]["shader_pack"], "ComplementaryUnbound_r5.2")
            self.assertEqual(payload["pack_status"]["fps"], 74)
            self.assertEqual(payload["pack_status"]["missing_models"], 1)
            self.assertIn("SalyRPG_Pack_v2", payload["pack_status"]["active_packs"])
            self.assertTrue(payload["pack_status"]["offscreen_headless"])
            self.assertEqual(payload["render_metrics"]["min_fps"], 58)
            self.assertEqual(payload["render_metrics"]["samples"], 2)
            self.assertGreaterEqual(payload["render_metrics"]["heap_max_mb"], 1)
            self.assertEqual(payload["captures"]["count"], 1)
            self.assertEqual(payload["captures"]["files"][0]["name"], "stage-01-shop.png")
            self.assertIn("u_FogColor", payload["errors"]["errors"][0]["message"])
            self.assertTrue(payload["shot"]["offscreen"])


if __name__ == "__main__":
    unittest.main()
