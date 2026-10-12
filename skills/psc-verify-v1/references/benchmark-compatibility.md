# Legacy o3 compatibility audit

Use this reference only to interpret disagreement with the released o3 labels. Do not include these exceptions in the scientific equivalence prompt.

The original judge contract used several permissive conventions that can conflict with the deterministic missingness table or with scientifically faithful equivalence:

- It sometimes treated `Null` and an implicit `1 atm` pressure as the same negative outcome.
- It allowed reversed ratios such as `4:1` and `1:4`.
- It erased inequality symbols and collapsed ranges or uncertainties to one endpoint.
- It conflated light spectrum (`AM1.5G`) with light intensity (`1 sun`, `100 mW cm-2`).
- It collapsed compact and mesoporous TiO2 layers and allowed chemically unsafe aliases such as NiO2/NiO.
- It allowed omitted null layer slots and coarse stack aliases more broadly than the field schema guarantees.

Preserve the released label as benchmark provenance, but also record the deterministic or scientific-policy expectation. Report legacy-conflict fields as a separate stratum so agreement with o3 is not presented as scientific correctness.
