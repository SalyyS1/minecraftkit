from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-global.ps1"
DOMAIN_CATALOG = ROOT / "data" / "minecraft-domain-catalog.json"
EXCLUDED_NAMES = {"dist", "__pycache__", ".git", ".gitignore", ".gitattributes"}


def tree_hashes(root: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_NAMES or part.endswith(".pyc") for part in relative.parts):
            continue
        records[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return records


class MinecraftKitInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = shutil.which("pwsh") or shutil.which("powershell")
        if cls.powershell is None:
            raise unittest.SkipTest("PowerShell is required for installer contract tests")

    def make_source(
        self,
        base: Path,
        *,
        fail_query: bool = False,
        fail_query_after: int | None = None,
    ) -> tuple[Path, list[dict[str, object]]]:
        source = base / "source"
        (source / "data").mkdir(parents=True)
        (source / "commands" / "mc").mkdir(parents=True)
        (source / "skill-wrappers").mkdir()
        (source / "scripts").mkdir()
        domains = json.loads(DOMAIN_CATALOG.read_text(encoding="utf-8"))["domains"]
        (source / "SKILL.md").write_text("---\nname: minecraftkit\n---\n", encoding="utf-8")
        (source / "data" / "minecraft-domain-catalog.json").write_text(
            json.dumps({"schema_version": 1, "domains": domains}, indent=2) + "\n",
            encoding="utf-8",
        )
        for domain in domains:
            wrapper = source / "skill-wrappers" / str(domain["skill_directory"])
            wrapper.mkdir()
            (wrapper / "SKILL.md").write_text(
                f"---\nname: {domain['skill_directory']}\n---\nroute wrapper\n",
                encoding="utf-8",
            )
            (source / "commands" / "mc" / f"{domain['id']}.md").write_text(
                f"# /{domain['route']}\n",
                encoding="utf-8",
            )
        (source / "scripts" / "validate_kit.py").write_text(
            "from pathlib import Path\n"
            "import os, sys, time\n"
            "root = Path(sys.argv[1])\n"
            "marker = os.environ.get('MINECRAFTKIT_TEST_VALIDATE_MARKER')\n"
            "if marker:\n"
            "    Path(marker).write_text('locked', encoding='utf-8')\n"
            "    time.sleep(float(os.environ.get('MINECRAFTKIT_TEST_VALIDATE_DELAY', '0')))\n"
            "required = [root / 'SKILL.md', root / 'data/minecraft-domain-catalog.json']\n"
            "raise SystemExit(0 if all(path.is_file() for path in required) else 9)\n",
            encoding="utf-8",
        )
        failure_call = 1 if fail_query else fail_query_after
        if failure_call is None:
            query_script = "raise SystemExit(0)\n"
        else:
            counter_path = base / "query-counter.txt"
            query_script = (
                "from pathlib import Path\n"
                f"counter = Path({str(counter_path)!r})\n"
                "count = int(counter.read_text(encoding='utf-8')) + 1 if counter.exists() else 1\n"
                "counter.write_text(str(count), encoding='utf-8')\n"
                f"raise SystemExit(17 if count == {failure_call} else 0)\n"
            )
        (source / "scripts" / "query_api.py").write_text(query_script, encoding="utf-8")
        return source, domains

    def installer_command(
        self,
        source: Path,
        codex: Path,
        claude: Path,
        commands: Path,
        *,
        target: str | None = None,
        plan_only: bool = False,
    ) -> list[str]:
        command = [
            str(self.powershell),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-SourceRoot",
            str(source),
            "-CodexSkillsRoot",
            str(codex),
            "-ClaudeSkillsRoot",
            str(claude),
            "-ClaudeCommandsRoot",
            str(commands),
            "-Python",
            sys.executable,
        ]
        if target is not None:
            command.extend(["-Target", target])
        if plan_only:
            command.append("-PlanOnly")
        return command

    def run_installer(
        self,
        source: Path,
        codex: Path,
        claude: Path,
        commands: Path,
        *,
        target: str | None = None,
        plan_only: bool = False,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = self.installer_command(
            source,
            codex,
            claude,
            commands,
            target=target,
            plan_only=plan_only,
        )
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )

    @staticmethod
    def create_existing_target(path: Path, value: str) -> None:
        path.mkdir(parents=True)
        (path / "old.txt").write_text(value, encoding="utf-8")

    def test_promotion_uses_no_replace_directory_move_before_marking_ownership(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        move = "[System.IO.Directory]::Move($record.Stage, $record.Target)"
        promoted = "$record.Promoted = $true"
        self.assertIn(move, script)
        self.assertIn(promoted, script)
        self.assertLess(script.index(move), script.index(promoted, script.index(move)))
        self.assertNotIn("Move-Item -LiteralPath $record.Stage", script)

    def test_plan_supports_all_targets_without_touching_unused_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, domains = self.make_source(base)
            expected_wrappers = {str(domain["skill_directory"]) for domain in domains}
            expectations = {
                "codex": (len(domains) + 1, {"Codex"}, 1),
                "claude": (len(domains) + 2, {"Claude"}, 1),
                "both": (2 * len(domains) + 3, {"Codex", "Claude"}, 2),
            }
            for target, (count, clients, legacy_count) in expectations.items():
                with self.subTest(target=target):
                    destinations = base / target
                    codex = destinations / "codex" if target != "claude" else source
                    claude = destinations / "claude" if target != "codex" else source
                    commands = destinations / "commands" if target != "codex" else source

                    result = self.run_installer(
                        source,
                        codex,
                        claude,
                        commands,
                        target=target,
                        plan_only=True,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    plan = json.loads(result.stdout)
                    self.assertEqual(plan["target"], target)
                    self.assertEqual(plan["canonicalSkill"], "minecraftkit")
                    self.assertEqual(len(plan["installs"]), count)
                    self.assertEqual({item["client"] for item in plan["installs"]}, clients)
                    self.assertEqual(
                        sum(item["kind"] == "canonical" for item in plan["installs"]),
                        len(clients),
                    )
                    self.assertEqual(
                        sum(item["kind"] == "wrapper" for item in plan["installs"]),
                        len(domains) * len(clients),
                    )
                    self.assertEqual(
                        sum(item["kind"] == "commands" for item in plan["installs"]),
                        int(target in {"claude", "both"}),
                    )
                    for root in (codex, claude):
                        if root == source:
                            continue
                        names = {
                            item["name"]
                            for item in plan["installs"]
                            if Path(item["target"]).parent == root
                        }
                        self.assertEqual(names, {"minecraftkit", *expected_wrappers})
                    self.assertEqual(len(plan["preservedLegacyTargets"]), legacy_count)
                    self.assertTrue(
                        all(Path(path).name == "minecraft-rpg-kit" for path in plan["preservedLegacyTargets"])
                    )
                    self.assertFalse(destinations.exists())

    def test_selected_install_does_not_validate_or_write_unused_roots(self) -> None:
        for target in ("codex", "claude"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                source, domains = self.make_source(base)
                source_before = tree_hashes(source)
                codex = base / "codex" if target == "codex" else source
                claude = base / "claude" if target == "claude" else source
                commands = base / "commands" if target == "claude" else source

                result = self.run_installer(source, codex, claude, commands, target=target)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(tree_hashes(source), source_before)
                selected_skill_root = codex if target == "codex" else claude
                self.assertTrue((selected_skill_root / "minecraftkit" / "SKILL.md").is_file())
                self.assertFalse((selected_skill_root / "minecraftkit" / "skill-wrappers").exists())
                self.assertEqual(
                    list((selected_skill_root / "minecraftkit").rglob("SKILL.md")),
                    [selected_skill_root / "minecraftkit" / "SKILL.md"],
                )
                for domain in domains:
                    self.assertTrue((selected_skill_root / str(domain["skill_directory"]) / "SKILL.md").is_file())
                installed_skills = [
                    path
                    for path in selected_skill_root.iterdir()
                    if path.is_dir() and (path / "SKILL.md").is_file()
                ]
                self.assertEqual(len(installed_skills), 11)
                if target == "claude":
                    self.assertTrue((commands / "mc").is_dir())
                    self.assertEqual(len(installed_skills) + int((commands / "mc").is_dir()), 12)
                self.assertFalse((source / "minecraftkit").exists())

    def test_script_location_is_the_default_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, _ = self.make_source(base)
            copied_installer = source / "scripts" / "install-global.ps1"
            shutil.copy2(INSTALLER, copied_installer)
            command = [
                str(self.powershell),
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(copied_installer),
                "-CodexSkillsRoot",
                str(base / "codex"),
                "-ClaudeSkillsRoot",
                str(base / "claude"),
                "-ClaudeCommandsRoot",
                str(base / "commands"),
                "-Python",
                sys.executable,
                "-PlanOnly",
            ]

            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")

            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["canonicalSkill"], "minecraftkit")
            self.assertEqual(len(plan["installs"]), 2 * len(json.loads(
                (source / "data" / "minecraft-domain-catalog.json").read_text(encoding="utf-8")
            )["domains"]) + 3)

    def test_temp_install_backs_up_targets_and_preserves_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, domains = self.make_source(base)
            codex, claude, commands = base / "codex", base / "claude", base / "commands"
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.create_existing_target(root / "minecraftkit", f"old-{label}-canonical")
                self.create_existing_target(root / "mc-rpg", f"old-{label}-rpg")
                self.create_existing_target(root / "minecraft-rpg-kit", f"legacy-{label}")
            self.create_existing_target(commands / "mc", "old-commands")

            result = self.run_installer(source, codex, claude, commands)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected_canonical = {
                relative: checksum
                for relative, checksum in tree_hashes(source).items()
                if not relative.startswith("skill-wrappers/")
            }
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.assertEqual(tree_hashes(root / "minecraftkit"), expected_canonical)
                self.assertFalse((root / "minecraftkit" / "skill-wrappers").exists())
                for domain in domains:
                    name = str(domain["skill_directory"])
                    self.assertEqual(
                        tree_hashes(root / name),
                        tree_hashes(source / "skill-wrappers" / name),
                    )
                self.assertEqual((root / "minecraft-rpg-kit" / "old.txt").read_text(encoding="utf-8"), f"legacy-{label}")
                canonical_backups = list(root.glob("minecraftkit.backup-*"))
                rpg_backups = list(root.glob("mc-rpg.backup-*"))
                self.assertEqual(len(canonical_backups), 1)
                self.assertEqual(len(rpg_backups), 1)
                self.assertEqual(
                    (canonical_backups[0] / "old.txt").read_text(encoding="utf-8"),
                    f"old-{label}-canonical",
                )
                self.assertEqual((rpg_backups[0] / "old.txt").read_text(encoding="utf-8"), f"old-{label}-rpg")
            self.assertEqual(tree_hashes(commands / "mc"), tree_hashes(source / "commands" / "mc"))
            command_backups = list(commands.glob("mc.backup-*"))
            self.assertEqual(len(command_backups), 1)
            self.assertEqual((command_backups[0] / "old.txt").read_text(encoding="utf-8"), "old-commands")
            self.assertFalse(any(base.rglob(".minecraftkit-stage-*")))
            self.assertFalse(any(base.rglob(".minecraftkit-commands-stage-*")))

    def test_failure_rolls_back_every_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, domains = self.make_source(base, fail_query=True)
            codex, claude, commands = base / "codex", base / "claude", base / "commands"
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.create_existing_target(root / "minecraftkit", f"old-{label}-canonical")
                self.create_existing_target(root / "mc-rpg", f"old-{label}-rpg")
                self.create_existing_target(root / "minecraft-rpg-kit", f"legacy-{label}")
            self.create_existing_target(commands / "mc", "old-commands")

            result = self.run_installer(source, codex, claude, commands)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical smoke test failed", result.stdout + result.stderr)
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.assertEqual((root / "minecraftkit" / "old.txt").read_text(encoding="utf-8"), f"old-{label}-canonical")
                self.assertEqual((root / "mc-rpg" / "old.txt").read_text(encoding="utf-8"), f"old-{label}-rpg")
                self.assertEqual((root / "minecraft-rpg-kit" / "old.txt").read_text(encoding="utf-8"), f"legacy-{label}")
                for domain in domains:
                    name = str(domain["skill_directory"])
                    if name != "mc-rpg":
                        self.assertFalse((root / name).exists())
            self.assertEqual((commands / "mc" / "old.txt").read_text(encoding="utf-8"), "old-commands")
            self.assertFalse(any(base.rglob("*.backup-*")))
            self.assertFalse(any(base.rglob(".minecraftkit-stage-*")))
            self.assertFalse(any(base.rglob(".minecraftkit-commands-stage-*")))

    def test_late_failure_after_multiple_promotions_restores_all_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, domains = self.make_source(base, fail_query_after=2)
            codex, claude, commands = base / "codex", base / "claude", base / "commands"
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.create_existing_target(root / "minecraftkit", f"old-{label}-canonical")
                self.create_existing_target(root / "mc-rpg", f"old-{label}-rpg")
            self.create_existing_target(commands / "mc", "old-commands")

            result = self.run_installer(source, codex, claude, commands)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Claude canonical smoke test failed", result.stdout + result.stderr)
            self.assertEqual((base / "query-counter.txt").read_text(encoding="utf-8"), "2")
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.assertEqual(
                    (root / "minecraftkit" / "old.txt").read_text(encoding="utf-8"),
                    f"old-{label}-canonical",
                )
                self.assertEqual((root / "mc-rpg" / "old.txt").read_text(encoding="utf-8"), f"old-{label}-rpg")
                for domain in domains:
                    name = str(domain["skill_directory"])
                    if name != "mc-rpg":
                        self.assertFalse((root / name).exists())
            self.assertEqual((commands / "mc" / "old.txt").read_text(encoding="utf-8"), "old-commands")
            self.assertFalse(any(base.rglob("*.backup-*")))
            self.assertFalse(any(base.rglob(".minecraftkit-stage-*")))
            self.assertFalse(any(base.rglob(".minecraftkit-commands-stage-*")))

    def test_concurrent_install_on_same_root_is_rejected_and_lock_is_released(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, _ = self.make_source(base)
            codex, claude, commands = base / "codex", base / "claude", base / "commands"
            marker = base / "validation-started.txt"
            environment = os.environ.copy()
            environment.update(
                {
                    "MINECRAFTKIT_TEST_VALIDATE_MARKER": str(marker),
                    "MINECRAFTKIT_TEST_VALIDATE_DELAY": "3",
                }
            )
            first = subprocess.Popen(
                self.installer_command(source, codex, claude, commands, target="codex"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    if first.poll() is not None:
                        break
                    time.sleep(0.05)
                self.assertTrue(marker.exists(), "first installer never reached locked validation")

                contender = self.run_installer(source, codex, claude, commands, target="codex")
                self.assertNotEqual(contender.returncode, 0)
                self.assertIn("already using root", contender.stdout + contender.stderr)

                first_stdout, first_stderr = first.communicate(timeout=20)
                self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
            finally:
                if first.poll() is None:
                    first.kill()
                    first.communicate(timeout=5)

            retry = self.run_installer(source, codex, claude, commands, target="codex")
            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertTrue((codex / "minecraftkit" / "SKILL.md").is_file())
            self.assertFalse(any(base.rglob(".minecraftkit-stage-*")))

    def test_plan_rejects_overlap_and_catalog_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, _ = self.make_source(base)
            shared = base / "shared"
            overlap = self.run_installer(source, shared, shared / "claude", base / "commands", plan_only=True)
            self.assertNotEqual(overlap.returncode, 0)
            self.assertIn("disjoint physical directories", overlap.stdout + overlap.stderr)

            catalog_path = source / "data" / "minecraft-domain-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["domains"][0]["id"] = "../escape"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            unsafe = self.run_installer(
                source,
                base / "safe-codex",
                base / "safe-claude",
                base / "safe-commands",
                plan_only=True,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("Unsafe domain name", unsafe.stdout + unsafe.stderr)
            self.assertFalse((base / "escape").exists())

    def test_plan_rejects_reparse_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, _ = self.make_source(base)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            try:
                os.symlink(real, linked, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            result = self.run_installer(
                source,
                linked,
                base / "claude",
                base / "commands",
                plan_only=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Reparse-point", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
