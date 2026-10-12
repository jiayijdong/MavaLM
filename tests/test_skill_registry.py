from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mavalm.skill_registry import annotation_contract, load_skill, verification_contract  # noqa: E402


class SkillRegistryTests(unittest.TestCase):
    def test_annotation_contract_is_pinned_and_complete(self) -> None:
        package, template, prompt = annotation_contract()
        self.assertEqual(package.identity, {"name": "psc-annotate-v1", "version": "1.0.0"})
        self.assertEqual(len(template), 97)
        self.assertIn("psc-annotate-v1@1.0.0", prompt)
        self.assertIn("Ref_DOI", prompt)

    def test_verification_contract_is_pinned_and_complete(self) -> None:
        package, prompt = verification_contract()
        self.assertEqual(package.identity, {"name": "psc-verify-v1", "version": "1.2.0"})
        for label in ("TN", "FP", "FN", "TP", "FP_mismatch"):
            self.assertIn(label, prompt)
        self.assertIn("normalized exact", prompt)
        self.assertIn("released o3 labels", package.read_text("benchmark_compatibility"))

    def test_archived_paper_skill_loads(self) -> None:
        package, prompt = verification_contract(REPO_ROOT / "skills" / "archive" / "registry.json")
        self.assertEqual(package.identity, {"name": "psc-verify-v1", "version": "1.1.0"})
        self.assertIn("# PSC verification v1.1", prompt)
        self.assertNotIn("normalized exact", prompt)

    def test_unknown_role_fails(self) -> None:
        with self.assertRaises(KeyError):
            load_skill("retrieval")


if __name__ == "__main__":
    unittest.main()
