---
name: psc-verify-v1
description: Verify candidate perovskite-solar-cell records against expert references with deterministic missingness and normalized exact matching, field-aware scientific equivalence, and explicit legacy-label audits. Use for PSC annotation scoring, claim-level audits, judge-model evaluation, or TP/TN/FP/FN classification of structured experimental records.
---

# PSC verification v1.2

Classify every candidate/reference field pair without revising either record. Verification measures agreement with an adjudicated reference; it does not establish whether the source paper is scientifically true.

## Decision boundary

Apply these deterministic rules before invoking semantic judgment:

- `TN`: both values are null.
- `FP`: the reference is null and the candidate is non-null.
- `FN`: the candidate is null and the reference is non-null.
- `TP`: both values are non-null and identical after trimming surrounding whitespace and case-folding.
- semantic judgment: both values are non-null and not a normalized exact match; choose only `TP` or `FP_mismatch`.

Treat `Null`, `None`, `nan`, `N/A`, `not reported`, `Unknown`, an empty string, and a missing key as null. Numeric zero and the string `False` are not null.

Read [equivalence-rules.md](references/equivalence-rules.md) before judging non-null pairs. Use its field-specific normalization, unit conversion, layer alignment, numerical tolerance, and non-equivalence rules.

## Workflow

1. Let the harness assign missingness labels and normalized-exact `TP` labels.
2. For each remaining non-null, non-exact pair, normalize only transformations allowed by its field rule.
3. Assign `TP` when the values are scientifically equivalent; otherwise assign `FP_mismatch`.
4. Return one JSON object mapping every supplied field name to `TP` or `FP_mismatch`. Add no prose.

## Guardrails

- Do not treat two plausible values as equivalent merely because they describe the same material family or process class.
- Do not reverse ratios, erase inequalities, reorder active device layers, merge different processing steps, or ignore device identity.
- Do not award a TP by consulting the paper to repair an incorrect reference during benchmark scoring. Route suspected reference errors to separate expert adjudication.
- Apply tolerance only to measurement fields and only after unit normalization; identifiers and compositions remain exact unless a field rule says otherwise.
- Keep spectrum, intensity, atmosphere identity, pressure, humidity, and purity as distinct claims.

## Harness boundary

This Skill supplies the semantic judgment policy. The STEAD harness pins the Skill version, constructs field pairs, assigns missingness and normalized-exact labels, validates semantic labels, aggregates metrics, and retains the audit trail. A verifier must never mutate the candidate record.

When measuring agreement with legacy o3 labels, keep fields that conflict with the deterministic outcome table in a separate audit stratum. Read [benchmark-compatibility.md](references/benchmark-compatibility.md) only to interpret that stratum; do not inject its legacy exceptions into the scientific judge prompt.
