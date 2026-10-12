"""Field-level outcome scoring shared by every MavaLM experiment.

The verifier labels each (candidate, reference) field pair with one of five
mutually exclusive outcomes:

* ``TN``          both values are null;
* ``FP``          the reference is null but the candidate reports a value
                  (over-prediction, written FP_pure in the paper);
* ``FN``          the reference has a value but the candidate is null;
* ``TP``          both values are present and scientifically equivalent;
* ``FP_mismatch`` both values are present but not equivalent.

Accuracy, precision, recall and F1 follow Appendix A of the paper, with
``FP = FP_pure + FP_mismatch``.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

LABELS: tuple[str, ...] = ("TP", "TN", "FP", "FN", "FP_mismatch")
SEMANTIC_LABELS: tuple[str, ...] = ("TP", "FP_mismatch")

# Legacy evaluation files occasionally spell the over-prediction label FP_pure.
LABEL_ALIASES: Mapping[str, str] = {"FP_pure": "FP"}

# The 97-field PerovskiteNet schema grouped into the seven PSC subfields used
# throughout the paper (Figure 1, Table 2, Figure 3, Appendix D.2).
FIELD_GROUPS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    (
        (
            "Reference data",
            (
                "Ref_DOI",
                "Ref_journal",
                "Ref_publication_year",
                "Ref_title",
            ),
        ),
        (
            "Cell definition",
            (
                "Cell_architecture",
                "Cell_area_measured",
                "Cell_stack_sequence",
            ),
        ),
        (
            "Device stack",
            (
                "Backcontact_thickness",
                "ETL_stack_sequence",
                "ETL_thickness",
                "Encapsulation_method",
                "HTL_stack_sequence",
                "HTL_thickness",
                "Perovskite_bandgap",
                "Perovskite_composition_long_form",
                "Perovskite_surface_treatment_material",
                "Perovskite_thickness",
            ),
        ),
        (
            "Material synthesis",
            (
                "ETL_additive_compound",
                "ETL_additive_concentration",
                "ETL_deposition_solution_concentration",
                "ETL_deposition_solvents_compound",
                "HTL_additive_compound",
                "HTL_additive_concentration",
                "HTL_deposition_solution_concentration",
                "HTL_deposition_solvents_compound",
                "Perovskite_additive_compound",
                "Perovskite_additive_concentration",
                "Perovskite_deposition_final_solutions_concentration_before_deposition",
                "Perovskite_deposition_reaction_solutions_compounds",
                "Perovskite_deposition_reaction_solutions_concentrations",
                "Perovskite_deposition_solvents_compound",
                "Perovskite_deposition_solvents_mixing_ratio",
                "Perovskite_dimension",
                "Perovskite_surface_treatment_solution_concentration",
                "Perovskite_surface_treatment_solvents_compound",
            ),
        ),
        (
            "Device fabrication",
            (
                "Backcontact_deposition_atmosphere_pressure",
                "Backcontact_deposition_method",
                "ETL_deposition_method",
                "ETL_deposition_spin_coating_speed",
                "ETL_deposition_spin_coating_time",
                "ETL_deposition_synthesis_atmosphere",
                "ETL_deposition_synthesis_atmosphere_pressure",
                "ETL_deposition_synthesis_atmosphere_relative_humidity",
                "ETL_deposition_thermal_annealing_temperature",
                "ETL_deposition_thermal_annealing_time",
                "Encapsulation_atmosphere",
                "HTL_deposition_method",
                "HTL_deposition_spin_coating_speed",
                "HTL_deposition_spin_coating_time",
                "HTL_deposition_synthesis_atmosphere",
                "HTL_deposition_synthesis_atmosphere_pressure",
                "HTL_deposition_synthesis_atmosphere_relative_humidity",
                "HTL_deposition_thermal_annealing_temperature",
                "HTL_deposition_thermal_annealing_time",
                "Perovskite_deposition_method",
                "Perovskite_deposition_sequential_spin_coating",
                "Perovskite_deposition_spin_coating_antisolvent",
                "Perovskite_deposition_spin_coating_speed",
                "Perovskite_deposition_spin_coating_time",
                "Perovskite_deposition_synthesis_atmosphere",
                "Perovskite_deposition_synthesis_atmosphere_pressure",
                "Perovskite_deposition_synthesis_atmosphere_relative_humidity",
                "Perovskite_deposition_thermal_annealing_atmosphere",
                "Perovskite_deposition_thermal_annealing_temperature",
                "Perovskite_deposition_thermal_annealing_time",
                "Perovskite_surface_treatment_deposition_spin_coating_speed",
                "Perovskite_surface_treatment_deposition_spin_coating_time",
                "Perovskite_surface_treatment_deposition_thermal_annealing_temperature",
                "Perovskite_surface_treatment_deposition_thermal_annealing_time",
                "Perovskite_surface_treatment_method",
                "Perovskite_surface_treatment_synthesis_atmosphere",
                "Perovskite_surface_treatment_synthesis_atmosphere_pressure",
                "Perovskite_surface_treatment_synthesis_atmosphere_relative_humidity",
            ),
        ),
        (
            "J-V metrics",
            (
                "JV_certified_PCE",
                "JV_measured_device_matching",
                "JV_measured_forward_scan_FF",
                "JV_measured_forward_scan_Jsc",
                "JV_measured_forward_scan_PCE",
                "JV_measured_forward_scan_Voc",
                "JV_measured_light_spectra",
                "JV_measured_light_spectra_intensity",
                "JV_measured_reverse_scan_FF",
                "JV_measured_reverse_scan_Jsc",
                "JV_measured_reverse_scan_PCE",
                "JV_measured_reverse_scan_Voc",
                "JV_measured_scan_delay_time",
                "JV_measured_scan_speed",
                "Stabilized_certified_PCE",
                "Stabilized_measured_PCE",
            ),
        ),
        (
            "Stability metrics",
            (
                "Stability_PCE_after_time",
                "Stability_PCE_after_time_value",
                "Stability_test_atmosphere",
                "Stability_test_device_matching",
                "Stability_test_light_intensity",
                "Stability_test_light_spectra",
                "Stability_test_relative_humidity",
                "Stability_test_temperature",
            ),
        ),
    )
)

SUBFIELDS: tuple[str, ...] = tuple(FIELD_GROUPS)
FIELD_TO_SUBFIELD: Mapping[str, str] = {
    field: group for group, fields in FIELD_GROUPS.items() for field in fields
}
SCHEMA_FIELDS: tuple[str, ...] = tuple(FIELD_TO_SUBFIELD)

# Historic key spellings that map onto the schema field they denote. The
# released candidate records and verifier audits still carry the legacy
# ``Beckcontact_deposition_method`` key of the original annotation template.
FIELD_ALIASES: Mapping[str, str] = {
    "Beckcontact_deposition_method": "Backcontact_deposition_method",
}


def canonical_field(name: str) -> str:
    return FIELD_ALIASES.get(name, name)


def canonical_label(label: Any) -> str | None:
    if not isinstance(label, str):
        return None
    label = LABEL_ALIASES.get(label, label)
    return label if label in LABELS else None


def subfield_of(field: str) -> str | None:
    return FIELD_TO_SUBFIELD.get(canonical_field(field))


def validate_field_groups() -> None:
    grouped = [field for fields in FIELD_GROUPS.values() for field in fields]
    if len(grouped) != len(set(grouped)):
        raise ValueError("FIELD_GROUPS contains duplicate fields")
    if len(grouped) != 97:
        raise ValueError(f"FIELD_GROUPS covers {len(grouped)} fields, expected 97")


@dataclass(frozen=True)
class Scores:
    """Accuracy, precision, recall and F1 derived from five-class counts."""

    TP: int
    TN: int
    FP: int
    FN: int
    FP_mismatch: int

    @property
    def total(self) -> int:
        return self.TP + self.TN + self.FP + self.FN + self.FP_mismatch

    @property
    def false_positives(self) -> int:
        return self.FP + self.FP_mismatch

    @property
    def accuracy(self) -> float:
        return (self.TP + self.TN) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        denominator = self.TP + self.false_positives
        return self.TP / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.TP + self.FN
        return self.TP / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "fields": self.total,
            "TP": self.TP,
            "TN": self.TN,
            "FP": self.FP,
            "FN": self.FN,
            "FP_mismatch": self.FP_mismatch,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def scores_from_counts(counts: Mapping[str, int]) -> Scores:
    return Scores(
        TP=int(counts.get("TP", 0)),
        TN=int(counts.get("TN", 0)),
        FP=int(counts.get("FP", 0)),
        FN=int(counts.get("FN", 0)),
        FP_mismatch=int(counts.get("FP_mismatch", 0)),
    )


def scores_from_labels(labels: Iterable[str]) -> Scores:
    return scores_from_counts(Counter(labels))


def load_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def read_field_decisions(evaluation: Mapping[str, Any]) -> dict[str, str]:
    """Return ``{field: label}`` from a verifier audit file.

    Unknown labels (for example ``ERROR``) are dropped so that only valid
    decisions enter the denominator, mirroring the harness' ``valid_fields``.
    """
    fields = evaluation.get("field_evaluations")
    if not isinstance(fields, Mapping):
        raise ValueError("Evaluation file has no field_evaluations object")
    decisions: dict[str, str] = {}
    for name, item in fields.items():
        if not isinstance(item, Mapping):
            continue
        label = canonical_label(item.get("classification"))
        if label is not None:
            decisions[str(name)] = label
    return decisions


def subfield_counts(decisions: Mapping[str, str]) -> dict[str, Counter]:
    """Split one record's decisions into per-subfield label counters.

    Fields outside the 97-field schema (hallucinated keys from a generator)
    are collected under the ``"<outside schema>"`` key so nothing is lost.
    """
    grouped: dict[str, Counter] = {group: Counter() for group in SUBFIELDS}
    grouped["<outside schema>"] = Counter()
    for field, label in decisions.items():
        group = subfield_of(field) or "<outside schema>"
        grouped[group][label] += 1
    return grouped


validate_field_groups()
