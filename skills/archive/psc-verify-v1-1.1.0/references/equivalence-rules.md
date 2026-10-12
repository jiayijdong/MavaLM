# Field-wise PSC equivalence rules

## Safe normalization

- Ignore case, surrounding whitespace, Unicode/ASCII typography, and harmless punctuation.
- Accept journal abbreviations that uniquely denote the same journal.
- Accept common chemical name/formula aliases only when composition is unchanged, such as methylammonium/MA, formamidinium/FA, and MAPbI3/CH3NH3PbI3. Accept an unambiguous spelling variant such as Spiro-OMeTAD/Spiro-MeOTAD.
- Convert units dimensionally: nm/um, s/min/h/d, V/mV, A/mA, M/mM, power-per-area, and area units. For example, `0.03 V/s` equals `30 mV/s`, `720 h` equals `30 d`, and an intensity of `1 sun` equals `100 mW cm-2`.
- Compare a unitless number with a unit-bearing number only when the schema declares that field's canonical unit. Thus `100` may equal `100 nm` in a thickness field, but not in an unspecified field.
- Treat `N2`, `nitrogen`, and `nitrogen glovebox` as equivalent only for an atmosphere field; a glovebox does not establish pressure, humidity, or purity.
- For `Perovskite_deposition_sequential_spin_coating` only, accept the dataset encoding `False = 1 = 1.0` and `True = 2 = 2.0`.

## Numerical fields

After unit conversion, use absolute tolerance 0.005 V for `Voc`, 0.05 mA cm-2 for `Jsc`, 0.1 percentage point for FF/PCE/retention, 2 nm for thickness, and 1% relative tolerance for scan rate, concentration, time, and temperature. Values rounded more coarsely in the reference may match within half of its last reported digit.

Percent fractions are field-sensitive: `0.80` may equal `80%` for FF or retention, but never for concentration unless the unit establishes that conversion. Preserve uncertainty, ranges, and inequalities: `>1000 h` is not equal to `1000 h`, and `20-25 C` is not automatically equal to `25 C`.

## Ordered and composite values

- Device stacks and layer-specific values are ordered. Ignore a passive substrate alias such as glass/SLG only when all electrically active layers align.
- In the coarse `Cell_stack_sequence` field, accept a generic perovskite layer name in place of its explicit composition. A compact/mesoporous TiO2 pair may collapse to one generic TiO2 layer only when the reference is explicitly coarse and the remaining active stack aligns. Do not apply this collapse to deposition, morphology, or processing fields.
- Accept NiOx/NiO as a conventional non-stoichiometric notation only when context makes the intended nickel-oxide layer unambiguous. Never equate NiO2 with NiO/NiOx, SnO2 with TiO2, or C60 with PCBM.
- Preserve ratios and order: `DMF:DMSO = 4:1` is not equivalent to `1:4`.
- For slash-delimited layer properties, align values positionally. Permit omitted trailing null placeholders only when a known layer map establishes the same positions. `Spin-coating/Null` does not equal `Spin-coating/Spin-coating`.
- In a layer-property field, treat prefixes such as `NiOx:Null/PTAA:Null` as layer alignment keys and the property values as `Null/Null`; do not treat the material names as property values.
- Mixed compositions match only when coefficients are algebraically equivalent within reported precision. Unknown symbols such as x/y/z are allowed, but their relationships must be preserved. A generic `FAPbI3-based` value does not equal an explicit mixed-cation composition in a composition field.

## Processing semantics

Accept close method synonyms such as spin coat/spin-coating and thermal evaporation/vacuum evaporation. Accept the generic `evaporation` only when field context rules out a different evaporation process. Do not merge spin coating with blade coating, slot-die coating, spray coating, evaporation, or atomic-layer deposition. Annealing and drying are distinct unless the source uses the terms interchangeably for the same step.

A material in the precursor is not equivalent to the same material applied as a surface treatment. Likewise, antisolvent identity, application timing, spin speed, annealing conditions, and atmosphere are independent claims.

For expanded concentration descriptions, compare the concentration of each aligned component after unit conversion. Preparation volumes may be ignored only when they do not change that concentration. Never hide a missing or extra component behind an abbreviated form.

## Device identity and performance

Forward and reverse scans are not interchangeable. Scanned PCE, stabilized PCE, and certified PCE are distinct claims. Mask area is not equivalent to active area unless the reference explicitly treats them as the same aperture. A stability result from another device is not equivalent to a champion-device result even when the stack is nominally identical.

Treat light spectrum and light intensity separately. `AM1.5G` describes a spectrum; `1 sun` and `100 mW cm-2` describe intensity. They are not interchangeable merely because they commonly occur together.

## Output validation

For the non-null pairs supplied to the semantic verifier, allowed labels are exactly `TP` and `FP_mismatch`. Return one label for every supplied field; let the harness reject missing keys or additional prose.
