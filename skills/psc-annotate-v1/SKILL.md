---
name: psc-annotate-v1
description: Extract a schema-conformant, evidence-grounded record for the champion single-junction perovskite solar cell from a full article and its supporting PDFs. Use for PSC literature annotation, experimental-detail extraction, champion-device selection, or construction of auditable 97-field JSON records.
---

# PSC annotation v1

Produce one record for the device with the highest explicitly reported scan PCE. Treat the article and supporting information as one source package, but never fill a field from general knowledge or from another device.

## Required references

Read [field-guide.md](references/field-guide.md) before extracting values. Load [psc-record.schema.json](references/psc-record.schema.json) as the exact output contract.

## Workflow

1. Inventory every PDF and read the main text, methods, tables, captions, and supporting information. Preserve the filename and page for each internally tracked value.
2. Enumerate candidate devices and select the highest-PCE single-junction PSC. Keep scan direction, active/masked area, certification, stabilized output, and stability specimens distinct.
3. Build an internal evidence ledger keyed by schema field. Prefer explicit device-specific statements over general methods; use nearby table headers, footnotes, and sample codes to resolve identity.
4. Populate every schema key exactly once. Emit strings only. Use `Null` when a value is absent, ambiguous between devices, or only inferable.
5. Run the consistency checks below, then return only the JSON object unless the user explicitly requests an evidence ledger.

## Consistency checks

- Confirm `PCE = Voc * Jsc * FF / 100` within rounding tolerance for each scan direction.
- Align slash-delimited layer properties with the order in `Cell_stack_sequence`; do not collapse distinct layers.
- Keep precursor additives separate from post-deposition surface treatments.
- Do not convert a stability retention percentage into an absolute PCE, or vice versa.
- Set certification fields only when an independent accredited measurement is explicitly reported.
- Set device-matching fields to `True` only when the text links the measurement to the champion device; otherwise use `False` or `Null` according to the evidence.

## Harness boundary

This Skill defines domain behavior and output semantics. The STEAD harness owns PDF parsing, model invocation, schema validation, provenance capture, and file I/O. Do not change the contract to accommodate a model response.
