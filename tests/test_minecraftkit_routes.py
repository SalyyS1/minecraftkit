from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("missing frontmatter")
    block = text[4:text.index("\n---\n", 4)]
    result: dict[str, str] = {}
    for line in block.splitlines():
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"\'')
    return result


class MinecraftKitRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = json.loads(
            (ROOT / "data" / "minecraft-domain-catalog.json").read_text(encoding="utf-8")
        )

    def test_domain_catalog_drives_wrappers_commands_and_references(self) -> None:
        domains = self.catalog["domains"]
        self.assertEqual(self.catalog["schema_version"], 1)
        self.assertEqual(len(domains), 10)
        self.assertIn("build", {item["id"] for item in domains})
        self.assertEqual([item["id"] for item in domains], sorted(item["id"] for item in domains))

        for item in domains:
            with self.subTest(domain=item["id"]):
                domain_id = item["id"]
                route = f"mc:{domain_id}"
                self.assertEqual(item["route"], route)
                self.assertEqual(item["skill_directory"], f"mc-{domain_id}")
                self.assertEqual(item["keywords"], sorted(set(item["keywords"])))

                wrapper = ROOT / "skill-wrappers" / item["skill_directory"] / "SKILL.md"
                wrapper_text = wrapper.read_text(encoding="utf-8")
                self.assertEqual(frontmatter(wrapper_text)["name"], item["skill_directory"])
                self.assertLessEqual(len(wrapper_text.splitlines()), 300)
                self.assertIsNone(re.search(r"\bTODO\b|\[TODO", wrapper_text, re.IGNORECASE))

                command = ROOT / "commands" / "mc" / f"{domain_id}.md"
                command_text = command.read_text(encoding="utf-8")
                self.assertEqual(set(frontmatter(command_text)), {"description", "argument-hint"})
                self.assertIn(f"`/{route}`", command_text)
                self.assertIn(f"`{item['skill_directory']}`", command_text)
                self.assertIn("$ARGUMENTS", command_text)
                self.assertLessEqual(len(command_text.splitlines()), 100)

                reference = ROOT / item["reference"]
                self.assertTrue(reference.is_file(), reference)

    def test_root_skill_is_router_and_mentions_every_route(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = frontmatter(text)
        self.assertEqual(metadata["name"], "minecraftkit")
        self.assertLessEqual(len(text.splitlines()), 300)
        for item in self.catalog["domains"]:
            self.assertIn(f"`{item['route']}`", text)
        for evidence_class in (
            "VERIFIED_UPSTREAM",
            "VERIFIED_BYTECODE",
            "DERIVED_SOURCE",
            "ORIGINAL_DESIGN",
            "UNVERIFIED",
        ):
            self.assertIn(evidence_class, text)

    def test_salyvn_author_identity_is_part_of_the_canonical_kit(self) -> None:
        for relative in ("README.md", "SKILL.md", "NOTICE.md"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("SalyVn / Salyyy", text)

    def test_build_reference_separates_paper_versions_and_shadow_artifacts(self) -> None:
        gradle = (ROOT / "references" / "kotlin-java-gradle.md").read_text(encoding="utf-8")
        build = (ROOT / "references" / "plugin-build-and-shipping.md").read_text(encoding="utf-8")
        handbook = (ROOT / "docs" / "plugin-engineering-handbook.md").read_text(encoding="utf-8")
        for text in (gradle, handbook):
            self.assertIn("paperApiDependencyVersion", text)
            self.assertIn("paperDescriptorApiVersion", text)
            self.assertNotIn('gradleProperty("paperApiVersion")', text)
        self.assertIn("api-version: '${paperDescriptorApiVersion}'", build)
        self.assertIn("api-version: '${paperDescriptorApiVersion}'", handbook)
        self.assertIn('archiveClassifier.set("")', gradle)
        self.assertIn("tasks.jar { enabled = false }", gradle)


if __name__ == "__main__":
    unittest.main()
