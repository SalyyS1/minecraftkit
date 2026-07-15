from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
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

    def make_source(self, base: Path, *, fail_query: bool = False) -> tuple[Path, list[dict[str, object]]]:
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
            "import sys\n"
            "root = Path(sys.argv[1])\n"
            "required = [root / 'SKILL.md', root / 'data/minecraft-domain-catalog.json']\n"
            "raise SystemExit(0 if all(path.is_file() for path in required) else 9)\n",
            encoding="utf-8",
        )
        (source / "scripts" / "query_api.py").write_text(
            f"raise SystemExit({17 if fail_query else 0})\n",
            encoding="utf-8",
        )
        return source, domains

    def run_installer(
        self,
        source: Path,
        codex: Path,
        claude: Path,
        commands: Path,
        *,
        plan_only: bool = False,
    ) -> subprocess.CompletedProcess[str]:
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
        if plan_only:
            command.append("-PlanOnly")
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")

    @staticmethod
    def create_existing_target(path: Path, value: str) -> None:
        path.mkdir(parents=True)
        (path / "old.txt").write_text(value, encoding="utf-8")

    def test_plan_has_canonical_wrappers_and_commands_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, domains = self.make_source(base)
            codex = base / "destinations" / "codex"
            claude = base / "destinations" / "claude"
            commands = base / "destinations" / "commands"

            result = self.run_installer(source, codex, claude, commands, plan_only=True)

            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["canonicalSkill"], "minecraftkit")
            self.assertEqual(len(plan["installs"]), 21)
            self.assertEqual(sum(item["kind"] == "canonical" for item in plan["installs"]), 2)
            self.assertEqual(sum(item["kind"] == "wrapper" for item in plan["installs"]), 18)
            self.assertEqual(sum(item["kind"] == "commands" for item in plan["installs"]), 1)
            expected_wrappers = {str(domain["skill_directory"]) for domain in domains}
            for root in (codex, claude):
                names = {item["name"] for item in plan["installs"] if Path(item["target"]).parent == root}
                self.assertEqual(names, {"minecraftkit", *expected_wrappers})
            self.assertEqual(
                {Path(path).name for path in plan["preservedLegacyTargets"]},
                {"minecraft-rpg-kit"},
            )
            self.assertFalse(codex.exists())
            self.assertFalse(claude.exists())
            self.assertFalse(commands.exists())

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
            self.assertEqual(len(plan["installs"]), 21)

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
            expected_canonical = tree_hashes(source)
            for root, label in ((codex, "codex"), (claude, "claude")):
                self.assertEqual(tree_hashes(root / "minecraftkit"), expected_canonical)
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
