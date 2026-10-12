from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mavalm.metrics import (  # noqa: E402
    FIELD_GROUPS,
    SCHEMA_FIELDS,
    ModelCatalog,
    model_token_from_evaluation_name,
    read_field_decisions,
    scores_from_counts,
    subfield_counts,
    subfield_of,
)


class ScoreTests(unittest.TestCase):
    def test_metric_definitions_follow_appendix_a(self) -> None:
        scores = scores_from_counts({"TP": 41, "TN": 47, "FP": 0, "FN": 4, "FP_mismatch": 5})
        self.assertEqual(scores.total, 97)
        self.assertAlmostEqual(scores.accuracy, 88 / 97)
        self.assertAlmostEqual(scores.precision, 41 / 46)
        self.assertAlmostEqual(scores.recall, 41 / 45)
        p, r = 41 / 46, 41 / 45
        self.assertAlmostEqual(scores.f1, 2 * p * r / (p + r))

    def test_empty_record_baseline_is_share_of_empty_reference_fields(self) -> None:
        scores = scores_from_counts({"TN": 3534, "FN": 6166})
        self.assertAlmostEqual(scores.accuracy, 0.3643, places=4)
        self.assertEqual(scores.precision, 0.0)
        self.assertEqual(scores.recall, 0.0)

    def test_field_groups_cover_schema_once(self) -> None:
        self.assertEqual(len(SCHEMA_FIELDS), 97)
        self.assertEqual(len(FIELD_GROUPS), 7)
        self.assertEqual(sum(len(f) for f in FIELD_GROUPS.values()), 97)
        self.assertEqual(subfield_of("Ref_DOI"), "Reference data")
        self.assertEqual(subfield_of("Backcontact_deposition_method"), "Device fabrication")
        self.assertEqual(subfield_of("Beckcontact_deposition_method"), "Device fabrication")  # legacy key in audits
        self.assertIsNone(subfield_of("not_a_field"))

    def test_decisions_and_subfields(self) -> None:
        evaluation = {
            "field_evaluations": {
                "Ref_DOI": {"classification": "TP"},
                "Cell_architecture": {"classification": "FP_pure"},
                "Made_up": {"classification": "TN"},
                "Broken": {"classification": "ERROR"},
            }
        }
        decisions = read_field_decisions(evaluation)
        self.assertEqual(decisions, {"Ref_DOI": "TP", "Cell_architecture": "FP", "Made_up": "TN"})
        grouped = subfield_counts(decisions)
        self.assertEqual(grouped["Reference data"]["TP"], 1)
        self.assertEqual(grouped["Cell definition"]["FP"], 1)
        self.assertEqual(grouped["<outside schema>"]["TN"], 1)


class ReleaseTests(unittest.TestCase):
    def test_token_resolution_is_longest_first_and_case_insensitive(self) -> None:
        import json
        import tempfile

        models = {
            "models": [
                {"label": "Baseline", "file_token": "Null_v2", "evaluation_aliases": []},
                {"label": "o3", "file_token": "o3", "evaluation_aliases": []},
                {"label": "o3-mini", "file_token": "o3_mini", "evaluation_aliases": []},
                {"label": "GPT-5 mini", "file_token": "gpt_5_mini", "evaluation_aliases": []},
                {"label": "DeepSeek R1 70B", "file_token": "deepseek_generated_gpt_oss_reprocessed", "evaluation_aliases": ["deepseek_gpt_oss"]},
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(models, handle)
        catalog = ModelCatalog.load(Path(handle.name))
        tokens = catalog.tokens_longest_first
        self.assertEqual(model_token_from_evaluation_name("Evaluation_o3_mini_10.1002_x_by_o3.json", tokens), "o3_mini")
        self.assertEqual(model_token_from_evaluation_name("Evaluation_o3_10.1002_x_by_o3.json", tokens), "o3")
        self.assertEqual(model_token_from_evaluation_name("Evaluation_GPT_5_mini_GT_10.1002.x.json", tokens), "gpt_5_mini")
        self.assertEqual(catalog.label_for("deepseek_gpt_oss"), "DeepSeek R1 70B")
        self.assertEqual(catalog.labels[0], "Baseline")


if __name__ == "__main__":
    unittest.main()
