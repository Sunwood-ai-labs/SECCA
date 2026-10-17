"""Skill validation fixtures, independent of a local Codex installation."""

from pathlib import Path
import tempfile
import unittest

from validate_skill import validate


class SkillValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "agents").mkdir()
        (self.root / "references").mkdir()
        self.skill = self.root / "SKILL.md"
        self.text = "---\nname: secca\ndescription: Run the fixed CAD task.\n---\n\n[Run guide](references/run.md)\n"
        self.skill.write_text(self.text, encoding="utf-8")
        (self.root / "references/run.md").write_text("Run guide fixture.\n", encoding="utf-8")
        self.agent = self.root / "agents/openai.yaml"
        self.agent.write_text('interface:\n  display_name: "SECCA"\n  default_prompt: "Use $secca to run the fixed CAD task."\n', encoding="utf-8")

    def test_self_contained_entrypoint_passes(self):
        result = validate(self.root)
        self.assertTrue(result["success"])
        self.assertEqual(result["local_links_checked"], ["references/run.md"])

    def test_frontmatter_name_and_description_are_required(self):
        for text in (self.text.replace("name: secca", "name: other"),
                     self.text.replace("description: Run the fixed CAD task.", "description: ''"),
                     self.text.removeprefix("---\n")):
            with self.subTest(text=text):
                self.skill.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    validate(self.root)

    def test_wrong_skill_invocation_is_rejected(self):
        self.agent.write_text('interface:\n  display_name: "SECCA"\n  default_prompt: "Use $secca-old."\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_missing_local_link_is_rejected(self):
        (self.root / "references/run.md").unlink()
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_local_link_cannot_escape_the_checkout(self):
        self.skill.write_text(self.text.replace("references/run.md", "../outside.md"), encoding="utf-8")
        with self.assertRaises(ValueError):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
